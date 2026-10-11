// chrome.js —— 解析 Chromium 可执行文件与持久化 profile 目录（多处兜底）
//
// 为什么需要：无头抓取要一个 Chromium 内核的浏览器。不同机器上它可能在
// Chrome for Testing（agent-browser / playwright 缓存）、系统 Google Chrome、
// 或其它 Chromium 系浏览器里。写死某个版本路径 = 版本一升级就全体挂掉。
//
// 可用环境变量覆盖：
//   WB_LIMIT_CHROME   —— 直接指定浏览器可执行文件
//   WB_LIMIT_PROFILE  —— 持久化 profile 目录（默认 ~/.workbuddy-limit/profile）

const fs = require("fs");
const os = require("os");
const path = require("path");

const HOME = os.homedir();

// 相对每个“浏览器仓库目录”的候选路径模式
const PATTERNS = [
  "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
  "chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
  "chrome-mac/Chromium.app/Contents/MacOS/Chromium",
  "chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium",
  "chrome-linux/chrome",
  "chrome-win/chrome.exe",
];

// 浏览器仓库目录（Chrome for Testing / playwright 下载缓存）
const STORE_DIRS = [
  path.join(HOME, ".agent-browser", "browsers"),
  path.join(HOME, "Library", "Caches", "ms-playwright"),
  path.join(HOME, ".cache", "ms-playwright"),
];

// 系统 / 常见 Chromium 系浏览器
const SYSTEM_BROWSERS = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
];

function versionKey(name) {
  return String(name)
    .replace(/[^0-9.]/g, ".")
    .split(".")
    .filter((s) => s.length)
    .map(Number);
}

// 返回 >0 表示 a 比 b 新
function compareVersion(a, b) {
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i++) {
    const x = a[i] || 0;
    const y = b[i] || 0;
    if (x !== y) return x - y;
  }
  return 0;
}

// 扫描浏览器仓库目录，取版本号最高的一个
function scanStores() {
  const hits = [];
  for (const base of STORE_DIRS) {
    let entries;
    try {
      entries = fs.readdirSync(base);
    } catch (e) {
      continue;
    }
    for (const dir of entries) {
      for (const rel of PATTERNS) {
        const p = path.join(base, dir, rel);
        if (fs.existsSync(p)) hits.push({ v: versionKey(dir), p });
        break;
      }
    }
  }
  hits.sort((a, b) => compareVersion(b.v, a.v));
  return hits.map((h) => h.p);
}

// 依次尝试：环境变量 → agent-browser/playwright 缓存 → 系统浏览器 → playwright 自带登记表
function resolveChrome() {
  const explicit = process.env.WB_LIMIT_CHROME;
  if (explicit && fs.existsSync(explicit)) return explicit;

  const fromStores = scanStores();
  if (fromStores.length) return fromStores[0];

  for (const p of SYSTEM_BROWSERS) {
    if (fs.existsSync(p)) return p;
  }

  // playwright-core 登记的浏览器（装了但不在上面的目录里时兜底）
  try {
    const { chromium } = require("playwright-core");
    const p = chromium.executablePath();
    if (p && fs.existsSync(p)) return p;
  } catch (e) {
    /* 没装 playwright 或没下载浏览器，忽略 */
  }

  return null;
}

const PROFILE =
  process.env.WB_LIMIT_PROFILE ||
  path.join(HOME, ".workbuddy-limit", "profile");

module.exports = { resolveChrome, PROFILE, HOME };
