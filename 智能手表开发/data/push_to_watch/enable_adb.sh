#!/system/bin/sh
# VP99 ADB Enabler - 通过settings命令开启ADB
settings put global adb_enabled 1
settings put global development_settings_enabled 1
setprop persist.sys.usb.config mtp,adb
setprop sys.usb.config mtp,adb
setprop service.adb.tcp.port 5555
stop adbd
start adbd
echo "ADB enabled on port 5555" > /storage/emulated/0/Download/adb_status.txt