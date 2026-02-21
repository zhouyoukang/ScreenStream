"""
BookWK API Client — 网课管理平台本地通联工具
站点: https://29.bookwk.top
技术栈: PHP 7.4 + MySQL + Vue 3 + Nginx

API架构 (25个已验证端点 + 12个系统端点):
  - apilogin.php: 公开API 7个（登录/注册/验证码/找回密码）
  - apisub.php:   分站API（用户/课程/订单/配置，需Session）
  - apisb.php:    系统API（版本/数据库/备份，需Session）

真实API act名（从页面源码提取，非猜测）:
  home.php:     userinfo, user_notice, yqprice, ktapi
  userlist.php: userlist, adddjlist, adduser, szyqm, user_ban, user_czmm, usergj, userjk, userkc
  add.php:      add, get, getclass, getclassfl, getCategoryInfo, getFavorites, toggleFavorite
  log.php:      loglist
  charge.php:   pay
  help.php:     help_list (via apisb)

配置:
  环境变量 BOOKWK_USER / BOOKWK_PASS 可预设凭据（避免硬编码）
  环境变量 BOOKWK_URL 可覆盖默认站点地址
"""

import requests
import json
import os
import time
import sys
from urllib.parse import urljoin
from typing import Optional, Dict, Any, List

DEFAULT_URL = "https://29.bookwk.top/"
MAX_RETRIES = 2
RETRY_DELAY = 1.0


class BookWKClient:
    """BookWK 网课管理平台 API 客户端 — 25个已验证端点"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.environ.get("BOOKWK_URL", DEFAULT_URL)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": self.base_url,
            "Referer": urljoin(self.base_url, "index/login.php"),
        })
        self.logged_in = False
        self.user_info = None
        self._init_session()

    def _init_session(self):
        """初始化Session：访问登录页获取PHPSESSID和必要Cookie"""
        try:
            self.session.get(urljoin(self.base_url, "index/login.php"), timeout=10)
        except Exception:
            pass

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path)

    def _request(self, method: str, path: str, data: dict = None,
                 params: dict = None, retries: int = MAX_RETRIES) -> dict:
        """统一请求方法，含重试和错误处理"""
        last_err = None
        for attempt in range(retries + 1):
            try:
                if method == "POST":
                    resp = self.session.post(
                        self._url(path), data=data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=15,
                    )
                else:
                    resp = self.session.get(self._url(path), params=params, timeout=15)
                resp.raise_for_status()
                text = resp.text.strip()
                if not text:
                    return {"code": -999, "msg": "空响应"}
                return json.loads(text)
            except (requests.ConnectionError, requests.Timeout) as e:
                last_err = e
                if attempt < retries:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
            except json.JSONDecodeError:
                return {"code": -998, "msg": f"非JSON响应: {resp.text[:200]}"}
            except requests.HTTPError as e:
                return {"code": -resp.status_code, "msg": str(e)}
        return {"code": -997, "msg": f"网络错误({retries+1}次重试): {last_err}"}

    def _post(self, path: str, data: dict) -> dict:
        return self._request("POST", path, data=data)

    def _get(self, path: str, params: dict = None) -> dict:
        return self._request("GET", path, params=params)

    def _sub(self, act: str, data: dict = None) -> dict:
        """apisub.php 快捷调用"""
        self._require_login()
        if data:
            return self._post(f"apisub.php?act={act}", data)
        return self._get(f"apisub.php?act={act}")

    def _sb(self, act: str, data: dict = None) -> dict:
        """apisb.php 快捷调用"""
        self._require_login()
        if data:
            return self._post(f"apisb.php?act={act}", data)
        return self._get(f"apisb.php?act={act}")

    def _require_login(self):
        if not self.logged_in:
            raise RuntimeError("请先登录 (调用 login_password 或 login_verify_code)")

    # ═══════════════════════════════════════════
    # apilogin.php — 公开API (7个)
    # ═══════════════════════════════════════════

    def login_password(self, username: str = None, password: str = None) -> dict:
        """密码登录（走apisub.php）
        成功: code=1 | 管理员二次验证: code=5 | 失败: code=-1
        凭据优先级: 参数 > 环境变量 BOOKWK_USER/BOOKWK_PASS
        """
        username = username or os.environ.get("BOOKWK_USER", "")
        password = password or os.environ.get("BOOKWK_PASS", "")
        if not username or not password:
            raise ValueError("需要用户名和密码 (参数或环境变量 BOOKWK_USER/BOOKWK_PASS)")
        result = self._post("apisub.php?act=login", {"user": username, "pass": password})
        if result.get("code") == 1:
            self.logged_in = True
            print(f"[OK] 登录成功: {username}")
        elif result.get("code") == 5:
            print(f"[!] 管理员账户需要二次验证")
        else:
            print(f"[FAIL] 登录失败: {result.get('msg', '未知错误')}")
        return result

    def login_admin_verify(self, username: str, password: str, pass2: str) -> dict:
        """管理员二次验证登录"""
        result = self._post("apisub.php?act=login", {
            "user": username, "pass": password, "pass2": pass2,
        })
        if result.get("code") == 1:
            self.logged_in = True
            print(f"[OK] 管理员登录成功: {username}")
        else:
            print(f"[FAIL] 二次验证失败: {result.get('msg', '未知错误')}")
        return result

    def login_verify_code(self, qq_account: str, verify_code: str) -> dict:
        """验证码登录"""
        result = self._post("apilogin.php?act=verify_login", {
            "account": qq_account, "verify_code": verify_code, "type": "登录",
        })
        if result.get("code") == 1:
            self.logged_in = True
            print(f"[OK] 验证码登录成功: {qq_account}")
        else:
            print(f"[FAIL] 验证码登录失败: {result.get('msg', '未知错误')}")
        return result

    def send_verify_code(self, qq_account: str, code_type: str = "登录") -> dict:
        """发送验证码到QQ邮箱 (type: '登录'|'注册', 成功: code=1, expire_time=300)"""
        result = self._post("apilogin.php?act=send_verify_code", {
            "account": qq_account, "type": code_type,
        })
        if result.get("code") == 1:
            print(f"[OK] 验证码已发送到 {qq_account}@qq.com (有效期{result.get('expire_time', 300)}秒)")
        else:
            print(f"[FAIL] 发送失败: {result.get('msg', '未知错误')}")
        return result

    def register(self, name: str, qq_account: str, password: str,
                 invite_code: str, verify_code: str = "") -> dict:
        """用户注册 (account: QQ号5-11位, password: >=6位, invite_code: 必填)"""
        if len(password) < 6:
            return {"code": -1, "msg": "密码长度至少6位"}
        return self._post("apilogin.php?act=register", {
            "name": name, "account": qq_account, "password": password,
            "verify_code": verify_code, "invite_code": invite_code,
        })

    def find_account(self, qq_number: str) -> dict:
        """通过QQ号查找账号（找回密码第一步）"""
        return self._post("apilogin.php?act=find_account", {"qq_number": qq_number})

    def send_reset_verify_code(self, qq_number: str) -> dict:
        """发送重置密码验证码"""
        return self._post("apilogin.php?act=send_reset_verify_code", {"qq_number": qq_number})

    def reset_password(self, qq_number: str, verify_code: str, new_password: str) -> dict:
        """重置密码"""
        return self._post("apilogin.php?act=reset_password", {
            "qq_number": qq_number, "verify_code": verify_code, "new_password": new_password,
        })

    # ═══════════════════════════════════════════
    # apisub.php — 分站业务API (真实act名，已验证)
    # ═══════════════════════════════════════════

    # --- home.php: 用户/首页 ---
    def get_user_info(self) -> dict:
        """✅ 已验证: 返回 uid/user/money/addprice/sjuser/dd/zcz 等"""
        return self._sub("userinfo")

    def set_user_notice(self) -> dict:
        """✅ 已验证"""
        return self._sub("user_notice")

    def set_yqprice(self, price: str) -> dict:
        """设置邀请费率 (必须为数字)"""
        return self._sub("yqprice", {"price": price})

    def ktapi(self, **kwargs) -> dict:
        """开通API"""
        return self._sub("ktapi", kwargs)

    # --- userlist.php: 用户管理 ---
    def get_user_list(self, page: int = 1) -> dict:
        """✅ 已验证: 返回 data/current_page/last_page"""
        return self._sub("userlist")

    def get_agent_levels(self) -> dict:
        """✅ 已验证: 返回代理等级列表 [{sort,name,rate}]"""
        return self._sub("adddjlist")

    def add_user(self, **kwargs) -> dict:
        """添加用户 (所有项目不能为空)"""
        return self._sub("adduser", kwargs)

    def set_invite_code(self, yqm: str) -> dict:
        """设置邀请码 (最少4位数字)"""
        return self._sub("szyqm", {"yqm": yqm})

    def ban_user(self, user_id: str) -> dict:
        """封禁用户 (需有权限)"""
        return self._sub("user_ban", {"uid": user_id})

    def reset_user_password(self, user_id: str) -> dict:
        """重置用户密码"""
        return self._sub("user_czmm", {"uid": user_id})

    def set_user_rate(self, user_id: str, rate: str) -> dict:
        """修改下级用户费率"""
        return self._sub("usergj", {"uid": user_id, "rate": rate})

    def recharge_user(self, user_id: str, money: str) -> dict:
        """给用户充值"""
        return self._sub("userjk", {"uid": user_id, "money": money})

    def deduct_user(self, user_id: str, money: str) -> dict:
        """扣除用户余额"""
        return self._sub("userkc", {"uid": user_id, "money": money})

    # --- add.php: 课程/下单 ---
    def get_courses(self) -> dict:
        """✅ 已验证: 返回课程列表 [{cid,name,noun,price,content,status,miaoshua}]"""
        return self._sub("getclass")

    def get_courses_with_filter(self) -> dict:
        """✅ 已验证: 返回课程(含nocheck字段)"""
        return self._sub("getclassfl")

    def get_category_info(self, cid: str) -> dict:
        """获取课程分类详情"""
        return self._sub("getCategoryInfo", {"cid": cid})

    def get_favorites(self) -> dict:
        """✅ 已验证: 获取收藏列表"""
        return self._sub("getFavorites")

    def toggle_favorite(self, cid: str) -> dict:
        """切换收藏状态"""
        return self._sub("toggleFavorite", {"cid": cid})

    def submit_order(self, **kwargs) -> dict:
        """提交订单 (需要: cid + 学生账号密码等)"""
        return self._sub("add", kwargs)

    def get_order(self, **kwargs) -> dict:
        """查询订单 (需要验证token)"""
        return self._sub("get", kwargs)

    # --- log.php: 日志 ---
    def get_logs(self, page: int = 1) -> dict:
        """✅ 已验证: 返回 data/current_page/last_page"""
        return self._sub("loglist")

    # --- charge.php: 充值 ---
    def pay(self, money: str) -> dict:
        """充值/支付"""
        return self._sub("pay", {"money": money})

    # ═══════════════════════════════════════════
    # apisb.php — 系统管理API (需登录)
    # ═══════════════════════════════════════════

    def get_help_list(self) -> dict:
        """✅ 已验证: 返回帮助文档 [{id,title,content,sort,status}]"""
        return self._sb("help_list")

    def send_qq_verify(self, qq: str) -> dict:
        """发送QQ验证码(管理)"""
        return self._sb("send_qq_verify_code", {"qq": qq})

    def update_qq_number(self, qq: str, code: str) -> dict:
        """更新QQ号"""
        return self._sb("update_qq_number", {"qq": qq, "code": code})

    def check_version(self) -> dict:
        return self._sb("check_version")

    def check_tables(self) -> dict:
        return self._sb("check_tables")

    def get_standard_tables(self) -> dict:
        return self._sb("get_standard_tables")

    def calibrate_db(self) -> dict:
        return self._sb("calibrate")

    def get_system_log(self) -> dict:
        return self._sb("get_log")

    def get_system_info(self) -> dict:
        return self._sb("get_system_info")

    def get_php_info(self) -> dict:
        return self._sb("get_php_info")

    def clear_cache(self) -> dict:
        return self._sb("clear_cache")

    def backup_db(self) -> dict:
        return self._sb("backup_db")

    def restore_db(self, **kwargs) -> dict:
        return self._sb("restore_db", kwargs)

    def update_system(self) -> dict:
        return self._sb("update_system")

    def run_sql(self, sql: str) -> dict:
        return self._sb("run_sql", {"sql": sql})

    # ═══════════════════════════════════════════
    # 便捷方法
    # ═══════════════════════════════════════════

    def probe_all_public(self) -> dict:
        """探测所有公开API端点，返回状态汇总"""
        results = {}
        for path in ["apilogin.php", "apisub.php", "apisb.php",
                      "api/", "install/", "index/"]:
            try:
                resp = self.session.get(self._url(path), allow_redirects=False, timeout=10)
                results[path] = {
                    "status": resp.status_code,
                    "size": len(resp.content),
                    "redirect": resp.headers.get("Location"),
                }
            except Exception as e:
                results[path] = {"error": str(e)}
        return results

    def full_status(self) -> dict:
        """登录后获取完整站点状态（全部已验证的API）"""
        self._require_login()
        status = {}
        for name, func in [
            ("userinfo", self.get_user_info),
            ("userlist", self.get_user_list),
            ("courses", self.get_courses),
            ("courses_fl", self.get_courses_with_filter),
            ("favorites", self.get_favorites),
            ("agent_levels", self.get_agent_levels),
            ("logs", self.get_logs),
            ("help", self.get_help_list),
            ("user_notice", self.set_user_notice),
        ]:
            try:
                status[name] = func()
            except Exception as e:
                status[name] = {"error": str(e)}
        return status

    def call(self, act: str, api: str = "sub", **kwargs) -> dict:
        """通用调用：api='sub'|'sb'|'login', act=端点名, **kwargs=参数"""
        self._require_login()
        endpoint = {"sub": "apisub", "sb": "apisb", "login": "apilogin"}[api]
        if kwargs:
            return self._post(f"{endpoint}.php?act={act}", kwargs)
        return self._get(f"{endpoint}.php?act={act}")


def _pp(data: Any):
    """格式化打印JSON"""
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if len(text) > 5000:
        print(text[:5000] + "\n  ... (truncated)")
    else:
        print(text)


def interactive_cli():
    """交互式命令行界面"""
    client = BookWKClient()
    print("=" * 60)
    print("  BookWK 网课管理平台 — API客户端 v2")
    print(f"  站点: {client.base_url}")
    env_user = os.environ.get("BOOKWK_USER", "")
    if env_user:
        print(f"  预设账号: {env_user}")
    print("=" * 60)

    COMMANDS = {
        "probe":     ("探测公开端点", None),
        "login":     ("密码登录", None),
        "vlogin":    ("验证码登录", None),
        "code":      ("发送验证码", None),
        "reg":       ("注册账号", None),
        "find":      ("QQ查找账号", None),
        "status":    ("完整站点状态(9个API)", "login"),
        "user":      ("✅ 当前用户信息", "login"),
        "users":     ("✅ 用户列表", "login"),
        "courses":   ("✅ 课程列表", "login"),
        "coursesfl": ("✅ 课程列表(含filter)", "login"),
        "favs":      ("✅ 收藏列表", "login"),
        "levels":    ("✅ 代理等级", "login"),
        "logs":      ("✅ 日志列表", "login"),
        "help":      ("✅ 帮助文档", "login"),
        "version":   ("系统版本", "login"),
        "tables":    ("数据库表检查", "login"),
        "sysinfo":   ("系统信息", "login"),
        "call":      ("通用API调用(任意act)", "login"),
    }

    while True:
        print("\n可用命令:")
        for cmd, (desc, _) in COMMANDS.items():
            print(f"  {cmd:10s} — {desc}")
        print(f"  {'exit':10s} — 退出")

        cmd = input("\n> ").strip().lower()
        try:
            if cmd in ("exit", "quit", "q"):
                break
            elif cmd == "probe":
                _pp(client.probe_all_public())
            elif cmd == "login":
                user = input("用户名/QQ号: ").strip()
                pwd = input("密码: ").strip()
                _pp(client.login_password(user, pwd))
            elif cmd == "vlogin":
                qq = input("QQ号: ").strip()
                code = input("验证码: ").strip()
                _pp(client.login_verify_code(qq, code))
            elif cmd == "code":
                qq = input("QQ号: ").strip()
                t = input("类型(登录/注册)[登录]: ").strip() or "登录"
                _pp(client.send_verify_code(qq, t))
            elif cmd == "reg":
                name = input("姓名: ").strip()
                qq = input("QQ号: ").strip()
                pwd = input("密码: ").strip()
                inv = input("邀请码: ").strip()
                vc = input("验证码(可留空): ").strip()
                _pp(client.register(name, qq, pwd, inv, vc))
            elif cmd == "find":
                _pp(client.find_account(input("QQ号: ").strip()))
            elif cmd == "status":
                _pp(client.full_status())
            elif cmd == "user":
                _pp(client.get_user_info())
            elif cmd == "users":
                _pp(client.get_user_list())
            elif cmd == "courses":
                _pp(client.get_courses())
            elif cmd == "coursesfl":
                _pp(client.get_courses_with_filter())
            elif cmd == "favs":
                _pp(client.get_favorites())
            elif cmd == "levels":
                _pp(client.get_agent_levels())
            elif cmd == "logs":
                _pp(client.get_logs())
            elif cmd == "help":
                _pp(client.get_help_list())
            elif cmd == "version":
                _pp(client.check_version())
            elif cmd == "tables":
                _pp(client.check_tables())
            elif cmd == "sysinfo":
                _pp(client.get_system_info())
            elif cmd == "call":
                act = input("act名称: ").strip()
                api = input("API(sub/sb/login)[sub]: ").strip() or "sub"
                _pp(client.call(act, api))
            else:
                print(f"未知命令: {cmd}")
        except Exception as e:
            print(f"[ERROR] {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--probe":
        client = BookWKClient()
        _pp(client.probe_all_public())
    elif len(sys.argv) > 1 and sys.argv[1] == "--status":
        client = BookWKClient()
        client.login_password()
        _pp(client.full_status())
    else:
        interactive_cli()
