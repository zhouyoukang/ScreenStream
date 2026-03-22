while true; do
  if [ -d "/storage/emulated/0/Android/data" ]; then
    break
  fi
  sleep 3
done
