#应用路径
userName="$1"
userType="$2"
userForce="$3"

pkgName=com.byyoung.setting
source /data/data/com.byyoung.setting/files/system/newbin/main_export.sh
export PATH=${filesPath}/term/:$PATH

if [ "$userName" = "" ]; then
  echo "传入用户名有误" 1>&2
  exit 128
fi
setprop fw.max_users 50
function create_user() {

  str=$(pm create-user "$userName")
  if [ "$str" = "" ]; then
    echo "创建新的分身出错！"
    exit 128
  fi
  userId=$(echo $str | sed 's/Success: created user id//')
  am start-user $userId
  pm set-user-restriction --user $userId allow_parent_profile_app_linking 1
  pm install-existing --user $userId $pkgName
  if [ "$?" -ne 0 ]; then
    apkPath=$(echo $(pm path "$pkgName") | sed 's/package://')
    pm install -r --user $userId "$apkPath"
  fi

}

if [ "$userType" = "" ]; then
  echo "当前分身逻辑使用默认"
  create_user
elif [ $userType = "profileOf" ]; then
  echo "当前分身逻辑使用工作模式优先"
  str=$(pm create-user --profileOf 0 --managed "$userName")
  if [ "$str" = "" ]; then

    if [ "$userForce" == "1" ]; then
      echo "创建新的工作分身出错，当前设置强制工作模式，分身终止"
      exit 128
    else
      echo "创建新的工作分身出错，正在切换默认分身创建"
      create_user
    fi

  else

    userId=$(echo $str | sed 's/Success: created user id//')
    pm set-user-restriction --user $userId allow_parent_profile_app_linking 1
    am start-user $userId
    pm install-existing --user $userId $pkgName
    if [ "$?" -ne 0 ]; then
      apkPath=$(echo $(pm path "$pkgName") | sed 's/package://')
      pm install -r --user $userId "$apkPath"
    fi

  fi
else
  echo "当前分身逻辑使用默认"
  create_user
fi
