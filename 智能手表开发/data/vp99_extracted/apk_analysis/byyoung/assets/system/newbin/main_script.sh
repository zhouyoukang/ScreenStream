pkgName=com.byyoung.setting
filesPath=/data/data/${pkgName}/files
export PATH=${filesPath}/term:$PATH

moduleId=WorkSettingPro
liteVersion=$(magisk -v | grep 'lite') &>/dev/null

if [[ -n "$liteVersion" ]]; then
  modulePath=/data/adb/lite_modules/${moduleId}
  if [ ! -d $modulePath ]; then
    echo "当前magisk_'$liteVersion'不支持的操作！" 1>&2
    exit 128
  fi

elif
  [[ -w /sbin/.magisk/img/${moduleId} ]]
then
  modulePath=/sbin/.magisk/img/${moduleId}
elif [[ -w /sbin/.core/img/${moduleId} ]]; then
  modulePath=/sbin/.core/img/${moduleId}
elif [[ -w /sbin/.magisk/modules/${moduleId} ]]; then
  modulePath=/sbin/.magisk/modules/${moduleId}
elif [[ -w /data/adb/modules/${moduleId} ]]; then
  modulePath=/data/adb/modules/${moduleId}
elif [[ -w /data/adb/ksu/modules/${moduleId} ]]; then
  modulePath=/data/adb/ksu/modules/${moduleId}
#elif [[ -d ${MagiskPath}/modules/${moduleId} ]]; then

elif [[ -f ${filesPath}/UseRoot ]]; then

  echo "没有检查到应用模块!正在以Root权限方式修改"
  echo ""

  enable_root
  exit 0

else

  echo "没有检查到应用模块!也没有设置允许Root权限修改，执行结束" 1>&2
  echo ""

  exit 128

fi

echo "检查到模块!正在以Magisk方式修改！"
echo ""

enable_magisk
exit 0
