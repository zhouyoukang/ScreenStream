#MagiskPath=$(magisk --path)
filePath="$1"
magiskBusybox=$(magisk --path)/.magisk/busybox
export PATH=${magiskBusybox}:$PATH

echo "-------------"
echo "正在刷入模块路径：${filePath}"
echo "-------------"

if [ "$filePath" = "" ]; then
  echo "传入路径与输出路径有误"
  exit 128
elif [ ! -f "$filePath" ]; then
  echo "要刷入的模块已丢失：$filePath"
  exit 128
fi
echo "正在解压模块获取核心文件！"

source /data/data/com.byyoung.setting/files/system/newbin/main_export.sh

magiskVersion=$(magisk -v)
if [ "$magiskVersion" == "" ]; then
  echo "您未安装Magisk，自动终止安装！"
  exit 128
fi

mkdir -p ${cachePath}/META-INF/com/google/android
tempModule=${cachePath}/tempModule.zip
cp -p -a -R "$filePath" "$tempModule"

$unzip -o "$tempModule" 'META-INF/com/google/android/*' -d ${cachePath}
if [ "$?" -eq 0 ]; then
  echo "读取核心文件成功，开始刷入！"
  updateBinaryPath=${cachePath}/META-INF/com/google/android/update-binary
  else
  echo "读取核心文件失败，请重置资源包试试，Magisk20.2以下模块刷入请切换兼容模式！"
  exit 128
fi

chmod -R 0777 "${updateBinaryPath}"

echo "正在刷入模块"

sh "${updateBinaryPath}" dummy 1 "$tempModule"
flashCode=$?
if [ "$flashCode" -eq 0 ]; then
  echo "√√√，模块刷入成功，错误信息仅供模块开发者参考！"
  rm -rf "${cachePath}"

else

  if [ $flashCode -eq 1 ]; then
    magisk --install-module "$tempModule"
    if [ "$?" -eq 0 ]; then
      echo "√√√，模块刷入成功（调用magisk的Api），错误信息仅供模块开发者参考！"
      rm -rf "${cachePath}"
    else
      echo "模块刷入失败，错误信息可提供模块开发者参考！"
      rm -rf "${cachePath}"
      exit 128
    fi
  else
    echo "模块刷入失败，错误信息可提供模块开发者参考！"
    rm -rf ${cachePath}
    exit $flashCode
  fi

fi
