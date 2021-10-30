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


def main(node_type, node_index, destination, dry_run):
    assert check_dest(destination), "Destination does not appear to be linux boot volume."

    pw = input("User Password:")
    pw_hash = sha512_crypt.using(rounds=4096).hash(pw.strip())

    with open('./config.yaml', 'r') as cfg_file:
        cfg = load(cfg_file, Loader=Loader)

    def outfile(path, content):
        if dry_run:
            print(f"\n\nOUTPUT TO {path}\n==============\n")
            print(content)
        else:
            with open(f'{destination}/{path}', 'w') as f:
                if 'user-data' in path:
                    f.write("#cloud-config\n")
                f.write(content)

    ipv4pattern = cfg['ipv4Pattern'][node_type]
    ipv4 = ipv4pattern % node_index
    ipv4GW = ipv4pattern[:-3] % 254
    netwk = {
        'version': 2,
        'ethernets': {
            'eth0': {
                'dhcp4': 'no',
                'addresses': [
                    ipv4
                ],
                'gateway4': ipv4GW,
                'nameservers': {
                    'addresses': cfg['dns']
                }
            }
        }
    }
    nw_out = yaml.dump(netwk)
    outfile('network-config', nw_out)
    meta = {
        'instance_id': f"{node_type}{node_index}",
        'local-hostname': f"{node_type}{node_index}",
    }
    meta_out = yaml.dump(meta)
    outfile('meta-data', meta_out)
    base = os.path.normpath(os.path.dirname(__file__))
    with open(f"{base}/setup.sh") as setup_file:
        setup_contents = setup_file.read()
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
                'ssh_authorized_keys': cfg['ssh_authorized_keys'],
                'sudo': 'ALL=(ALL) NOPASSWD:ALL'
            }
        ],
        'package_update': True,
        'package_upgrade': True,
        'write_files': [
            {
                'path': '/usr/bin/setup.sh',
                'content': str(setup_contents),
                'permissions': '0744',
                'owner': 'root:root'
            }
        ],
        # 'runcmd': [
        #     ['/usr/bin/setup.sh']
        # ]
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
    parser.add_argument('-t', '--type',
                        choices=['control', 'worker', 'xtra'],
                        help="Node type", default="worker")
    parser.add_argument('-d', '--dest', help="Destination - where to copy cloud-init files", required=True)
    parser.add_argument('--dry-run', help="Dry-run, do not actually write to destination but show what we would write",
                        action='store_true', default=False)
    args = parser.parse_args()
    main(args.type, int(args.index), args.dest, args.dry_run)
