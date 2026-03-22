pkgName=com.byyoung.setting
filesPath=/data/data/${pkgName}/files
localPath=/data/local
moduleId=WorkSettingPro

export PATH=${filesPath}/term/:$PATH
zip=${filesPath}/term/zip
unzip=${filesPath}/term/unzip

function busybox_install() {
  install_path=$filesPath/busybox
  systemBinPath=/system/bin
  busyboxPath=${install_path}/busybox
  chmod 0755 "${busyboxPath}"
  ${busyboxPath} --install -s ${install_path}
  for file in $(ls ${systemBinPath}); do
    if [ "$file" != "unzip" ] && [ "$file" != "busybox" ] && [ "$file" != "tar" ]; then
      [ ! -L ${systemBinPath}/$file ] && rm -rf $install_path/$file 2>/dev/null
    fi

  done

}
if [ -d $localPath ]; then
  cachePath=${localPath}/cache/$(date "+%Y%m%d%H%M%S")
else
  cachePath=/data/data/${pkgName}/cache/$(date "+%Y%m%d%H%M%S")
fi

if [ ! -f ${filesPath}/term/unzip ] && [ -f ${filesPath}/term/busybox ]; then
  echo "busybox被其他软件当垃圾给清理掉了，正在尝试随便找一个凑合使用，您可重置资源包解决此问题！" 1>&2
  busybox_install
  chmod -R 0777 ${filesPath}/busybox/*
fi

echo "数据初始化中！"
