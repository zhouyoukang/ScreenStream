---
trigger: glob
glob_pattern: "*.{html,js,css}"
---

# 前端项目认知

> 此文件为"术"层——项目特定知识。当编辑 `*.html/*.js/*.css` 文件时自动加载。

## 前端资源

| 文件 | 用途 |
|------|------|
| `网络投屏/cast/index.html` | 投屏控制页面 |
| `网络投屏/前端/` | HTML/CSS/JS资源 |

## 开发服务器

```bash
# 在对应目录启动
python -m http.server 8080
```

## 注意事项

- 静态资源路径注意相对路径
- JavaScript 模块使用 ES6+ 语法
- CSS 使用现代布局（Flexbox/Grid）

---

*此文件仅在编辑前端文件时加载。*
