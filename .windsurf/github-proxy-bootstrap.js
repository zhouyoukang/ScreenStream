// Bootstrap: patch Node.js native fetch to use HTTP CONNECT proxy
// Zero external dependencies - uses only built-in modules
// v2: Accept-Encoding:identity + localhost bypass + error fallback
const http = require('http');

const PROXY = process.env.HTTPS_PROXY || process.env.HTTP_PROXY || 'http://127.0.0.1:7897';
let proxyUrl;
try { proxyUrl = new URL(PROXY); } catch(e) { /* invalid proxy URL, skip patching */ }

if (proxyUrl) {
const origFetch = globalThis.fetch;
globalThis.fetch = async function(input, init) {
  let target;
  try {
    target = typeof input === 'string' ? new URL(input) : (input instanceof URL ? input : new URL(input.url));
  } catch(e) { return origFetch(input, init); }
  // Skip non-HTTPS and localhost (CDP, MCP internal)
  if (target.protocol !== 'https:') return origFetch(input, init);
  if (target.hostname === 'localhost' || target.hostname === '127.0.0.1') return origFetch(input, init);

  // Create CONNECT tunnel through proxy
  const tunnel = await new Promise((resolve, reject) => {
    const req = http.request({
      host: proxyUrl.hostname,
      port: proxyUrl.port || 7897,
      method: 'CONNECT',
      path: `${target.hostname}:${target.port || 443}`,
    });
    req.on('connect', (res, socket) => {
      if (res.statusCode === 200) resolve(socket);
      else reject(new Error(`CONNECT failed: ${res.statusCode}`));
    });
    req.on('error', reject);
    req.setTimeout(15000, () => { req.destroy(); reject(new Error('CONNECT timeout')); });
    req.end();
  });

  // Use the tunnel socket for TLS connection via undici
  // Fallback: reconstruct fetch with custom agent
  const tls = require('tls');
  const tlsSocket = tls.connect({
    host: target.hostname,
    socket: tunnel,
    servername: target.hostname,
  });
  await new Promise((resolve, reject) => {
    tlsSocket.on('secureConnect', resolve);
    tlsSocket.on('error', reject);
  });

  // Build raw HTTP request over TLS socket
  const method = (init && init.method) || 'GET';
  const headers = (init && init.headers) || {};
  const body = (init && init.body) || null;
  
  let reqPath = target.pathname + (target.search || '');
  // Collect headers into a map
  const headerMap = {};
  if (headers instanceof Headers) {
    headers.forEach((v, k) => { headerMap[k] = v; });
  } else if (typeof headers === 'object') {
    for (const [k, v] of Object.entries(headers)) { headerMap[k] = v; }
  }
  // Force identity encoding to prevent gzip corruption (raw HTTP parser can't decompress)
  headerMap['Accept-Encoding'] = 'identity';
  // Default User-Agent (GitHub API rejects bare requests)
  if (!headerMap['user-agent'] && !headerMap['User-Agent']) {
    headerMap['User-Agent'] = 'node-github-mcp/1.0';
  }
  let rawReq = `${method} ${reqPath} HTTP/1.1\r\nHost: ${target.hostname}\r\n`;
  for (const [k, v] of Object.entries(headerMap)) { rawReq += `${k}: ${v}\r\n`; }
  if (body) rawReq += `Content-Length: ${Buffer.byteLength(body)}\r\n`;
  rawReq += `Connection: close\r\n\r\n`;

  return new Promise((resolve, reject) => {
    tlsSocket.write(rawReq);
    if (body) tlsSocket.write(body);

    let data = '';
    tlsSocket.on('data', chunk => { data += chunk.toString(); });
    tlsSocket.on('end', () => {
      const [headersPart, ...bodyParts] = data.split('\r\n\r\n');
      const bodyStr = bodyParts.join('\r\n\r\n');
      const statusLine = headersPart.split('\r\n')[0];
      const statusCode = parseInt(statusLine.split(' ')[1], 10);
      const respHeaders = {};
      headersPart.split('\r\n').slice(1).forEach(line => {
        const idx = line.indexOf(': ');
        if (idx > 0) respHeaders[line.slice(0, idx).toLowerCase()] = line.slice(idx + 2);
      });
      resolve(new Response(bodyStr, { status: statusCode, headers: respHeaders }));
    });
    tlsSocket.on('error', reject);
  });
};
} // end if (proxyUrl)
