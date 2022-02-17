#!/usr/bin/env bash


DEV=/dev/sda
DEST=/tmp/newimage.img
LOOPDEVPLACEHOLDER=--LOOPDEVNAME--




BLKSZ=$(blockdev --getss $DEV)
MIN_UNUSED=$(( ((1024*1024*256)) / $BLKSZ)) # Only change partition size if it has more than 256 MB free space
PARTITION_PADDING=131072 # Always add one padding block when resizing.
sfdisk -d /dev/sda > /tmp/original_fdisk.txt
cat << EOF > /tmp/new.sfdisk
label: dos
label-id: 0xf66f0719
device: $LOOPDEVPLACEHOLDER
unit: sectors

EOF

# add partitions to the fdisk file
CURRENT_OFFSET=2048 # room for the MBR itself, 1MB
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
    ((THIS_SIZE += PARTITION_PADDING))
  else
    THIS_SIZE=$ORIG_SIZE
  fi
  echo ${LOOPDEVPLACEHOLDER}p${CURRENT_INDEX} : start= $CURRENT_OFFSET, size= $THIS_SIZE, $ORIG_LINE_END >> /tmp/new.sfdisk
  ((TOTAL_SIZE += $THIS_SIZE))
  ((CURRENT_OFFSET += $THIS_SIZE))
  ((CURRENT_INDEX += 1))
done
# TOTAL_SIZE is number of blocks. Here calculate total bytes
TOTAL_BYTES=$(($TOTAL_SIZE * $BLKSZ))
# and derive MB by dividing by (1024*1024)
TOTAL_MB=$(($TOTAL_BYTES / 1048576))
# Pad size for MBR - I think it is only 512 Bytes, so this is slightly generous
((TOTAL_MB += 2))

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
cat /tmp/new.sfdisk | sed -E "s/--LOOPDEVNAME--/$LOOPDEV/" | sfdisk $LOOPDEV

CURRENT_INDEX=1
for DVC in $(ls -f /dev/sda[0-9] | xargs -n 1)
do
  DVCHASH=D$(echo $DVC | md5sum | awk '{print $1}')
  # @TODO Make Filesystems first!!
  TYPE=$(lsblk -o FSTYPE $DVC | tail -n 1)
  echo running mkfs.$TYPE ${LOOPDEV}p${CURRENT_INDEX}
  mkfs.$TYPE ${LOOPDEV}p${CURRENT_INDEX}
  umount -q /mnt/source-$DVCHASH
  mkdir -p /mnt/source-$DVCHASH
  mount -o ro --source $DVC --target /mnt/source-$DVCHASH
  umount -q /mnt/target-$DVCHASH
  mkdir -p /mnt/target-$DVCHASH
  mount -o rw --source ${LOOPDEV}p${CURRENT_INDEX} --target /mnt/target-$DVCHASH
  echo copying files from $DVC to ${LOOPDEV}p${CURRENT_INDEX}
  echo which is /mnt/source-$DVCHASH to /mnt/target-$DVCHASH
  rsync -a /mnt/source-$DVCHASH/* /mnt/target-$DVCHASH/
  ((CURRENT_INDEX += 1))
done


CURRENT_INDEX=1
for DVC in $(ls -f /dev/sda[0-9] | xargs -n 1)
do
  DVCHASH=D$(echo $DVC | md5sum | awk '{print $1}')
  umount -q /mnt/source-$DVCHASH
  umount -q /mnt/target-$DVCHASH
  losetup -d $LOOPDEV
done
rm /tmp/newimage.img
