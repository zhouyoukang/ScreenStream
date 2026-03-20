// Turnstile Patcher v2.1 — 覆盖MouseEvent screenX/screenY为随机值
// 核心原理: Cloudflare Turnstile通过检测鼠标事件的screenX/screenY坐标
// 来判断是否为自动化操作(headless浏览器通常返回0,0)
// 注入随机真实值使Turnstile认为是真实用户操作

function getRandomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

let screenX = getRandomInt(800, 1200);
let screenY = getRandomInt(400, 600);

Object.defineProperty(MouseEvent.prototype, 'screenX', { value: screenX });
Object.defineProperty(MouseEvent.prototype, 'screenY', { value: screenY });

// 额外: 覆盖navigator.webdriver为undefined (anti-automation detection)
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 额外: 覆盖chrome.runtime为真实值 (防止检测扩展注入)
if (!window.chrome) { window.chrome = {}; }
if (!window.chrome.runtime) { window.chrome.runtime = { id: undefined }; }
