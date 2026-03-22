#方案和mac地址
method="$1" mac="$2"
if [ "$mac" = "" ] || [ "$method" = "" ]; then
  echo "传入方法有误" 1>&2
  exit 128
fi

if [ "$method" -eq 1 ]; then
  svc wifi disable
  ifconfig wlan0 down
  ifconfig wlan0 hw ether "$mac"

  for wlanPath in $(find /sys/devices -name 'wlan0'); do
    if [[ -f "$wlanPath/address" ]]; then
      chmod 644 "$wlanPath/address"
      echo "$mac" >"$wlanPath/address"
      echo "$wlanPath/address"
    fi
  done

  chmod 0755 /sys/class/net/wlan0/address
  echo "$mac" >/sys/class/net/wlan0/address

  for wlanPath in $(find /sys/devices -name '*,wcnss-wlan'); do
    if [[ -f "$wlanPath/wcnss_mac_addr" ]]; then
      chmod 644 "$wlanPath/wcnss_mac_addr"
      echo "$mac" >"$wlanPath/wcnss_mac_addr"
      echo '"$wlanPath/wcnss_mac_addr"'
    fi
  done

  ifconfig wlan0 up
  svc wifi enable

else

  ifconfig wlan0 down
  stop wifi 2>/dev/null
  ifconfig wlan0 hw ether "$mac"
  ifconfig wlan0 up
  start wifi 2>/dev/null
fi
nowMac=$(cat /sys/class/net/wlan0/address)
if [ "$mac" == "$nowMac" ]; then
  echo "修改Mac成功，当前Mac：$nowMac"
else
  echo "修改Mac失败，当前Mac：$nowMac" 1>&2
  exit 127

fi
