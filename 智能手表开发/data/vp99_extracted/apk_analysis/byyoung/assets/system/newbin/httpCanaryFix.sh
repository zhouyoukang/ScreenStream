dataPath=/data/data
for path in $(ls $dataPath | grep httpcanary); do
  echo $dataPath/"$path"
  appPath=$dataPath/$path
  if [ -f "$appPath/files/backup/HttpCanary.pem" ] && [ ! -f "$appPath/files/backup/HttpCanary.jks" ]; then
    cp -p -a "$appPath/files/backup/HttpCanary.pem" "$appPath/files/backup/HttpCanary.jks"
  else
    echo "发现备份文件/没有找到副本，自动跳过"
  fi
  if [ -f "$appPath/cache/HttpCanary.pem" ] && [ ! -f "$appPath/cache/HttpCanary.jks" ]; then
    cp -p -a "$appPath/cache/HttpCanary.pem" "$appPath/cache/HttpCanary.jks"
  elif [ -f "$appPath/files/backup/HttpCanary.pem" ] && [ ! -f "$appPath/cache/HttpCanary.jks" ]; then
    cp -p -a "$appPath/files/backup/HttpCanary.pem" "$appPath/cache/HttpCanary.jks"
  else
    echo "发现备份文件/没有找到副本，自动跳过"
  fi

done
