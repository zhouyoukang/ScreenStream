#MagiskPath=$(magisk --path)
systemuiPath=/system/media/theme/default/com.android.systemui
#名称和值
key="$@"
#0恢复默认状态栏，-1后台圆角
# 1:5个快捷
# 2:6个快捷方式

if [ "$key" == "" ]; then
  echo "传入参数出错，执行结束"
  exit 128
fi

function enable_root() {
  mount -o remount,rw /system
  mkdir -p /system/media/theme/default
  if [ "$key" -eq 0 ]; then

    rm -rf ${systemuiPath}

    echo "正在以Root修改方式修改MIUI状态设置，还原状态栏"

  elif [ "$key" -eq -1 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/backstage/* ${systemuiPath}

    echo "正在以Root修改方式修改MIUI状态设置，设置并开启后台圆角"

  elif [ "$key" -eq 1 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/buju/5x4/* ${systemuiPath}

    echo "正在以Root修改方式修改MIUI时钟设置，设置5个快捷方式"

  elif [ "$key" -eq 2 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/buju/6x4/* ${systemuiPath}

    echo "正在以Root修改方式修改MIUI时钟设置，设置6个快捷方式"

  else

    echo "未知动作，执行结束！"

  fi
  killall com.android.systemui
}

function enable_magisk() {
  mkdir -p ${modulePath}/system/media/theme/default
  if [ "$key" -eq 0 ]; then

    rm -rf ${modulePath}${systemuiPath}

    echo "正在以Magisk模块修改方式修改MIUI状态设置，还原状态栏"

  elif [ "$key" -eq -1 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/backstage/* ${modulePath}${systemuiPath}

    echo "正在以Magisk模块修改方式修改MIUI状态设置，设置并开启后台圆角"

  elif [ "$key" -eq 1 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/buju/5x4/* ${modulePath}${systemuiPath}

    echo "正在以Magisk模块修改方式修改MIUI时钟设置，设置5个快捷方式"

  elif [ "$key" -eq 2 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/buju/6x4/* ${modulePath}${systemuiPath}

    echo "正在以Magisk模块修改方式修改MIUI时钟设置，设置6个快捷方式"

  else

    echo "未知动作，执行结束！"

  fi
  killall com.android.systemui

}

source /data/data/com.byyoung.setting/files/system/newbin/main_script.sh
