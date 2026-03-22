busybox=/sbin/.magisk/busybox/busybox
LOG=/data/data/com.byyoung.setting/cache/.boost.log

if [ -f /sbin/.magisk/busybox/busybox ]; then
  busybox=/sbin/.magisk/busybox/busybox
elif [ -f /data/adb/magisk/busybox ]; then
  busybox=/data/adb/magisk/busybox
elif [ -f /system/xbin/busybox ]; then
  busybox=/system/xbin/busybox
elif [ -f /system/bin/busybox ]; then
  busybox=/system/bin/busybox
elif
  [ -f /data/data/com.byyoung.setting/files/term/busybox ]
then
  busybox=/data/data/com.byyoung.setting/files/term/busybox

else

  echo "没有检查到busybox!"
  exit 0
fi

#$busybox mount -o remount,rw /
#$busybox mount -o remount,rw rootfs
#$busybox mount -o remount,rw /system

$busybox clear
$busybox echo ""
$busybox free | $busybox awk '/Mem/{print ">>>...Memory Before Boosting: "$4/1024" MB";}'
$busybox sleep 1
$busybox echo ""
$busybox echo "Dropping cache"
$busybox sync
$busybox sleep 1
$busybox sysctl -w vm.drop_caches=3
$busybox sleep 1
dc=/proc/sys/vm/drop_caches
dc_v=$(cat $dc) 2>/dev/null
if [ "$dc_v" -gt 1 ]; then
  $busybox sysctl -w vm.drop_caches=1
fi
$busybox echo ""
$busybox echo "BOOSTED!!!"
$busybox echo ""
$busybox free | $busybox awk '/Mem/{print ">>>...Memory After Boosting : "$4/1024" MB";}'
$busybox echo "RAM boost $(date +"%m-%d-%Y %H:%M:%S")" | $busybox tee -a $LOG
