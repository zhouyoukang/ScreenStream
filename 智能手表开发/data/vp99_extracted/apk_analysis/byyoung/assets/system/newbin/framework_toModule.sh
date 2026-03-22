source /data/data/com.byyoung.setting/files/system/newbin/main_export.sh
filePath=/sdcard/Documents/advanced/过渡动画模块

key="$@"

if [ "$key" = "" ]; then

  echo "请选择要制作的模块类型"
  exit 128

fi

mkdir -p ${cachePath}/system/framework
mkdir -p ${filePath}

echo "该功能不一定适配所有机型，请谨慎使用，不会救砖请不要作死使用此功能"
echo "该功能不一定适配所有机型，请谨慎使用，不会救砖请不要作死使用此功能"
echo "该功能不一定适配所有机型，请谨慎使用，不会救砖请不要作死使用此功能"

cp -p -a -R ${filesPath}/system/xbin/byyoung/moban/framework.zip ${cachePath}/framework.zip

echo "复制并修改当前framework-res.apk到缓存目录中"

cp -p -a -R /system/framework/framework-res.apk ${cachePath}/system/framework/framework-res.apk

if [ ! -d ${filesPath}/framework/$key ]; then
  echo "过渡动画文件已丢失！"
  exit 128

fi

cd ${filesPath}/framework/$key

$zip -q -r ${cachePath}/system/framework/framework-res.apk res
echo "修改过渡动画完成，正在输出模块"

cd ${cachePath}
$zip -q -r ${cachePath}/framework.zip system
echo "打包模块完成，正在清理缓存！"

mv ${cachePath}/framework.zip ${filePath}/framework_${key}.zip

#/删除垃圾

rm -rf ${cachePath}
echo "模块制作完成，输出路径："
echo "${filePath}/framework_${key}.zip"
