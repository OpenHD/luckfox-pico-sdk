#!/bin/bash
rm ./output/image/ohd_config.img
truncate --size 256M ./output/image/ohd_config.img
mkfs.vfat -F 32 ./output/image/ohd_config.img
mkdir output/mnt
sudo mount ./output/image/ohd_config.img output/mnt
sudo touch output/mnt/config.txt
sudo mkdir output/mnt/openhd
sudo touch output/mnt/openhd/rv1106.txt
sudo umount output/mnt
resize2fs ./output/image/rootfs.img 1G
genimage --config genimage.cfg --inputpath ./output/image --outputpath ./output/genimage --rootpath ./rootfs-empty
