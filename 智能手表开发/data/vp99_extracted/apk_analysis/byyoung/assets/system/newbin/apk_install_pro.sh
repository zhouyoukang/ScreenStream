#应用路径
source /data/data/com.byyoung.setting/files/system/newbin/main_export.sh
export PATH=${filesPath}/term/:$PATH
#apkPath=应用路径
#suffix=指定格式
#userId=多用户id
#installer=安装调用者
#degraded=尝试降级安装

apkPath="$1"
if [ -n "$2" ]; then
  suffix="$2"
else
  suffix=${apkPath##*.}
fi
userId="$3"
installer="$4"

fileName=$(basename "$apkPath")
if [ "$apkPath" = "" ] || [ "$suffix" = "" ]; then
  echo "传入路径与获取文件格式有误"
  exit 128

elif [ ! -f "$apkPath" ]; then
  echo "待安装的路径不存在：$apkPath"
  exit 128

fi

function install_apk() {
  API=$(getprop ro.build.version.sdk)
  if [ "$API" -ge 28 ]; then
    apkSize=$(wc -c <"$apkPath")
    installMsg=$(cat "$apkPath" | pm install -i "$installer" -r -d -t --user "$userId" -S "$apkSize")
  else
    pm install -i "$installer" -r -d -t --user "$userId" "$apkPath" 1>/dev/null

  fi

  if [ "$?" -eq 0 ]; then
    echo "${fileName}安装应用完成！"
  elif [[ $installMsg == *"INSTALL_FAILED_DEPRECATED_SDK_VERSION"* ]]; then
    echo "SDK<23，正在使用低版本兼容安装！"
    apkSize=$(wc -c <"$apkPath")
    cat "$apkPath" | pm install --bypass-low-target-sdk-block -i "$installer" -r -d -t --user "$userId" -S "$apkSize"
  elif [[ $installMsg == *"INSTALL_FAILED_HYPEROS_ISOLATION_VIOLATION"* ]]; then
    echo "正在尝试绕过HyperOS禁用更新系统应用模式！"
    apkSize=$(wc -c <"$apkPath")
    cat "$apkPath" | pm install -i "android" -r -d -t --user "$userId" -S "$apkSize"

  else
    mkdir -p ${cachePath}
    cp -p -a -R "$apkPath" ${cachePath}/temp.apk
    chmod 0777 ${cachePath}/temp.apk
    pm install -i "$installer" -r -d -t --user "$userId" ${cachePath}/temp.apk 1>&2
    if [ "$?" -eq 0 ]; then
      echo "${fileName}安装应用完成！"
      rm -rf ${defaultPath}

    else

      errorCode="$?"
      echo "${fileName}安装应用失败！"
      rm -rf ${cachePath}
      exit $errorCode
    fi
  fi

}

function install_apex() {
  apkSize=$(wc -c <"$apkPath")
  cat "$apkPath" | pm install -i "$installer" -r -d -t --user "$userId" -S "$apkSize" --apex 1>&2
  if [ "$?" -eq 0 ]; then
    echo "${fileName}安装应用完成！"
  else
    errorCode="$?"
    echo "${fileName}安装应用失败！"
    exit $errorCode
  fi

}

function install_others() {
  mkdir -p ${cachePath}
  $unzip -o "$apkPath" -d ${cachePath}
  if [ "$?" -eq 0 ]; then
    echo "解压文件成功，正在搜索子应用！"
  else
    echo "解压应用文件出错了！自动终止安装！"
    rm -rf ${cachePath}

    exit 128
  fi
  session=$(pm install-create -r -t -i "$installer" -d --user "$userId")
  session_id=$(echo "$session" | sed -n 's/.*\[\(.*\)\]/\1/p')
  exec
  cd "${cachePath}" || exit
  for sonFile in $(ls "${cachePath}"); do
    chmod 0777 "${sonFile}"

    if [ -d "${sonFile}/data" ]; then
      cp -p -a -R "${sonFile}"/data/* /sdcard/Android/data
      echo "复制存档数据"

    elif [ -d "${sonFile}/obb" ]; then
      cp -p -a -R "${sonFile}"/obb/* /sdcard/Android/obb
      echo "复制OBB数据包"
    elif [ -f "${sonFile}" ]; then
      sonSuffix=${sonFile##*.}
      if [ "$sonSuffix" == "apk" ]; then
        sonSize=$(wc -c <"$sonFile")
        cat "$sonFile" | pm install-write -S "$sonSize" "$session_id" "$sonFile" 1>/dev/null
        echo "安装子文件：$sonFile"
      fi
    fi
  done
  exec
  echo "开始推送：${fileName}"
  pm install-commit $session_id

  if [ "$?" -eq 0 ]; then
    echo "${fileName}安装应用完成！"
    rm -rf ${cachePath}

  else

    errorCode="$?"
    echo "${fileName}安装应用失败！"
    rm -rf ${cachePath}

    exit $errorCode
  fi

}

if [ "$suffix" == "apk" ]; then

  install_apk

elif [ "$suffix" == "apex" ]; then
  install_apex
else
  $unzip -l "$apkPath" | grep AndroidManifest.xml
  if [ "$?" -eq 0 ]; then
    echo "这货就是个apk！还是以apk方式安装吧！"
    install_apk
  else
    install_others
  fi

fi
