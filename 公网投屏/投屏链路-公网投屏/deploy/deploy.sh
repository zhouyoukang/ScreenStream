#!/bin/bash
# Deploy ScreenStream Relay to aiotvr.xyz
# Run from the server via SSH:
#   ssh aliyun 'bash -s' < deploy/deploy.sh
# Or copy files first then run on server.

set -e

APP_DIR="/www/dk_project/screenstream-relay"
REPO_DIR="投屏链路/公网投屏"

echo "=== ScreenStream Relay Deployment ==="

# 1. Create app directory
mkdir -p "$APP_DIR/client"

# 2. Install Node.js if not present
if ! command -v node &> /dev/null; then
    echo "Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
echo "Node.js: $(node -v)"

# 3. Install PM2 if not present
if ! command -v pm2 &> /dev/null; then
    echo "Installing PM2..."
    npm install -g pm2
fi

# 4. Copy files (assumes files are already on server via scp/rsync)
echo "Files should be at: $APP_DIR/"
echo "  - package.json"
echo "  - server.js"
echo "  - client/index.html"
echo "  - .env (copy from .env.example)"

# 5. Install dependencies
cd "$APP_DIR"
npm install --production

# 6. Create .env if not exists
if [ ! -f .env ]; then
    cat > .env << 'EOF'
PORT=9100
# TURN_SERVER=turn:turn.aiotvr.xyz:3478
# TURN_SECRET=change_me
EOF
    echo "Created .env with defaults"
fi

# 7. Start with PM2 (Node 18 doesn't support --env-file, use dotenv-style loading)
pm2 delete screenstream-relay 2>/dev/null || true

# Source .env vars and pass to PM2 via ecosystem-style start
set -a; source .env 2>/dev/null; set +a
pm2 start server.js \
    --name screenstream-relay \
    --max-memory-restart 200M \
    --exp-backoff-restart-delay=1000

pm2 save

echo ""
echo "=== Deployment Complete ==="
echo "Server running on :9100"
echo "PM2 status: pm2 status"
echo "PM2 logs:   pm2 logs screenstream-relay"
echo ""
echo "Next steps:"
echo "  1. Add Nginx config (see deploy/nginx-screen.conf)"
echo "  2. Test: curl https://aiotvr.xyz/app/ping"
echo "  3. Open: https://aiotvr.xyz/screen/"
