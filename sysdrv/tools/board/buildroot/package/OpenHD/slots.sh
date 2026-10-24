#!/bin/sh
# Selection runs before either application. A failed/unconfirmed trial reverts
# on the following boot. Explicit confirmation requires a live bench check.
case "$1" in
    start)
        mkdir -p /run/openhd
        [ -e /run/openhd/boot-selected ] && exit 0
        if /usr/sbin/openhd-pico-update boot; then
            touch /run/openhd/boot-selected
            exit 0
        fi
        echo "Pico slots unavailable; using factory applications" >&2
        ln -sfn / /run/openhd/current
        ;;
    stop) ;;
    *) exit 1 ;;
esac
