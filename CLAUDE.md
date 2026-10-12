# CLAUDE.md — workbuddy-limit

macOS 菜单栏挂件：rumps 菜单栏 + 无头 Chrome 抓 `workbuddy.cn` 积分接口。主程序 `workbuddy-limit.py`（约 400 行，单文件）。

## 红线（违反会出事）

- ⛔ **README / 截图 / 日志里绝不出现真实积分数值**——示例一律用虚构值（如 `2846.3 / 10000`）。曾被真实余额污染过一次并重写历史清除，勿重演。
- ⛔ **不提交 token / cookie / 浏览器 profile / 缓存**：它们都在 `~/.workbuddy-limit/`（项目目录之外）。新增文件前先确认 `.gitignore` 覆盖得到。
- ⛔ **不硬编码 node / Chrome 的版本化路径**——托管运行时升级会换目录（`22.22.2-3` → `-6`），写死会静默失败且进程照常活着（同一坑踩过两次）。一律走 `_resolve_node()` 和 `chrome.js` 的运行时探测。

## 推送到 GitHub

本仓库已 `--local` 固化代理，直接 `git push` 即可。换机器时需带：
`https_proxy=http://127.0.0.1:7897 git -c http.version=HTTP/1.1 push`
（直连 github.com 被墙；HTTP/2 经该代理数据不回流。）

## 结构

| 文件 | 职责 |
|---|---|
| `workbuddy-limit.py` | 主程序：菜单栏渲染 + 抓取调度 + 缓存 |
| `wb_fetch.js` / `wb_login.js` | 无头 Chrome 脚本，经 `chrome.js` 取浏览器可执行文件 |
| `chrome.js` | 浏览器探测（`WB_LIMIT_CHROME` → Chrome for Testing → 系统浏览器） |
| `setup.sh` / `run.sh` | 安装 / 启动 |

运行期数据（缓存、profile、状态文件）全在 `~/.workbuddy-limit/`，**不在项目内**。
