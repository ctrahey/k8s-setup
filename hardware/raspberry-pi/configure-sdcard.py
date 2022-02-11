#!/usr/bin/env python
"""
Run this script to customize a freshly-imaged sdcard with specific instance details.
Uses Cloud-Init features to setup networking, host details, and prepare the instance for running kubeadm

Design Goals:
No files should need changed from host-to-host as you move through
all hosts in a cluster, just minor invocation differences.

1. All values that are changed per-cluster should be in config.yaml
2. All values that chage per-host are managed through arguments to this script.

The files which are actually copied to the SDCard are produced from Jinja templates
"""
import os
import argparse
import os.path
import random
from string import Template

import yaml
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from passlib.hash import sha512_crypt


def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


yaml.add_representer(str, str_presenter)


def check_dest(destination):
    for file in ['vmlinuz', 'initrd.img']:
        if not os.path.exists(f"{destination}/{file}"):
            return False
    return True


def address_for_node(cidr: str, offset: int, node_index, keep_mask=True):
    draft = cidr.replace('.0/', f".{node_index + offset}/")
    if keep_mask is False:
        return draft.split('/')[0]
    return draft

def compile_network_stanzas(cfg, hardware, node_role, node_index):
    from pprint import pprint as pp

    profile = cfg['networkHardwareProfiles'][hardware]
    device_alias = {}
    ethernets = {}
    for eth in profile.get('ethernets', []):
        ethernets[eth] = {
            'match': {'name': profile['ethernets'][eth]['match']}
        }
        if 'alias' in profile['ethernets'][eth]:
            device_alias[profile['ethernets'][eth]['alias']] = eth
    for bnd in profile.get('bonds', []):
        #  @todo bonds
        pass

    networks = cfg['networks']
    vlans = {}
    for att in cfg['netAttachments'][node_role]:
        nw = networks[att['network']]
        block = {
            'id': att['vlan'],
            'addresses': [address_for_node(nw['cidr'], nw['offset'], node_index)] if att.get('staticIPv4', False) else [],
            'link': device_alias.get(att['device'], att['device']),
            'dhcp4': att.get('dhcp', False) and not att.get('staticIPv4', False),
            'nameservers': {
                'addresses': nw.get('dns', [])
            }
        }
        if att.get('staticIPv4', False) and 'gateway' in nw:
            block['gateway4'] = nw['gateway']
        vlans[att['network']] = block
    netwk = {
        'version': 2,
        'ethernets': ethernets,
        'bonds': {},
        'vlans': vlans
    }
    return netwk

def workloads_stanzas(cfg, node_role, node_index, network_setup):
    if node_role != 'control':
        return []
    base = os.path.normpath(os.path.dirname(__file__))

    def stanza(src, dst, substitutions: dict = None):
        with open(f"{base}/workloads/{src}") as this_file:
            content = str(this_file.read())
        if substitutions is not None:
            print(f"doing substitution on {src}")
            content = Template(content).safe_substitute(**substitutions)
        return {
            'path': dst,
            'content': content,
            'permissions': '0644',
            'owner': 'root:root'
        }
    files = []
    nwk = cfg['network']['networks'][cfg['network']['apiserverAttachment']]
    subs = {'CONFIG_ID': 'main' if node_index == 1 else 'backup',
            'KUBEAPI': cfg['network']['kubeAPI'],
            'BACKENDPORT': cfg['network']['apiBackendPort'],
            'FRONTENDPORT': cfg['network']['apiFrontendPort'],
            'PODSUBNET': cfg['network']['podCIDR'],
            'SVCSUBNET': cfg['network']['svcCIDR'],
            'SERVER1IP': address_for_node(nwk['cidr'], nwk['offset'], 1, False),
            'SERVER2IP': address_for_node(nwk['cidr'], nwk['offset'], 2, False),
            'SERVER3IP': address_for_node(nwk['cidr'], nwk['offset'], 3, False)
            }
    files.append(stanza('keepalived.conf','/etc/keepalived/keepalived.conf', subs))
    files.append(stanza('keepalived.yaml', '/etc/kubernetes/manifests/keepalived.yaml', subs))
    files.append(stanza('check_apiserver.sh', '/etc/keepalived/check_apiserver.sh', subs))
    files.append(stanza('haproxy.cfg', '/etc/haproxy/haproxy.cfg', subs))
    files.append(stanza('haproxy.yaml', '/etc/kubernetes/manifests/haproxy.yaml', subs))
    files.append(stanza('kubeadmin.yaml', '/etc/kubernetes/custom-kubeadmin.yaml', subs))
    files.append(stanza('20auto-upgrades', '/etc/apt/apt.conf.d/20auto-upgrades'))
    return files


def main(cfg, hardware, node_role, node_index, destination, dry_run):
    base = os.path.normpath(os.path.dirname(__file__))
    if not dry_run:
        assert check_dest(destination), "Destination does not appear to be linux boot volume."
    pw = input("User Password:")
    pw_hash = sha512_crypt.using(rounds=4096).hash(pw.strip())

    def outfile(path, content):
        if dry_run:
            print(f"\n\nOUTPUT TO {path}\n==============\n")
            print(content)
        else:
            with open(f'{destination}/{path}', 'w') as f:
                if 'user-data' in path:
                    f.write("#cloud-config\n")
                f.write(content)


    netwk = compile_network_stanzas(cfg['network'], hardware, node_role, node_index)
    nw_out = yaml.dump(netwk, sort_keys=False)
    outfile('network-config', nw_out)
    meta = {
        # randint is for cloud-init to recognize a first-boot
        'instance_id': f"{node_role}{node_index}-{random.randint(10000,99999)}",
        'local-hostname': f"{node_role}{node_index}",
    }
    meta_out = yaml.dump(meta)
    outfile('meta-data', meta_out)
    with open(f"{base}/setup.sh") as setup_file:
        setup_contents = setup_file.read()
    files_stanza = [
        {
            'path': '/usr/bin/setup.sh',
            'content': str(setup_contents),
            'permissions': '0744',
            'owner': 'root:root'
        }
    ]
    files_stanza.extend(workloads_stanzas(cfg, node_role, node_index, netwk))
    userdata = {
        'chpasswd': {
            'expire': False,
            'list': ['ubuntu:ubuntu']
        },
        'ssh_pwauth': True,
        'ssh_import_id': ['gh:ctrahey'],
        'users': [
            'default',
            {
                'name': 'ctrahey',
                'gecos': 'Chris Trahey',
                'lock_passwd': False,
                'shell': '/bin/bash',
                'passwd': pw_hash,
                # 'ssh_authorized_keys': cfg['ssh_authorized_keys'],
                'sudo': 'ALL=(ALL) NOPASSWD:ALL'
            }
        ],
        'package_update': False,
        'package_upgrade': False,
        'write_files': files_stanza,
        'runcmd': [
            'dpkg-reconfigure unattended-upgrades -f noninteractive',
            ['/usr/bin/setup.sh']
            # need to install  libdw1 libunwind8 linux-tools-common
            # Boot message: arbitrary executable file formats file system automount point not supported
            # 'dpkg -i /boot/firmware/custom_kernel/*.deb'

        ]
    }
    userdata_out = yaml.dump(userdata, width=1000)
    outfile('user-data', userdata_out)
    cp_cmd = f"cp {base}/cp_files/* {destination}"
    if dry_run:
        print(f"Dry-run: os.system({cp_cmd})")
    else:
        os.system(cp_cmd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--index', help="Node index for hostname, etc.", required=True)
    parser.add_argument('--image', help="Should we perform imaging first?",
                        action='store_true', default=False)
    parser.add_argument('-r', '--role',
                        choices=['control', 'worker', 'xtra'],
                        help="Node role", default="worker")
    parser.add_argument('--hardware',
                        choices=['rpi'],
                        help="Hardware profile", default="rpi")
    parser.add_argument('-d', '--dest', help="Destination - where to copy cloud-init files", required=True)
    parser.add_argument('--dry-run', help="Dry-run, do not actually write to destination but show what we would write",
                        action='store_true', default=False)
    args = parser.parse_args()

    with open('./config.yaml', 'r') as cfg_file:
        cfg = load(cfg_file, Loader=Loader)

    main(cfg, args.hardware, args.role, int(args.index), args.dest, args.dry_run)
