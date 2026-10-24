#!/bin/sh
[ -f /etc/profile.d/RkEnv.sh ] && . /etc/profile.d/RkEnv.sh

LOG_FILE="/var/log/openhd-sys-utils.log"
COMMAND="/run/openhd/current/usr/bin/openhd_sys_utils"
[ -x "$COMMAND" ] || COMMAND="/usr/bin/openhd_sys_utils"
export LD_LIBRARY_PATH="/run/openhd/current/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
PID_FILE="/var/run/openhd-sys-utils.pid"

start_openhd_sysutils() {
    echo "Starting OpenHD-SysUtils..." | tee -a "$LOG_FILE"

    stop_openhd_sysutils  # Ensure no previous instance is running

    # Run OpenHD-SysUtils in the background
    nohup $COMMAND >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    echo "OpenHD-SysUtils started successfully with PID $(cat $PID_FILE)!" | tee -a "$LOG_FILE"
}

stop_openhd_sysutils() {
    echo "Stopping OpenHD-SysUtils..." | tee -a "$LOG_FILE"

    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill "$PID" 2>/dev/null; then
            echo "OpenHD-SysUtils stopped (PID: $PID)." | tee -a "$LOG_FILE"
        else
            echo "Failed to stop OpenHD-SysUtils. Process might not exist." | tee -a "$LOG_FILE"
        fi
        rm -f "$PID_FILE"
    else
        echo "OpenHD-SysUtils is not running." | tee -a "$LOG_FILE"
    fi
}

restart_openhd_sysutils() {
    stop_openhd_sysutils
    start_openhd_sysutils
}

status_openhd_sysutils() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "OpenHD-SysUtils is running (PID: $PID)." | tee -a "$LOG_FILE"
            exit 0
        else
            echo "OpenHD-SysUtils is not running, but PID file exists." | tee -a "$LOG_FILE"
            exit 1
        fi
    else
        echo "OpenHD-SysUtils is not running." | tee -a "$LOG_FILE"
        exit 1
    fi
}

case "$1" in
    start)
        start_openhd_sysutils
        ;;
    stop)
        stop_openhd_sysutils
        ;;
    restart)
        restart_openhd_sysutils
        ;;
    status)
        status_openhd_sysutils
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}" | tee -a "$LOG_FILE"
        exit 1
        ;;
esac

exit 0
