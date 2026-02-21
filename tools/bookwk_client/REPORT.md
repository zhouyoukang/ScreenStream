# 站点深度剖析报告：29.bookwk.top

> 生成时间: 2026-02-21  
> 工具: Playwright浏览器 + Python API客户端  
> 方法: 前端源码分析 + API端点探测 + 数据库校准接口逆向

---

## 一、产品身份

| 项目 | 值 |
|------|-----|
| **产品名** | 29网课交单平台 (又名"青卡网课") |
| **表前缀** | `qingka_wangke_` |
| **域名** | `29.bookwk.top` (子域名编号29) |
| **站点类型** | 网课代刷/交单平台（分站模式） |
| **商业模式** | 邀请码注册 → 充值 → 下单刷课 → 货源对接 |
| **来源** | PHP商业CMS，CSDN/网络有搭建教程和源码流出 |
| **默认管理** | uid=1，user表的ID/pass/name可改 |

## 二、技术栈

```
┌────────────────────────────────────────────┐
│         Frontend: Vue 3.5.28 (CDN)         │
│   Bootstrap + Font Awesome 5.15.4 + Layer  │
│         WxqqJump (微信QQ跳转组件)           │
├────────────────────────────────────────────┤
│            Nginx (HTTPS + HSTS)            │
│          max-age=31536000 (1年)            │
├────────────────────────────────────────────┤
│           PHP 7.4.33 Backend               │
│   3个API入口 + Session鉴权 + QQ邮箱验证    │
├────────────────────────────────────────────┤
│       MySQL (127.0.0.1:3306)               │
│   Database: bookwk | 79张表(标准21张)       │
└────────────────────────────────────────────┘
```

## 三、目录结构（已探测确认）

```
bookwk.top/
├── index/                          ← 前端入口
│   ├── index.php                   ← 主页(302→login.php)
│   ├── login.php                   ← Vue 3 登录/注册页
│   └── database_calibration.php    ← ⚠️ DB校准API(公开!)
├── install/                        ← ⚠️ DB校准工具(公开!)
├── api/                            ← API目录(200空)
├── config/config.php               ← [403] 数据库配置
├── confing/confing.php             ← [403] 配置(拼写错误路径也存在)
├── nginx.htaccess                  ← [403] 伪静态规则
├── database.sql                    ← [403] 数据库SQL文件
├── assets/                         ← [403] 静态资源
│   ├── css/bootstrap.min.css       ← [200]
│   └── js/jquery.min.js            ← [200]
├── WxqqJump/                       ← [403] 微信QQ跳转
│   └── layer/layer.js              ← [200] Layer弹窗库
├── apilogin.php                    ← 公开API(登录/注册/验证)
├── apisub.php                      ← 分站API(38个端点,需登录)
└── apisb.php                       ← 系统API(12个端点,需登录)
```

## 四、API端点清单（53个已确认）

### apilogin.php — 公开API（7个）

| act | 方法 | 参数 | 功能 |
|-----|------|------|------|
| `register` | POST | name, account(QQ), password, verify_code, invite_code | 注册 |
| `login` | POST | — | (密码登录走apisub) |
| `verify_login` | POST | account, verify_code, type | 验证码登录 |
| `send_verify_code` | POST | account(QQ号), type(登录/注册) | 发QQ邮箱验证码 |
| `find_account` | POST | qq_number | QQ查找账号 |
| `send_reset_verify_code` | POST | qq_number | 重置密码验证码 |
| `reset_password` | POST | qq_number, verify_code, new_password | 重置密码 |

### apisub.php — 分站业务API（38个，需Session）

**用户管理**: user_info, get_user_list, get_all_users, edit_user, del_user  
**课程管理**: get_course_list, add_course, del_course, edit_course  
**订单管理**: get_order_list, get_task_list  
**财务管理**: get_money_log, get_pay_config, get_recharge_list  
**系统管理**: get_config, get_settings, get_site_info, dashboard, get_notice, check_update  
**分站管理**: get_subsite_list, add_subsite, get_agent_list  
**邀请码/卡密**: get_invite_codes, generate_invite_code, get_km_list, generate_km  
**货源/分类**: get_huoyuan_list, get_fenlei_list  
**内容管理**: get_gonggao_list, get_gongdan_list, get_help_list, get_huodong_list  
**等级/密价**: get_dengji_list, get_mijia_list  
**域名/日志**: get_domain_list, get_log_list, get_stats  
**登录**: login (user+pass, 支持pass2管理员二次验证)

### apisb.php — 系统管理API（12个，需Session）

| act | 功能 | 危险等级 |
|-----|------|---------|
| check_version | 版本更新检查 | 🟢 |
| check_tables | 检查数据库表结构 | 🟡 |
| get_standard_tables | 获取标准表定义 | 🟡 |
| calibrate | 数据库校准/修复 | 🟡 |
| get_log | 获取系统日志 | 🟡 |
| get_system_info | 系统信息 | 🟡 |
| get_php_info | PHP信息 | 🔴 |
| clear_cache | 清除缓存 | 🔴 |
| backup_db | 数据库备份 | 🔴 |
| restore_db | 数据库恢复 | 🔴 |
| update_system | 系统更新 | 🔴 |
| **run_sql** | **执行SQL** | 🔴🔴 |

## 4.5、前端真实API（从页面HTML提取，25个）

> ⚠️ 前端页面实际使用的act名称与上方管理端点命名不同（如 `userinfo` vs `user_info`）

| 来源页面 | act | API | 测试结果 |
|----------|-----|-----|---------|
| home.php | `userinfo` | apisub | ✅ code=1 (uid/money/addprice/key等16字段) |
| home.php | `user_notice` | apisub | ✅ code=1 |
| home.php | `yqprice` | apisub | 需参数(费率数字) |
| home.php | `ktapi` | apisub | code=-2 未知异常 |
| home.php | `send_qq_verify_code` | apisb | 需参数 |
| home.php | `update_qq_number` | apisb | 需参数 |
| userlist.php | `userlist` | apisub | ✅ code=1 (分页) |
| userlist.php | `adddjlist` | apisub | ✅ code=1 (代理等级列表) |
| userlist.php | `adduser` | apisub | 需参数 |
| userlist.php | `user_ban` | apisub | 需权限 |
| userlist.php | `user_czmm` | apisub | 需权限(下级) |
| userlist.php | `usergj` | apisub | 需参数(费率) |
| userlist.php | `userjk` | apisub | 需参数(金额) |
| userlist.php | `userkc` | apisub | 空响应 |
| userlist.php | `szyqm` | apisub | 需参数(>=4位数字) |
| add.php | `add` | apisub | 需参数(课程) |
| add.php | `get` | apisub | 需CSRF验证 |
| add.php | `getclass` | apisub | ✅ code=1 (课程列表+价格) |
| add.php | `getclassfl` | apisub | ✅ code=1 (课程分类) |
| add.php | `getCategoryInfo` | apisub | 空响应 |
| add.php | `getFavorites` | apisub | ✅ code=1 |
| add.php | `toggleFavorite` | apisub | 需参数(分类ID) |
| log.php | `loglist` | apisub | ✅ code=1 (分页, 25页) |
| charge.php | `pay` | apisub | 需参数(金额) |
| help.php | `help_list` | apisb | ✅ code=1 (分页) |

**代理等级体系**（从adddjlist响应）: 顶级代理(0.15-0.185) → 基础代理(0.20) → 入门代理(0.30-0.60)

## 五、数据库结构（21张标准表 + 58张扩展表 = 79张）

### 标准表

| 表名 | 字段数 | 用途 |
|------|--------|------|
| qingka_wangke_user | 23 | 用户（QQ号/密码/余额/等级/邀请码） |
| qingka_wangke_order | 44 | 订单（最大表，网课代刷订单） |
| qingka_wangke_class | 20 | 课程/班级 |
| qingka_wangke_lg_pg_lp | 20 | 批量同步/分页 |
| qingka_wangke_lg_jy | 19 | 交易记录 |
| qingka_wangke_subsites | 17 | 分站管理 |
| qingka_wangke_pay | 15 | 支付配置 |
| qingka_wangke_pay2 | 14 | 支付配置2 |
| qingka_wangke_fenlei | 13 | 分类 |
| qingka_wangke_huoyuan | 13 | 货源 |
| qingka_wangke_gongdan | 11 | 工单 |
| qingka_wangke_dengji | 10 | 等级 |
| qingka_wangke_huodong | 10 | 活动 |
| qingka_wangke_help | 9 | 帮助文档 |
| qingka_wangke_homenotice | 9 | 首页通知 |
| qingka_wangke_domain_records | 8 | 域名记录 |
| qingka_wangke_log | 8 | 操作日志 |
| qingka_wangke_mijia | 8 | 密价/定价 |
| qingka_wangke_km | 7 | 卡密 |
| qingka_wangke_gonggao | 7 | 公告 |
| qingka_wangke_config | 2 | 键值配置 |

## 六、泄露的配置键名（123个）

### 支付相关（17个）
`epay_api`, `epay_key`, `epay_pid`, `epay_protocol`, `epay_zs`, `epay_zs_open`, `epay_kgzs`, `epay_hdkgzs`, `epay_hdzs`, `epay_hdzsfw`, `is_alipay`, `is_qqpay`, `is_wxpay`, `zdpay`, `zgpay`, `zgtspay`, `paytj`

### 邮件SMTP（12个）
`smtp_host`, `smtp_port`, `smtp_user`, `smtp_pass`, `smtp_secure`, `smtp_from_name`, `smtp_cuser`, `smtp_default_subject`, `smtp_open`, `smtp_open_cz`, `smtp_open_gd`, `smtp_open_huo`, `smtp_open_login`, `smtp_open_xd`

### 第三方登录（4个）
`login_apiurl`, `login_appid`, `login_appkey`, `login_banner`

### 服务器（3个）
`serverIP`, `serverIP_type`, `serverIP_uid`

### 站点配置（15个）
`sitename`, `subsitename`, `description`, `keywords`, `logo`, `hlogo`, `cb_logo`, `login_logo`, `homePath`, `f_homePath`, `storePath`, `fontsFamily`, `fontsZDY`, `fontsZDY_jscss`, `themesData_default`

### 功能开关（20+个）
`chadan_open`, `chadan_bs`, `chadan_default`, `chadan_t_notice`, `onlineStore_open`, `onlineStore_add`, `onlineStore_trdltz`, `verify_code_login`, `verify_code_register`, `verify_login_enabled`, `verify_register_enabled`, `money_transfer`, `webVfx_open`, `flkg`, `sjqykg`, `sykg`, `xdsmopen`, `dlgl_notice_open` ...

### 其他关键键
`user_pass`(默认密码), `user_ktmoney`(开通金额), `user_yqzc`(邀请注册), `user_htkh`(回退扣号), `authcodes`(授权码), `nanatoken`, `bt_token`(宝塔Token), `akcookie`, `dklcookie`

## 七、业务流程分析

```
用户注册(邀请码+QQ验证码)
    ↓
用户登录(密码/QQ验证码)
    ↓
浏览课程分类(fenlei) → 选择货源(huoyuan)
    ↓
下单(order, 44字段！) → 支付(epay/支付宝/微信/QQ)
    ↓
系统自动或人工处理订单 → 网课代刷
    ↓
完成/退款 → 交易记录(lg_jy)
```

### 分站体系
- 主站管理员通过 `subsites` 表管理分站
- 分站有独立域名(`domain_records`)
- 分站用户通过邀请码关联
- 卡密系统(`km`)用于充值/激活

### 登录体系
- **密码登录** → `apisub.php?act=login` (user+pass)
- **验证码登录** → `apilogin.php?act=verify_login` (QQ号+邮箱验证码)
- **管理员二次验证** → `apisub.php?act=login` (user+pass+pass2)
- **QQ聚合登录** → `login_apiurl` + `login_appid` + `login_appkey`

## 八、安全评估

### 🔴 高危（3个）

1. **install/ + database_calibration.php 公开无鉴权**
   - 可执行 `calibrate` 操作修改数据库结构
   - 泄露完整表结构(21表+字段数)
   - 泄露123个配置键名（含支付/SMTP/Token名称）
   - 泄露PHP版本(7.4.33)、数据库地址(127.0.0.1:3306)、库名(bookwk)

2. **验证码接口无频率限制**
   - `send_verify_code` 可用任意QQ号触发
   - 无IP限制、无图形验证码、无频率控制
   - 可被滥用为QQ邮箱轰炸工具

3. **apisb.php 含 `run_sql` 端点**
   - 虽需登录，但若获得Session即可执行任意SQL
   - 同理 `backup_db`/`restore_db` 可完全控制数据库

### 🟡 中危（4个）

4. **敏感文件路径暴露**：config.php, confing.php, database.sql, nginx.htaccess 均返回403而非404
5. **前端逻辑完全暴露**：Vue 3 CDN + 内联JS，所有API参数/流程/校验逻辑明文可见
6. **无CSRF保护**：所有API用 `application/x-www-form-urlencoded`，无token/nonce
7. **Session固定**：`server_name_session` Cookie值在不同会话间可能被复用

### 🟢 低危（2个）

8. **目录列表已关闭**：assets/、WxqqJump/ 返回403
9. **Session鉴权基本有效**：apisub/apisb 38+12个端点均需登录

## 九、本地工具

```
tools/bookwk_client/
├── bookwk_api.py   ← API客户端 v2（53端点全覆盖 + 重试 + 环境变量配置）
└── REPORT.md       ← 本报告
```

### 配置（环境变量，避免硬编码凭据）

```
BOOKWK_USER=你的QQ号     # 登录用户名
BOOKWK_PASS=你的密码     # 登录密码
BOOKWK_URL=https://29.bookwk.top/  # 可选，覆盖默认站点
```

### 使用示例

```python
from bookwk_api import BookWKClient

c = BookWKClient()

# 公开操作（无需登录）
c.probe_all_public()                   # 探测端点连通性
c.find_account("12345")                # QQ查找账号
c.send_verify_code("12345", "登录")     # 发验证码

# 登录（优先读取环境变量，也可传参）
c.login_password("user", "pass")       # 密码登录
c.login_verify_code("qq", "code")      # 验证码登录

# 业务API（需登录，共46个方法）
c.full_status()          # 9个关键API一次拉取
c.get_course_list()      # 课程
c.get_order_list()       # 订单
c.get_invite_codes()     # 邀请码
c.get_km_list()          # 卡密
c.get_huoyuan_list()     # 货源
c.get_stats()            # 统计

# 系统管理API（12个，含高危操作）
c.check_version()        # 版本
c.check_tables()         # 数据库检查
c.get_system_info()      # 系统信息
c.run_sql("SELECT 1")   # ⚠️ 极高危：任意SQL

# 通用调用（未封装的端点也能调）
c.call("some_act", api="sub", key="value")

# CLI交互模式（25个命令）
python bookwk_api.py

# 快捷命令行
python bookwk_api.py --probe    # 探测
python bookwk_api.py --status   # 登录+全状态（需环境变量）
```

---

*本报告仅用于安全研究和技术学习目的。*
