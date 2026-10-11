# workbuddy-limit

> 把 **WorkBuddy**（腾讯 CodeBuddy）的剩余积分放到 macOS 菜单栏——抬眼就能看到，不用开网页。

菜单栏常驻一个小图标，实时显示积分余额；点开能看到总额度、每个额度包的余量与百分比、上次刷新时间，支持扫码重新登录和开机自启。

```
菜单栏            ┌─────────────────────────────┐
  2846.3   ───▶  │ WorkBuddy 积分               │
                 │   总额度  2846.3 / 10000 (28.5%) │
                 │   额度包1  1000 / 2000 (50%)     │
                 │   额度包2  136.3 / 3000 (4.5%)   │
                 │   额度包3  1710 / 5000 (34.2%)   │
                 │   更新于 09:15:00            │
                 ├─────────────────────────────┤
                 │ 刷新频率          ▶ 1 分钟   │
                 │ 立即刷新                     │
                 │ 登录状态: ✅ 正常            │
                 │ 重新登录（扫码）             │
                 │ 开机自启                     │
                 └─────────────────────────────┘
```

## 特性

- **菜单栏直接显示余额**，不需要点开
- 下拉菜单给出总额度 + 每个额度包的明细（余量 / 总量 / 百分比）
- 刷新频率可选 1 / 2 / 5 / 10 / 30 分钟，也可手动「立即刷新」
- 登录过期时一键弹出浏览器**扫码**重新登录
- 「开机自启」开关（写一个 LaunchAgent，登录时自动拉起）
- 抓取失败会明确显示 ⚠️ 和原因，不会拿旧数据冒充最新

## 环境要求

- macOS
- Python 3
- Node.js（跑抓取脚本）
- Chromium 内核浏览器（系统装了 Google Chrome 就行）

## 安装

```bash
git clone https://github.com/<your-name>/workbuddy-limit.git
cd workbuddy-limit
./setup.sh     # 建 .venv + 装 rumps/pyobjc + npm install
./run.sh       # 启动菜单栏挂件
```

首次启动菜单栏显示 `WB …`，点开菜单 → **「重新登录（扫码）」** → 在弹出来的浏览器窗口里扫码登录 WorkBuddy，登录态会存进本地 profile，之后自动刷新。

想让它常驻：菜单里勾选 **「开机自启」**；想双击启动可以直接开 `WorkBuddyLimit.app`。

### 浏览器路径

默认自动探测，按顺序尝试：

1. 环境变量 `WB_LIMIT_CHROME`
2. Chrome for Testing —— 扫 `~/.agent-browser/browsers`、playwright 缓存，取版本最高的一个
3. 系统浏览器 —— Google Chrome / Chromium / Microsoft Edge / Brave
4. playwright-core 登记的浏览器

想手动指定：`WB_LIMIT_CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ./run.sh`

## 工作原理

```
workbuddy-limit.py  (rumps 菜单栏)
        │  每 N 分钟触发
        ▼
   node wb_fetch.js   ← 无头 Chrome + 持久化 profile
        │  打开 workbuddy.cn/app，用页面内 fetch 调积分接口
        │  POST /billing/meter/get-user-resource-summary
        ▼
~/.workbuddy-limit/credits-cache.json   ← 本地缓存
        │
        ▼
   菜单栏渲染余额
```

- 登录态存在 `~/.workbuddy-limit/profile`（一个独立的浏览器 profile，**不动你日常用的 Chrome**）
- 状态文件 `~/.workbuddy-limit-menubar.json`（记录刷新频率）
- 抓取失败会把错误原因写进缓存状态并在菜单里显示

## 隐私

- **所有数据都在本机**：没有账号系统、没有服务器、没有遥测，不做任何上传
- 代码**不读取密码、不保存 token**，登录态只以浏览器 profile 的形式留在本地
- 缓存和 profile 都放在 `~/.workbuddy-limit/`（项目目录之外），不会被误提交进仓库

## 免责声明

本项目为个人非官方工具，与腾讯 / WorkBuddy / CodeBuddy 无任何关联或背书。

它只做一件事：**读取你自己账号的余额**并显示出来。不做签到、不刷积分、不转发账号、不提供任何接口代理。产品内部接口可能随时变更，若接口调整导致失效，属于预期内的风险。

## 已知限制

- 只支持 macOS（依赖 rumps / pyobjc）
- 额度包固定展示最多 3 个（跟随账号实际返回）
- 首次运行需要手动扫码登录一次

## License

[MIT](LICENSE)
