// Bootstrap: route Node.js native fetch through HTTP proxy
// v4: Uses undici EnvHttpProxyAgent (undici v7+ compatible, reads HTTPS_PROXY env)
// v3 ProxyAgent broke with undici v7 (connect timeout on CONNECT tunnel)
const PROXY = process.env.HTTPS_PROXY || process.env.HTTP_PROXY || 'http://127.0.0.1:7890';

if (PROXY) {
  // Ensure env var is set for EnvHttpProxyAgent to pick up
  process.env.HTTPS_PROXY = process.env.HTTPS_PROXY || PROXY;
  process.env.HTTP_PROXY = process.env.HTTP_PROXY || PROXY;
  try {
    // Primary: EnvHttpProxyAgent from global npm undici (works with v7+)
    const path = require('path');
    const npmGlobal = path.join(process.env.APPDATA || '', 'npm', 'node_modules');
    const { EnvHttpProxyAgent, setGlobalDispatcher } = require(path.join(npmGlobal, 'undici'));
    setGlobalDispatcher(new EnvHttpProxyAgent());
  } catch (e) {
    try {
      // Fallback: Node.js built-in undici (22.8+)
      const { EnvHttpProxyAgent, setGlobalDispatcher } = require('undici');
      setGlobalDispatcher(new EnvHttpProxyAgent());
    } catch (e2) {
      process.stderr.write(`[github-proxy-bootstrap] WARNING: proxy setup failed: ${e.message}\n`);
    }
  }
}