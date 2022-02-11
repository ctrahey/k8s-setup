#!/bin/bash
iptables -I INPUT -i publx -d 224.0.0.0/8 -p vrrp -j ACCEPT
iptables -I OUTPUT -o publx -d 224.0.0.0/8 -p vrrp -j ACCEPT
