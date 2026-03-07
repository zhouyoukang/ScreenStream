#!/bin/bash
# Deploy relay server to aiotvr.xyz
# Usage: bash deploy.sh

set -e

SERVER="aliyun"  # SSH alias
REMOTE_DIR="/opt/desktop-cast"

echo "=== Deploying Desktop Cast Relay to aiotvr.xyz ==="

# Upload files
ssh $SERVER "mkdir -p $REMOTE_DIR/viewer"
scp server.js package.json $SERVER:$REMOTE_DIR/
scp viewer/index.html viewer/manifest.json $SERVER:$REMOTE_DIR/viewer/

# Install deps & restart
ssh $SERVER "cd $REMOTE_DIR && npm install --omit=dev && systemctl restart desktop-cast"

# Verify
sleep 2
ssh $SERVER "systemctl is-active desktop-cast && tail -3 /var/log/desktop-cast.log"

echo ""
echo "=== Deployed! ==="
echo "Relay: wss://aiotvr.xyz/desktop/"
echo "Viewer: https://aiotvr.xyz/desktop/"
