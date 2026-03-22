export PATH=/system/bin:$PATH

key="$@"

if [ "$key" = "" ]; then

  echo "请填入路径"
  exit 128

fi

dir=$(dirname "$key")

function enable_root() {
  mount -o remount,rw /system

  if [ ! -d "$dir" ]; then
    mkdir -p "$dir"
  else
    echo "系统目录已经存在，直接创建文件！"
  fi

  touch ${key}

}

function enable_magisk() {

  magiskdir=${modulePath}${dir}
  if [ ! -d "$magiskdir" ]; then
    mkdir -p "$magiskdir"
  else
    echo "该Magisk模块目录已经存在，直接创建文件！"
  fi

  touch ${modulePath}${key}

}

echo "部分设置重启生效"

source /data/data/com.byyoung.setting/files/system/newbin/main_script.sh
