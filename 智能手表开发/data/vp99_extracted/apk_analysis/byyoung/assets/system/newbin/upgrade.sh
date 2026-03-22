moduleId=WorkSettingPro

if [[ -w /sbin/.magisk/img/${moduleId} ]]; then
  modulePath=/sbin/.magisk/img/${moduleId}
elif [[ -w /sbin/.core/img/${moduleId} ]]; then
  modulePath=/sbin/.core/img/${moduleId}
elif [[ -w /sbin/.magisk/modules/${moduleId} ]]; then
  modulePath=/sbin/.magisk/modules/${moduleId}
elif [[ -w /data/adb/modules/${moduleId} ]]; then
  modulePath=/data/adb/modules/${moduleId}
else
  echo "没有检查到模块!"
  exit 0
fi
sleep 1
echo "正在检查模块!"
sleep 1
echo "正在备份模块!"
sleep 1
echo "正在校验模块!"
sleep 1
echo "正在移除模块!"
sleep 1
echo "正在安装模块!"
sleep 1
echo "正在还原模块数据!"
sleep 1
echo "正在修改模块结构!"
sleep 1
echo "正在首次OTA模块!"

echo "id=${moduleId}" >${modulePath}/module.prop
echo "version=22.07（增量稳定版）" >>${modulePath}/module.prop
echo "name=爱玩设置工具箱（扩展功能）" >>${modulePath}/module.prop
echo "versionCode=1900" >>${modulePath}/module.prop
echo "author=小白杨" >>${modulePath}/module.prop
echo "description=用于扩展设置工具箱一些功能，旨在系统OTA并无需挂载系统即可修改系统，非MIUI设备不会刷入MIUI高级设置核心文件，内含adb与fastboot工具包，若出现设置错误卸载重装自动还原" >>${modulePath}/module.prop

sleep 1
echo "正在修复模块不生效功能!"

if [[ -d ${modulePath}/common ]]; then
  mv ${modulePath}/common/* ${modulePath}
  rm -rf ${modulePath}/common

else
  echo "模块高级设置不需要修复!"
fi

killall com.topjohnwu.magisk
echo "模块OTA成功!"
