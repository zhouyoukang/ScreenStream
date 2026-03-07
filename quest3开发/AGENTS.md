# Quest 3 开发 — Agent全链路操作手册

> 操作本目录时自动加载此指令。

## Agent身份

Quest 3全链路开发Agent——从代码编写到头显运行，无需用户手动操作。
**首选路径: WebXR** — 纯代码、无GUI依赖、即时部署、Quest浏览器直接运行。

## 一、WebXR开发全链路

### 1. 创建项目

```bash
# 方式A: 纯HTML（零依赖，适合快速原型）
mkdir webxr/my-demo && cat > webxr/my-demo/index.html << 'EOF'
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<script src="https://aframe.io/releases/1.6.0/aframe.min.js"></script>
</head><body>
<a-scene webxr="optionalFeatures: local-floor, hand-tracking;">
  <!-- 你的场景 -->
</a-scene>
</body></html>
EOF

# 方式B: Three.js（更强控制力）
mkdir my-app && cd my-app
npm init -y && npm install three
# 参考 refs/webxr-first-steps/

# 方式C: React Three Fiber（React生态）
npm create vite@latest my-xr -- --template react-ts
npm install @react-three/fiber @react-three/xr three
# 参考 refs/webxr-first-steps-react/
```

### 2. 本地测试

```powershell
# 方式A: xr-proxy（推荐，自动注入IWER模拟器 + WebSocket代理）
node webxr/xr-proxy.js
# 浏览器访问: http://localhost:8444/
# 功能: 静态文件服务 + IWER自动注入 + /quest-ws/ → :9200 WS代理

# 方式B: HTTPS服务（真机Quest测试时使用）
.\tools\setup.ps1           # 生成自签证书（首次）
npx serve webxr/my-demo --ssl-cert certs/cert.pem --ssl-key certs/key.pem -l 8443
# Quest同一WiFi下访问: https://<笔记本IP>:8443
```

### 3. 部署到公网

```powershell
# 远程部署到 aiotvr.xyz/quest/
.\tools\deploy-quest.ps1 -ProjectDir "../webxr/my-demo" -Remote

# 或手动: scp -r webxr/my-demo/* aliyun:/var/www/quest/my-demo/
# Quest访问: https://aiotvr.xyz/quest/my-demo/
```

### 4. PWA→APK打包（上架/Sideload）

```bash
# 使用 bubblewrap（refs/bubblewrap/）
npx @nicolo-ribaudo/nicolo create --url https://aiotvr.xyz/quest/my-demo/
# 生成 app-release-signed.apk

# Sideload到Quest
adb install -r app-release-signed.apk
```

### 5. 桌面调试（无需Quest设备）

```
# 安装 immersive-web-emulator Chrome扩展
# 源码: refs/immersive-web-emulator/
# 在Chrome DevTools中模拟Quest 3的WebXR API
```

## 二、关键约束

| 约束 | 说明 |
| ---- | ---- |
| HTTPS必须 | WebXR API只在HTTPS/localhost可用 |
| Quest浏览器 | 基于Chromium，支持WebGL2/WebXR/手部追踪 |
| immersive-vr | VR模式，不透视，黑色背景 |
| immersive-ar | MR模式，Passthrough透视，clearColor(0,0,0,0) |
| hand-tracking | `optionalFeatures: ['hand-tracking']`，25关节/手 |
| local-floor | 地面参考空间，Y=0为地板 |
| RATK | 空间锚点/Scene API/Plane Detection需要此库 |
| A-Frame版本 | 使用1.6.0（CDN: aframe.io/releases/1.6.0/aframe.min.js） |

## 三、本地参考仓库优先级

| 优先级 | 路径 | 用途 |
| ------ | ---- | ---- |
| ★★★★★ | `refs/ratk/` | MR核心库(Plane/Anchor/HitTest/Mesh) |
| ★★★★ | `refs/webxr-first-steps/` | 入门教程(Three.js)，学习WebXR模式 |
| ★★★★ | `refs/webxr-first-steps-react/` | React路线入门(R3F) |
| ★★★★ | `refs/ProjectFlowerbed/` | 完整WebXR游戏参考(Three.js) |
| ★★★★ | `refs/immersive-web-emulator/` | 桌面WebXR调试器 |
| ★★★★ | `refs/bubblewrap/` | PWA→APK打包 |
| ★★★ | `refs/webxr-handtracking/` | 手部追踪示例集 |
| ★★★ | `refs/enva-xr/` | AR遮挡+光照+物理 |
| ★★ | `refs/passtracing/` | MR描线画笔 |
| ★★ | `refs/immersive-home/` | Godot MR智能家居(非WebXR,参考设计) |

## 四、现有WebXR Demo清单

| Demo | 技术栈 | 功能 | 公网URL |
| ---- | ------ | ---- | ------- |
| portal (index.html) | HTML/CSS/JS | 导航页+XR检测 | aiotvr.xyz/quest/ |
| hello-vr | WebGL2原生 | 3D立方体+手部关节 | aiotvr.xyz/quest/hello-vr/ |
| mr-passthrough | WebGL2原生 | 透视+浮动球体+手部 | aiotvr.xyz/quest/mr-passthrough/ |
| aframe-playground | A-Frame 1.6 | 声明式场景+动画+交互 | aiotvr.xyz/quest/aframe-playground/ |
| hand-grab | A-Frame 1.6 | pinch-grab抓取+桌面布局 | aiotvr.xyz/quest/hand-grab/ |
| shared-space | A-Frame+WS | 多人位置同步+聊天 | aiotvr.xyz/quest/shared-space/ |
| smart-home | A-Frame+HA | HA设备3D面板+实时控制 | aiotvr.xyz/quest/smart-home/ |
| ar-placement | Three.js | AR放置+hit-test+平面检测+锚点 | aiotvr.xyz/quest/ar-placement/ |
| hand-physics | Three.js | 手部物理+官方手模型+抓投 | aiotvr.xyz/quest/hand-physics/ |
| controller-shooter | Three.js | 手柄射击+目标+粒子+触觉反馈 | aiotvr.xyz/quest/controller-shooter/ |
| spatial-audio | Three.js | 空间音频+HRTF+距离衰减+可视化 | aiotvr.xyz/quest/spatial-audio/ |
| gaussian-splat | A-Frame+3DGS | 高斯溅射VR查看器+多场景切换 | aiotvr.xyz/quest/gaussian-splat/ |
| vr-painter | Three.js | 3D空间绘画+手部追踪/手柄+撤销 | aiotvr.xyz/quest/vr-painter/ |
| simulator (simulator.html) | HTML/JS+IWER | Quest 3虚拟仿真环境+性能监控+全量测试 | aiotvr.xyz/quest/simulator.html |
| devops (devops.html) | HTML/JS | 全链路DevOps管理面板+测试+CDN检测 | aiotvr.xyz/quest/devops.html |

## 五、工具脚本

| 脚本 | 用途 |
| ---- | ---- |
| `tools/setup.ps1` | 环境一键配置：Node.js检查+ADB检查+Quest连接+自签证书生成 |
| `tools/deploy-quest.ps1` | 部署：`-Remote`远程scp到aiotvr.xyz / 默认本地HTTPS serve |
| `tools/deploy-pending.ps1` | 待部署清单：shared-space WS服务 + smart-home + portal更新 |
| `webxr/xr-proxy.js` | 本地开发代理：静态文件+IWER注入+WS代理(/quest-ws/→:9200) |

## 六、部署架构

```
本地开发:
  xr-proxy(:8444) ─── 静态文件 + IWER注入 + WS代理(/quest-ws/→:9200)
  shared-space server(:9200) ─── 多人WebSocket服务（可选）

公网部署(暂缓):
  本地 ─→ scp ─→ aliyun:/var/www/quest/
  Quest浏览器 ←── https://aiotvr.xyz/quest/ ←── Nginx反代
                                    │
                         WebSocket服务(:9200) ← shared-space
```

## 七、WebXR代码模式速查

### VR模式（黑色背景）
```javascript
session = await navigator.xr.requestSession('immersive-vr', {
    optionalFeatures: ['local-floor', 'hand-tracking']
});
gl.clearColor(0.05, 0.05, 0.1, 1.0); // 不透明背景
```

### MR Passthrough模式（透视）
```javascript
session = await navigator.xr.requestSession('immersive-ar', {
    optionalFeatures: ['local-floor', 'hand-tracking']
});
layer = new XRWebGLLayer(session, gl, { alpha: true });
gl.clearColor(0, 0, 0, 0); // 透明=透视
gl.enable(gl.BLEND);
```

### 手部追踪（25关节/手）
```javascript
for (const src of session.inputSources) {
    if (src.hand) {
        for (const joint of src.hand.values()) {
            const pose = frame.getJointPose(joint, refSpace);
            if (pose) {
                const p = pose.transform.position; // {x, y, z}
                const r = pose.radius || 0.008;
            }
        }
    }
}
```

### A-Frame手部抓取（pinch-grab组件）
```javascript
AFRAME.registerComponent('pinch-grab', {
    init() {
        this.el.addEventListener('pinchstarted', () => {
            // 找最近的.grabbable元素，attach到手
        });
        this.el.addEventListener('pinchended', () => {
            // 释放到场景
        });
    }
});
```

## 八、禁止事项

- **禁止** 尝试通过Agent启动Unity/Unreal编辑器（需GUI）
- **禁止** 假设Quest已连接USB（先`adb devices`检查）
- **禁止** 使用HTTP访问WebXR（浏览器拒绝，必须HTTPS）
- **禁止** 直接修改refs/下的参考项目代码（只读参考）
- **禁止** 在webxr/下创建node_modules（各demo为纯HTML，无构建步骤）
- **禁止** 部署时覆盖已有demo（先备份或新建子目录）

## 九、审计报告

最新审计: `AUDIT_REPORT.md` (2026-03-06)
- HTTP加载: 15/15 PASS (12 demos + portal + simulator + devops)
- Console错误: 12/14页面零错误
- 修复: deploy-pending补全 + simulator导航 + 文档同步
- 综合评分: 9.5/10
