#MagiskPath=$(magisk --path)
genericPath=/system/usr/keylayout/Generic.kl
#名称和值
key="$@"
#0恢复默认按键，1按键互换，2屏蔽按键
function enable_root() {
  mount -o remount,rw /system

  if [ ! -f ${genericPath}.bak ]; then

    echo "第一次使用，正在备份按键配置！"
    echo ""

    cp -p -a ${genericPath} ${genericPath}.bak

  fi

  if [ "$key" -eq 0 ]; then

    mv -f ${genericPath}.bak ${genericPath}

    echo "正在以Root修改方式还原按键设置"

  elif [ "$key" -eq 1 ]; then

    cp -p -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/anjian/shiti/pingbi/Generic.kl ${genericPath}

    echo "正在以Root修改方式修改按键互换设置"

  elif [ "$key" -eq 2 ]; then

    cp -p -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/anjian/shiti/qita/Generic.kl ${genericPath}

    echo "正在以Root修改方式设置按键屏蔽设置"

  else

    echo "未知动作，执行结束！"

  fi

}

function enable_magisk() {

  if [ "$key" -eq 0 ]; then

    rm -r ${modulePath}/system/usr

    echo "正在以Magisk修改方式还原按键设置"

  elif [ "$key" -eq 1 ]; then

    mkdir -p ${modulePath}/system/usr/keylayout
    cp -p -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/anjian/shiti/qita/Generic.kl ${modulePath}${genericPath}

    echo "正在以Magisk修改方式修改按键互换设置"

  elif [ "$key" -eq 2 ]; then

    mkdir -p ${modulePath}/system/usr/keylayout
    cp -p -R /data/data/com.byyoung.setting/files/system/xbin/byyoung/anjian/shiti/pingbi/Generic.kl ${modulePath}${genericPath}

    echo "正在以Magisk修改方式设置按键屏蔽设置"

  else

    echo "未知动作，执行结束！"

  fi

}

source /data/data/com.byyoung.setting/files/system/newbin/main_script.sh
