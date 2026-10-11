#!/usr/bin/env python3
"""workbuddy-limit 菜单栏 App（rumps 版）

常驻 macOS 菜单栏，实时显示 WorkBuddy 积分剩余额度。
数据链路：无头 Chrome（持久化登录 profile）→ workbuddy.cn 积分接口 → 本地缓存。
登录过期时点「重新登录（扫码）」，在弹出的浏览器窗口里扫码即可。
"""
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import webbrowser

# ── 路径（全部相对本文件解析，项目可放在任意目录） ───────────────────────────

_HOME = pathlib.Path.home()
_APP_DIR = pathlib.Path(__file__).resolve().parent

# 依赖（rumps / pyobjc）：优先本项目 ./vendor（离线、免安装），
# 否则使用 setup.sh 建好的虚拟环境里 pip 安装的包。
_VENDOR = _APP_DIR / "vendor"
if _VENDOR.is_dir():
    sys.path.insert(0, str(_VENDOR))

try:
    import rumps
except ModuleNotFoundError as exc:  # 依赖缺失时给出明确指引，而不是丢一堆栈
    raise SystemExit(
        "缺少依赖 rumps —— 请先在项目目录执行 ./setup.sh（见 README.md「安装」）。"
    ) from exc

_FETCH_JS = _APP_DIR / "wb_fetch.js"
_LOGIN_JS = _APP_DIR / "wb_login.js"
_ICON = _APP_DIR / "menubar-icon.png"

# 运行数据（缓存、登录 profile）放在项目外，避免登录态被误提交进仓库
_DATA_DIR = _HOME / ".workbuddy-limit"
_CACHE_PATH = _DATA_DIR / "credits-cache.json"
_PROFILE_DIR = _DATA_DIR / "profile"
_STATE_PATH = _HOME / ".workbuddy-limit-menubar.json"

_LAUNCH_AGENT_LABEL = "com.zc790-hub.workbuddy-limit"
_LAUNCH_AGENT_PLIST = _HOME / "Library/LaunchAgents" / f"{_LAUNCH_AGENT_LABEL}.plist"

_REFRESH_MINS = (1, 2, 5, 10, 30)
_SUB_PAGE = "https://www.workbuddy.cn/app"

# node 依赖搜索路径：① 项目本地 node_modules（setup.sh 里 npm install 装的）
# ② 兜底：WorkBuddy 自带的托管 node workspace（历史安装沿用）
_LEGACY_NODE_MODULES = _HOME / ".workbuddy/binaries/node/workspace/node_modules"


def _node_modules_env():
    paths = [p for p in (_APP_DIR / "node_modules", _LEGACY_NODE_MODULES) if p.is_dir()]
    return ":".join(str(p) for p in paths)


def _js_env():
    """Node 子进程环境：注入 node_modules 搜索路径与持久化 profile 目录。"""
    env = dict(os.environ)
    node_modules = _node_modules_env()
    if node_modules:
        env["NODE_PATH"] = node_modules
    env.setdefault("WB_LIMIT_PROFILE", str(_PROFILE_DIR))
    return env


def _version_key(name):
    """把版本目录名转成可比较的元组，如 '22.22.2-6' -> (22, 22, 2, 6)。"""
    parts = []
    for seg in str(name).replace("-", ".").split("."):
        parts.append(int(seg) if seg.isdigit() else -1)
    return tuple(parts)


def _resolve_node():
    """返回可用的 node 可执行文件路径；找不到返回 None。

    三重兜底，不再写死版本号（WorkBuddy 托管 node 升级后旧路径会消失）：
    ① 系统 PATH；② ~/.workbuddy/binaries/node/versions/*/bin/node，取版本最高者；
    ③ 常见安装位置。
    """
    found = shutil.which("node")
    if found and os.access(found, os.X_OK):
        return found
    cands = []
    versions_dir = _HOME / ".workbuddy/binaries/node/versions"
    if versions_dir.is_dir():
        for d in versions_dir.iterdir():
            b = d / "bin" / "node"
            if b.exists() and os.access(b, os.X_OK):
                cands.append((_version_key(d.name), str(b)))
    for p in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node"):
        if os.path.exists(p) and os.access(p, os.X_OK):
            cands.append(((0,), p))
    if cands:
        cands.sort(key=lambda t: t[0], reverse=True)
        return cands[0][1]
    return None


_NODE = _resolve_node()


def _node_path():
    """取用前校验 node；路径失效（如托管版本升级）则自动重新解析。"""
    global _NODE
    if not _NODE or not os.access(_NODE, os.X_OK):
        _NODE = _resolve_node()
    return _NODE

TZ_LOCAL = datetime.datetime.now().astimezone().tzinfo

# ── 状态 / 缓存 ──────────────────────────────────────────────────────────────

def _load_state():
    state = {"refresh_min": 5}
    try:
        raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and raw.get("refresh_min") in _REFRESH_MINS:
            state["refresh_min"] = raw["refresh_min"]
    except Exception:
        pass
    return state


def _save_state(state):
    try:
        _STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


def _load_cache():
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(data):
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data["fetched_epoch"] = datetime.datetime.now(TZ_LOCAL).timestamp()
        _CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass

# ── 开机自启 ─────────────────────────────────────────────────────────────────

def _login_item_enabled():
    return _LAUNCH_AGENT_PLIST.exists()


def _set_login_item(enabled: bool):
    if enabled:
        _LAUNCH_AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)
        _LAUNCH_AGENT_PLIST.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/Property-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_LAUNCH_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{pathlib.Path(__file__).resolve()}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{_APP_DIR}</string>
    <key>StandardOutPath</key>
    <string>{_APP_DIR / "app.log"}</string>
    <key>StandardErrorPath</key>
    <string>{_APP_DIR / "app.log"}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
""",
            encoding="utf-8",
        )
    else:
        try:
            _LAUNCH_AGENT_PLIST.unlink()
        except FileNotFoundError:
            pass

# ── 数据抓取 ─────────────────────────────────────────────────────────────────

def _parse_summary(raw_text):
    data = json.loads(raw_text)
    if data.get("code") != 0:
        raise ValueError(data.get("msg") or f"code={data.get('code')}")
    pkgs = []
    for p in (data.get("data") or {}).get("Packages") or []:
        total = float(p.get("CycleTotalCapacity") or 0)
        remain = float(p.get("CycleRemainCapacity") or 0)
        if total <= 0:
            continue
        pkgs.append({"remain": remain, "total": total, "pct": round(remain / total * 100, 1)})
    total_all = sum(p["total"] for p in pkgs)
    remain_all = sum(p["remain"] for p in pkgs)
    pct_all = round(remain_all / total_all * 100, 1) if total_all else 0.0
    return {"pkgs": pkgs, "remain": remain_all, "total": total_all, "pct": pct_all,
            "fetched_at": datetime.datetime.now(TZ_LOCAL).strftime("%H:%M:%S")}


def _fetch_blocking():
    """跑一次 node wb_fetch.js，返回解析后的积分 dict；失败抛异常。"""
    node = _node_path()
    if not node:
        raise RuntimeError("未找到可用的 node 运行时（PATH 与 ~/.workbuddy 托管目录均无）")
    env = _js_env()
    proc = subprocess.run(
        [node, str(_FETCH_JS)],
        capture_output=True, text=True, timeout=120, env=env, cwd=str(_APP_DIR),
    )
    out = (proc.stdout or "").strip()
    if proc.returncode == 2 or out == "NEED_LOGIN":
        raise PermissionError("登录过期")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or out or "unknown").strip()[:120])
    return _parse_summary(out)

# ── App ──────────────────────────────────────────────────────────────────────

def _inert(item):
    item.set_callback(None)
    return item


class WorkBuddyLimitApp(rumps.App):
    def __init__(self):
        super().__init__("WB …", icon=str(_ICON), template=True, quit_button=None)
        self.state = _load_state()
        self._pending = None
        self._fetching = False
        self._login_expired = False

        self._header = _inert(rumps.MenuItem("WorkBuddy 积分"))
        self._total = _inert(rumps.MenuItem("  总额度  …"))
        self._pkg_items = [_inert(rumps.MenuItem(f"  额度包{i+1}  …")) for i in range(3)]
        self._updated = _inert(rumps.MenuItem("  更新于 …"))

        self._rate_menu = rumps.MenuItem("刷新频率")
        self._rate_items = {}
        for m in _REFRESH_MINS:
            it = rumps.MenuItem(f"{m} 分钟", callback=self._make_set_rate(m))
            self._rate_items[m] = it
            self._rate_menu.add(it)

        self._refresh_item = rumps.MenuItem("立即刷新", callback=self._on_force_refresh)
        self._login_state = _inert(rumps.MenuItem("登录状态: …"))
        self._login_btn = rumps.MenuItem("重新登录（扫码）", callback=self._on_relogin)
        self._open_page = rumps.MenuItem("打开 WorkBuddy", callback=self._on_open_page)
        self._autostart_item = rumps.MenuItem("开机自启", callback=self._on_toggle_autostart)
        self._about = _inert(rumps.MenuItem("workbuddy-limit · 数据来自 workbuddy.cn 积分接口"))
        self._quit_item = rumps.MenuItem("退出", callback=rumps.quit_application)

        self.menu = [
            self._header, self._total, *self._pkg_items, self._updated,
            None,
            self._rate_menu, self._refresh_item,
            None,
            self._login_state, self._login_btn, self._open_page, self._autostart_item,
            None,
            self._about, self._quit_item,
        ]
        self._update_rate_checks()
        self._update_autostart_check()
        # 启动即异步刷新一次，避免首屏显示过期缓存（首屏先渲染缓存，随后被新数据替换）
        self._kick_background_fetch()

    # 渲染 ────────────────────────────────────────────────────────────────
    def _render(self):
        self._login_state.title = "登录状态: ❌ 已过期（点下方重新扫码）" if self._login_expired else "登录状态: ✅ 正常"
        d = self._pending
        if d is None:
            self.title = "WB …"
            return
        if d.get("error"):
            self.title = "WB ⚠️"
            self._total.title = "  " + d["error"]
            self._updated.title = "  更新于 …"
            return
        pct = d.get("pct", 0)
        remain = d.get("remain", 0)
        remain_show = round(remain, 1)
        if remain_show == int(remain_show):
            remain_show = int(remain_show)
        self.title = f"{remain_show:g}"
        self._total.title = f"  总额度  {d['remain']:g} / {d['total']:g}（{pct:g}%）"
        pkgs = d.get("pkgs") or []
        for i, item in enumerate(self._pkg_items):
            if i < len(pkgs):
                p = pkgs[i]
                item.title = f"  额度包{i+1}  {p['remain']:g} / {p['total']:g}（{p['pct']:g}%）"
                item.hidden = False
            else:
                item.hidden = True
        self._updated.title = f"  更新于 {d.get('fetched_at', '?')}"

    @rumps.timer(0.3)
    def _init_render(self, _):
        # 仅在尚无数据时用缓存做首屏渲染；不要覆盖已抓取的数据或错误状态，
        # 否则抓取失败会被旧缓存静默掩盖（表现为数字卡死、无报错）。
        if self._pending is None:
            cached = _load_cache()
            if cached and "pct" in cached:
                self._pending = cached
        self._render()

    @rumps.timer(0.4)
    def _apply_pending(self, _):
        self._render()

    # 刷新 ────────────────────────────────────────────────────────────────
    def _kick_background_fetch(self):
        if self._fetching:
            return
        self._fetching = True
        threading.Thread(target=self._async_refresh, daemon=True).start()

    def _async_refresh(self):
        self._login_expired = False
        try:
            data = _fetch_blocking()
            _save_cache(data)
            self._pending = data
        except PermissionError:
            self._login_expired = True
            self._pending = {"error": "登录已过期，点下方「重新登录（扫码）」"}
        except Exception as e:
            self._pending = {"error": f"获取失败: {e}"}
        finally:
            self._fetching = False

    @rumps.timer(60)
    def _auto_refresh(self, _):
        cache = _load_cache() or {}
        last = cache.get("fetched_epoch") or 0
        now = datetime.datetime.now(TZ_LOCAL).timestamp()
        if now - last >= self.state["refresh_min"] * 60 - 5:
            self._kick_background_fetch()

    # 菜单事件 ────────────────────────────────────────────────────────────
    def _on_force_refresh(self, _):
        self._kick_background_fetch()

    def _make_set_rate(self, minutes):
        def cb(_):
            self.state["refresh_min"] = minutes
            _save_state(self.state)
            self._update_rate_checks()
        return cb

    def _update_rate_checks(self):
        for m, it in self._rate_items.items():
            it.state = 1 if m == self.state["refresh_min"] else 0

    def _on_toggle_autostart(self, _):
        enabled = not _login_item_enabled()
        _set_login_item(enabled)
        self._update_autostart_check()

    def _update_autostart_check(self):
        self._autostart_item.state = 1 if _login_item_enabled() else 0

    def _on_open_page(self, _):
        webbrowser.open(_SUB_PAGE)

    def _on_relogin(self, _):
        rumps.notification("workbuddy-limit", "", "正在打开浏览器，请在窗口中扫码登录 WorkBuddy")
        def run():
            try:
                node = _node_path()
                if node:
                    subprocess.run(
                        [node, str(_LOGIN_JS)],
                        capture_output=True, timeout=300,
                        env=_js_env(), cwd=str(_APP_DIR),
                    )
            except Exception:
                pass
            self._kick_background_fetch()
        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    WorkBuddyLimitApp().run()
