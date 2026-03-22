export PATH=/system/bin:$PATH
oldPath="$1" newPath="$2"

if [ "$oldPath" = "" ] || [ "$newPath" = "" ]; then
  echo "请填入路径"
  exit 128
elif [ ! -f "$oldPath" ]; then
  echo "要复制的文件已丢失"
  exit 128
fi

dir=$(dirname "$newPath")

function enable_root() {
  mount -o remount,rw /system

  if [ ! -d "$dir" ]; then
    mkdir -p "$dir"
  fi
  cp -p -a -R ${oldPath} ${newPath}

}

function enable_magisk() {

  magiskdir=${modulePath}${dir}
  if [ ! -d "$magiskdir" ]; then
    mkdir -p "$magiskdir"
  else
    echo "该Magisk模块目录已经存在，直接复制文件！"
  fi
  cp -p -a -R ${oldPath} ${modulePath}${newPath}

}

echo "部分设置重启生效"

source /data/data/com.byyoung.setting/files/system/newbin/main_script.sh
