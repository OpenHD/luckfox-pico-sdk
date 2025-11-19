#!/bin/bash
export PATH=$PATH:/usr/sbin/
rm ./output/image/ohd_config.img
truncate --size 256M ./output/image/ohd_config.img
mkfs.vfat -F 32 ./output/image/ohd_config.img
mkdir output/mnt
export MTOOLS_SKIP_CHECK=1
mmd   -i ./output/image/ohd_config.img ::/openhd
echo -n "" | mcopy -i ./output/image/ohd_config.img - ::/config.txt
echo -n "" | mcopy -i ./output/image/ohd_config.img - ::/openhd/rv1106.txt
echo -n "" | mcopy -i ./output/image/ohd_config.img - ::/openhd/air.txt
resize2fs ./output/image/rootfs.img 1G
genimage --config genimage.cfg --inputpath ./output/image --outputpath ./output/genimage --rootpath ./rootfs-empty
