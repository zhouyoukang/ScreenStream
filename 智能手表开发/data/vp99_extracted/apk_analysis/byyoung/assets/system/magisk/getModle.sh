MagiskPath=$(magisk --path)
for i in $(ls -a "$MagiskPath"/.magisk/modules); do
  if [ -n "$i" ]; then
    echo "$MagiskPath"/.magisk/modules/"$i"
  fi

done
