#!/bin/sh
[ -f /etc/profile.d/RkEnv.sh ] && . /etc/profile.d/RkEnv.sh
export LD_LIBRARY_PATH="/run/openhd/current/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
mkdir -p /var/log /var/run
# Boot invokes this script too, but SysUtils exclusively owns automatic startup.
# For a manual start use: OPENHD_SYSUTILS_START=1 /etc/init.d/S99openhd start
if [ "$1" = start ] && [ "${OPENHD_SYSUTILS_START:-0}" != 1 ]; then
    echo "OpenHD startup is managed by SysUtils"
    exit 0
fi
LOG_FILE=/var/log/openhd.log
PID_FILE=/var/run/openhd.pid
COMMAND=/run/openhd/current/usr/bin/openhd
[ -x "$COMMAND" ] || COMMAND=/usr/bin/openhd
prepare_start() {
    if [ -f /oem/usr/ko/insmod_ko.sh ]; then
        /bin/sh /oem/usr/ko/insmod_ko.sh >> "$LOG_FILE" 2>&1
    fi
    if [ -f /config/mis5001_CMK-OT2115-PC1_30IRC-F16.json ]; then
        cp /config/mis5001_CMK-OT2115-PC1_30IRC-F16.json /oem/usr/share/iqfiles/ || return 1
    fi
    return 0
}

running() {
    [ -r "$PID_FILE" ] || return 1
    PID=$(cat "$PID_FILE")
    case "$PID" in ''|*[!0-9]*) return 1 ;; esac
    [ "$PID" -gt 1 ] && kill -0 "$PID" 2>/dev/null &&
        [ "$(readlink -f /proc/$PID/exe)" = "$(readlink -f "$COMMAND")" ]
}
stop_service() {
    if running; then
        kill "$PID" || return 1
        count=0
        while running; do
            count=$((count + 1))
            [ "$count" -lt 10 ] || { echo "Timed out stopping $COMMAND" >&2; return 1; }
            sleep 1
        done
    fi
    rm -f "$PID_FILE"
}
start_service() {
    running && return 0
    [ -x "$COMMAND" ] || { echo "Missing executable: $COMMAND" >&2; return 1; }
    prepare_start || return 1
    nohup "$COMMAND" >> "$LOG_FILE" 2>&1 < /dev/null &
    echo $! > "$PID_FILE"
    sleep 1
    if ! running; then
        echo "Failed to start $COMMAND; see $LOG_FILE" >&2
        rm -f "$PID_FILE"
        return 1
    fi
    echo "Started $COMMAND (PID $PID)"
}
case "$1" in
    start) start_service ;;
    stop) stop_service ;;
    restart) stop_service && start_service ;;
    status) running ;;
    *) echo "Usage: $0 {start|stop|restart|status}" >&2; exit 1 ;;
esac
