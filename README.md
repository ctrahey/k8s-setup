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

```commandline
./configure-sdcard.py -d /Volumes/system-boot -t worker -i 1
```
