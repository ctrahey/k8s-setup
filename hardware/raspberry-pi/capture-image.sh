#!/usr/bin/env bash


DEV=/dev/sda
DEST=/tmp/newimage.img
LOOPDEVPLACEHOLDER=--LOOPDEVNAME--




BLKSZ=$(blockdev --getss $DEV)
MIN_UNUSED=$(( ((1024*1024*256)) / $BLKSZ)) # Only change partition size if it has more than 256 MB free space
PARTITION_PADDING_PCT=15 # some padding for misc. filesystem overhead
sfdisk -d /dev/sda > /tmp/original_fdisk.txt
cat << EOF > /tmp/new.sfdisk
label: dos
label-id: 0xf66f0719
device: $LOOPDEVPLACEHOLDER
unit: sectors

EOF

# add partitions to the fdisk file
TOTAL_SIZE=2048
CURRENT_INDEX=1
for DVC in $(ls -f /dev/sda[0-9] | xargs -n 1)
do
  DVCHASH=D$(echo $DVC | md5sum | awk '{print $1}')
  umount -q /mnt/$DVCHASH
  mkdir -p /mnt/$DVCHASH
  mount -o ro --source $DVC --target /mnt/$DVCHASH
  echo "Checking usage of $DVC. This may take a moment"
  THIS_SIZE=$(du -s -B $BLKSZ /mnt/$DVCHASH | awk '{print $1}')
  ORIG_LINE=$(cat /tmp/original_fdisk.txt | grep $DVC)
  ORIG_SIZE=$(echo ${ORIG_LINE##*size=} | cut -d ',' --f 1)
  ORIG_LINE_END=$(echo ${ORIG_LINE##*size=} | cut -d ',' --f 2-)

  # If this size is more than MIN_UNUSED blocks less than the size in the partition table, update the size
  THIS_GAP=$((ORIG_SIZE - THIS_SIZE))
  if [ "$THIS_GAP" -gt "$MIN_UNUSED" ]; then
    echo "Resizing partition for $DVC. Basis: $THIS_SIZE"
    THIS_SIZE=$(($THIS_SIZE * (100+$PARTITION_PADDING_PCT) / 100))
    echo "Final padded size: $THIS_SIZE"
  else
    THIS_SIZE=$ORIG_SIZE
  fi
  # @TODO we need to copy labels (possibly later in the script) such as system-boot and writable.
  echo ${LOOPDEVPLACEHOLDER}p${CURRENT_INDEX} : size= $THIS_SIZE, $ORIG_LINE_END >> /tmp/new.sfdisk
  ((TOTAL_SIZE += $THIS_SIZE))
  ((CURRENT_INDEX += 1))
done
# TOTAL_SIZE is number of blocks. Here calculate total bytes
TOTAL_BYTES=$(($TOTAL_SIZE * $BLKSZ))
# and derive MB by dividing by (1024*1024)
TOTAL_MB=$(($TOTAL_BYTES / 1048576))
# Pad size for MBR - I think it is only 512 Bytes, so this is slightly generous
((TOTAL_MB += 256))

# @todo confirm space is available on local drive for this image.
# AVAIL=$(df --output=avail . | tail -n 1)
# etc...

echo Running: "dd if=/dev/zero of=/tmp/newimage.img bs=1048576 count=$TOTAL_MB"
echo "this may take a moment"
dd if=/dev/zero of=$DEST bs=1048576 count=$TOTAL_MB
ls -l /tmp/newimage.img
LOOPDEV=$(losetup --show -fP /tmp/newimage.img)
echo We have a device at $LOOPDEV attached to /tmp/newimage.img ready for formatting
# @todo use placeholder for entire device path
cat /tmp/new.sfdisk | sed -e "s~--LOOPDEVNAME--~$LOOPDEV~" | sfdisk $LOOPDEV

CURRENT_INDEX=1
for DVC in $(ls -f /dev/sda[0-9] | xargs -n 1)
do
  DVCHASH=D$(echo $DVC | md5sum | awk '{print $1}')
  # @TODO Make Filesystems first!!
  TYPE=$(lsblk -o FSTYPE $DVC | tail -n 1)
  echo running mkfs.$TYPE ${LOOPDEV}p${CURRENT_INDEX}
  if [[ "$TYPE" = "ext4" ]]; then
    echo ext4 detected, so trying without journal
    mkfs.$TYPE -O ^has_journal ${LOOPDEV}p${CURRENT_INDEX}
  else
    echo not ext4, so mkfs with no options
    mkfs.$TYPE ${LOOPDEV}p${CURRENT_INDEX}
  fi
  umount -q /mnt/source-$DVCHASH
  mkdir -p /mnt/source-$DVCHASH
  mount -o ro --source $DVC --target /mnt/source-$DVCHASH
  umount -q /mnt/target-$DVCHASH
  mkdir -p /mnt/target-$DVCHASH
  mount -o rw --source ${LOOPDEV}p${CURRENT_INDEX} --target /mnt/target-$DVCHASH
  echo copying files from $DVC to ${LOOPDEV}p${CURRENT_INDEX}
  echo which is /mnt/source-$DVCHASH to /mnt/target-$DVCHASH
  rsync -a --info=progress2 /mnt/source-$DVCHASH/* /mnt/target-$DVCHASH/
  ((CURRENT_INDEX += 1))
done


CURRENT_INDEX=1
for DVC in $(ls -f /dev/sda[0-9] | xargs -n 1)
do
  DVCHASH=D$(echo $DVC | md5sum | awk '{print $1}')
  umount -q /mnt/source-$DVCHASH
  umount -q /mnt/target-$DVCHASH
done
losetup -d $LOOPDEV
rm /tmp/newimage.img
