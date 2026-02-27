---
name: pwa-framework
description: PWA单文件框架+WebView封装+五感UX。当需要创建离线优先Web应用、单文件PWA、移动端优化应用时自动触发。
triggers:
  - 需要创建离线优先的Web应用
  - 要求无服务器部署和零外部依赖
  - 移动端优化和PWA特性需求
  - Android WebView封装
---

# PWA单文件框架 (PWA Framework)

> **核心理念**：自给自足的单文件应用，零依赖离线运行，跨平台一致体验

## 触发条件
- 需要创建离线优先的Web应用
- 要求无服务器部署和零外部依赖
- 移动端优化和PWA特性需求
- 关键词：PWA、离线应用、单文件、Service Worker、移动优先

## 框架特性

### 单文件架构
- **HTML+CSS+JS完全内嵌**：消除网络请求
- **数据直接嵌入**：JSON数据编译时写入JavaScript
- **资源Base64内联**：图标、字体等资源嵌入
- **零外部依赖**：可通过文件协议直接运行

### PWA标准特性
- **Web App Manifest**：可安装到主屏幕
- **Service Worker**：离线缓存策略
- **响应式设计**：适配各种屏幕尺寸
- **触屏优化**：移动端交互体验

## 基础模板

### HTML结构模板
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">

  <!-- PWA元信息 -->
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="theme-color" content="#主题色">
  <meta name="description" content="应用描述">

  <!-- 标题和图标 -->
  <title>应用名</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='80'>图</text></svg>">

  <!-- 内联样式 -->
  <style>
    /* 重置和基础样式 */
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
      -webkit-tap-highlight-color: transparent;
    }

    /* CSS变量定义 */
    :root {
      --primary: #主色;
      --bg: #背景色;
      --text: #文字色;
      --safe-b: env(safe-area-inset-bottom, 0px);
      --safe-t: env(safe-area-inset-top, 0px);
    }

    /* 全屏布局 */
    html, body {
      height: 100%;
      overflow: hidden;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, system-ui, sans-serif;
    }

    /* 主容器 */
    .app {
      display: flex;
      flex-direction: column;
      height: 100dvh;
      padding-top: var(--safe-t);
      padding-bottom: var(--safe-b);
    }
  </style>
</head>
<body>
  <!-- 应用结构 -->
  <div class="app">
    <!-- 内容区域 -->
  </div>

  <!-- Service Worker注册 -->
  <script>
    // PWA离线缓存
    if ('serviceWorker' in navigator) {
      const sw = `
        const CACHE_NAME = '应用名-v1';
        self.addEventListener('install', e => {
          self.skipWaiting();
        });
        self.addEventListener('activate', e => {
          e.waitUntil(clients.claim());
        });
        self.addEventListener('fetch', e => {
          // 离线策略
          e.respondWith(fetch(e.request).catch(() => new Response('离线模式')));
        });
      `;
      navigator.serviceWorker.register(URL.createObjectURL(new Blob([sw], {type: 'application/javascript'})));
    }

    // 数据嵌入区域
    const APP_DATA = {
      // 编译时嵌入的数据
    };

    // 应用逻辑
    class App {
      constructor() {
        this.init();
      }

      init() {
        // 初始化逻辑
      }
    }

    // 启动应用
    new App();
  </script>
</body>
</html>
```

## 核心功能模块

### 1. 本地存储管理
```javascript
class Storage {
  static save(key, data) {
    try {
      localStorage.setItem(key, JSON.stringify(data));
      return true;
    } catch (e) {
      console.error('存储失败:', e);
      return false;
    }
  }

  static load(key, defaultValue = null) {
    try {
      const data = localStorage.getItem(key);
      return data ? JSON.parse(data) : defaultValue;
    } catch (e) {
      return defaultValue;
    }
  }

  static remove(key) {
    localStorage.removeItem(key);
  }
}
```

### 2. 响应式状态管理
```javascript
class State {
  constructor(initialState = {}) {
    this._state = initialState;
    this._listeners = new Map();
  }

  get(key) {
    return this._state[key];
  }

  set(key, value) {
    const oldValue = this._state[key];
    this._state[key] = value;

    if (this._listeners.has(key)) {
      this._listeners.get(key).forEach(callback => {
        callback(value, oldValue);
      });
    }
  }

  subscribe(key, callback) {
    if (!this._listeners.has(key)) {
      this._listeners.set(key, new Set());
    }
    this._listeners.get(key).add(callback);
  }
}
```

### 3. 路由系统
```javascript
class Router {
  constructor() {
    this.routes = new Map();
    this.currentPath = '';
  }

  register(path, handler) {
    this.routes.set(path, handler);
  }

  navigate(path) {
    if (this.routes.has(path)) {
      this.currentPath = path;
      this.routes.get(path)();
      history.pushState({}, '', '#' + path);
    }
  }

  init() {
    window.addEventListener('hashchange', () => {
      const path = location.hash.slice(1) || '/';
      this.navigate(path);
    });

    // 初始路由
    const path = location.hash.slice(1) || '/';
    this.navigate(path);
  }
}
```

### 4. 网络请求封装
```javascript
class HTTP {
  static async request(url, options = {}) {
    const config = {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    };

    try {
      const response = await fetch(url, config);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('请求失败:', error);
      throw error;
    }
  }

  static get(url, params = {}) {
    const query = new URLSearchParams(params).toString();
    const fullUrl = query ? `${url}?${query}` : url;
    return this.request(fullUrl);
  }

  static post(url, data = {}) {
    return this.request(url, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }
}
```

## 移动端优化

### 触摸交互优化
```css
/* 触摸反馈 */
.btn {
  transition: transform 0.1s;
  -webkit-user-select: none;
  user-select: none;
}

.btn:active {
  transform: scale(0.95);
}

/* 滚动优化 */
.scrollable {
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
}

/* 输入框优化 */
input, textarea {
  font-size: 16px; /* 防止iOS缩放 */
  border-radius: 0; /* 防止iOS圆角 */
}
```

### 性能优化
```javascript
// 防抖函数
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// 节流函数
function throttle(func, limit) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// 虚拟滚动（大列表优化）
class VirtualScroll {
  constructor(container, itemHeight, renderItem) {
    this.container = container;
    this.itemHeight = itemHeight;
    this.renderItem = renderItem;
    this.data = [];
    this.viewportHeight = container.clientHeight;
    this.visibleCount = Math.ceil(this.viewportHeight / itemHeight) + 2;
    this.startIndex = 0;

    this.init();
  }

  init() {
    this.container.addEventListener('scroll', throttle(() => {
      this.update();
    }, 16));
  }

  setData(data) {
    this.data = data;
    this.update();
  }

  update() {
    const scrollTop = this.container.scrollTop;
    this.startIndex = Math.floor(scrollTop / this.itemHeight);
    const endIndex = Math.min(this.startIndex + this.visibleCount, this.data.length);

    // 渲染可见项
    const visibleItems = this.data.slice(this.startIndex, endIndex);
    const html = visibleItems.map((item, index) =>
      this.renderItem(item, this.startIndex + index)
    ).join('');

    this.container.innerHTML = html;
    this.container.style.paddingTop = `${this.startIndex * this.itemHeight}px`;
    this.container.style.paddingBottom = `${(this.data.length - endIndex) * this.itemHeight}px`;
  }
}
```

## 数据嵌入策略

### 编译时数据注入
```javascript
// 构建脚本示例
const fs = require('fs');

function embedData(templatePath, dataPath, outputPath) {
  let template = fs.readFileSync(templatePath, 'utf8');
  const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));

  // 替换数据占位符
  template = template.replace(
    '// 数据嵌入区域',
    `const EMBEDDED_DATA = ${JSON.stringify(data, null, 2)};`
  );

  fs.writeFileSync(outputPath, template);
}
```

### 数据压缩优化
```javascript
// 简单数据压缩
function compressData(data) {
  // 移除不必要的空白
  let compressed = JSON.stringify(data);

  // 简单字符串压缩（基于重复模式）
  const patterns = {
    '"time":"': 't:"',
    '"sender":"': 's:"',
    '"text":"': 'x:"'
  };

  Object.entries(patterns).forEach(([old, new_]) => {
    compressed = compressed.replace(new RegExp(old, 'g'), new_);
  });

  return compressed;
}
```

## 部署和分发

### 文件压缩优化
```bash
# HTML压缩
npx html-minifier --collapse-whitespace --remove-comments --minify-css --minify-js input.html -o output.html

# Gzip压缩测试
gzip -c app.html | wc -c
```

### 多平台适配
- **桌面浏览器**：直接打开HTML文件
- **移动浏览器**：添加到主屏幕
- **Android WebView**：assets资源封装
- **Electron**：桌面应用包装

## 最佳实践

1. **离线优先设计**：核心功能无网络依赖
2. **渐进增强**：网络可用时提供更好体验
3. **性能优先**：内联资源减少请求数
4. **移动优先**：针对触屏设备优化
5. **可维护性**：清晰的代码结构和注释

## 成功案例

- **AI初恋mobile.html**：787行单文件，包含完整对话系统
- **记忆搜索**：1400条数据实时检索，无外部数据库
- **离线PWA**：可安装到主屏幕，完全离线运行

## Android WebView封装

> 从mobile-app-dev skill合并而来。完整模板见 `templates/android-webview-template.md`

### 封装流程
```
PWA单文件 → assets/app.html → WebView加载 → 沉浸式全屏 → APK
```

### WebView核心配置
```java
WebSettings settings = webView.getSettings();
settings.setJavaScriptEnabled(true);
settings.setDomStorageEnabled(true);
settings.setCacheMode(WebSettings.LOAD_CACHE_ONLY);
settings.setAllowFileAccess(true);
settings.setBlockNetworkLoads(true); // 纯离线
```

### Gradle关键配置
```gradle
android {
    compileSdkVersion 34
    defaultConfig { minSdkVersion 21; targetSdkVersion 34 }
}
// gradle.properties必须:
// android.overridePathCheck=true  (中文路径兼容)
```

### 常见问题
- **WebView白屏** → 检查assets路径和JS权限
- **中文路径编译失败** → `android.overridePathCheck=true`
- **返回键无效** → 重写`onBackPressed()`
- **触摸延迟** → 禁用zoom和user-scalable

## 五感体验设计

| 感官 | 设计要点 |
|------|---------|
| **视觉** | 沉浸式全屏 + `env(safe-area-inset-*)` + 主题色统一 + skeleton screen |
| **触觉** | `-webkit-tap-highlight-color: transparent` + `touch-action`控制 + `scale(0.95)` active反馈 |
| **认知** | 零学习成本 + 返回键自然映射 + 状态清晰(加载/成功/失败) |
| **情感** | 人格一致性 + 本地偏好存储 + 人性化文案 |
| **听觉** | 遵循系统静音 + 关键操作音效 + 视觉替代降级 |

## 质量清单

- [ ] PWA离线运行正常（file://协议测试）
- [ ] Android App安装+启动<2秒
- [ ] 触摸响应<100ms
- [ ] 返回键/屏幕旋转符合预期
- [ ] 320px-2560px宽度适配
- [ ] 单文件<1MB（含数据）
