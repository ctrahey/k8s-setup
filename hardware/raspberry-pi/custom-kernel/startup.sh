KERNELPKG=$(apt-cache search linux-image-5.4.0 | grep raspi | sort | tail -n 1 | awk '{print $1}')
echo "deb-src http://us-west-2.ec2.ports.ubuntu.com/ubuntu-ports/ focal main restricted" >> /etc/apt/sources.list
echo "deb-src http://us-west-2.ec2.ports.ubuntu.com/ubuntu-ports/ focal-updates main restricted" >> /etc/apt/sources.list
sudo apt-get update
sudo apt-get install -y libncurses-dev gawk flex bison openssl libssl-dev dkms libelf-dev libudev-dev libpci-dev libiberty-dev autoconf git fakeroot
sudo apt-get -y build-dep linux $KERNELPKG
cd /home/ubuntu
apt-get -y source $KERNELPKG
cd linux-raspi-5.4.0/
chmod a+x debian/rules debian/scripts/* debian/scripts/misc/*


vim debian.raspi/changelog
LANG=C fakeroot debian/rules editconfigs
LANG=C fakeroot debian/rules clean
time LANG=C fakeroot debian/rules binary-headers binary-arch skipmodule=true