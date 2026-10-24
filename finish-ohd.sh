#!/bin/bash
set -euo pipefail
export PATH=$PATH:/usr/sbin/
test -s ./output/image/rootfs.img
mkdir -p output/mnt rootfs-empty
rm -f ./output/image/ohd_config.img
truncate --size 256M ./output/image/ohd_config.img
mkfs.vfat -F 32 -n OPENHD ./output/image/ohd_config.img
export MTOOLS_SKIP_CHECK=1
mmd   -i ./output/image/ohd_config.img ::/openhd
echo -n "" | mcopy -i ./output/image/ohd_config.img - ::/config.txt
echo -n "" | mcopy -i ./output/image/ohd_config.img - ::/openhd/rv1106.txt
echo -n "" | mcopy -i ./output/image/ohd_config.img - ::/openhd/air.txt
truncate --size 256M ./output/image/swap.img
mkswap -L SWAP ./output/image/swap.img
resize2fs ./output/image/rootfs.img 1G
genimage --config genimage.cfg --inputpath ./output/image --outputpath ./output/genimage --rootpath ./rootfs-empty
