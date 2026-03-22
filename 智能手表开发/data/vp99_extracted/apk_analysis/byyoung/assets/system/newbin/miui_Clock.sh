#MagiskPath=$(magisk --path)
frameworkPath=/system/media/theme/default/framework-miui-res
#名称和值
key="$@"
#0恢复默认时钟，1时钟农历，2时钟星期，3农历星期
function enable_root() {
  mount -o remount,rw /system
  mkdir -p /system/media/theme/default
  if [ "$key" -eq 0 ]; then

    rm -rf ${frameworkPath}

    echo "正在以Root修改方式修改MIUI时钟设置，还原时钟"

  elif [ "$key" -eq 1 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/shizhong/nongli/* ${frameworkPath}

    echo "正在以Root修改方式修改MIUI时钟设置，显示农历"

  elif [ "$key" -eq 2 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/shizhong/xingqi/* ${frameworkPath}

    echo "正在以Root修改方式修改MIUI时钟设置，显示星期"

  elif [ "$key" -eq 3 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/shizhong/nonglixingqi/* ${frameworkPath}

    echo "正在以Root修改方式修改MIUI时钟设置，显示农历和星期"

  else

    echo "未知动作，执行结束！"

  fi
  killall com.android.systemui
}

function enable_magisk() {
  mkdir -p ${modulePath}/system/media/theme/default

  if [ "$key" -eq 0 ]; then

    rm -rf ${modulePath}${frameworkPath}

    echo "正在以Magisk模块方式修改方式修改MIUI时钟设置，还原时钟"

  elif [ "$key" -eq 1 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/shizhong/nongli/* ${modulePath}${frameworkPath}

    echo "正在以Magisk模块方式修改方式修改MIUI时钟设置，显示农历"

  elif [ "$key" -eq 2 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/shizhong/xingqi/* ${modulePath}${frameworkPath}

    echo "正在以Magisk模块方式修改方式修改MIUI时钟设置，显示星期"

  elif [ "$key" -eq 3 ]; then

    cp -p -a -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/systemui/shizhong/nonglixingqi/* ${modulePath}${frameworkPath}

    echo "正在以Magisk模块方式修改方式修改MIUI时钟设置，显示农历和星期"

  else

    echo "未知动作，执行结束！"

  fi
  killall com.android.systemui

}

source /data/data/com.byyoung.setting/files/system/newbin/main_script.sh
