# k8s-setup
A set of scripts and resources to setup a bare-metal Kubernetes cluster.

## /hardware
### /hardware/raspberry-pi
#### configure-sdcard.py
A Python script that simplifies the customization of an SD card immediately after imaging.
This is achieved through dynamically building cloud-init scripts.
There is a config.yaml to configure global parameters of your cluster.
Then per-host values are given as script parameters (though it will prompt for password).

@todo There are still portions of the script that hard code values specific to me, and therefore
require touch-ups for sharing (like username created on hosts). These should be factored out to config.yaml 

1. Flash SDCard (e.g. BalenaEtcher). Remove and re-insert to get system-boot mounted
2. copy bootdir_base (custom kernel) (this step could be removed by minting a fresh image)
3. Run this script to customize cloud-init
4. Boot up!
```commandline
./configure-sdcard.py -d /Volumes/system-boot -t worker -i 1
```

# Networking
Networking is specified in terms of three primitives:
1. Hardware Profiles - describes the physical setup of the machine. Specify eth devices & bonds
2. Networks - the Layer 3 definitions of networks, essentially giving a semantic name to a CIDR
3. NetAttachments - a binding between hardware and network. Currently makes every attachment a VLAN.

The choice to make every attachment a VLAN might be reconsidered. It has the disadvantage that the switch
needs to be configured for "tagged" packets for any networking to work (e.g. there will be no un-tagged
traffic from this host). However, there is an advantage that broadcast domains are not explicit-only, which
may simplify reasoning about the network.