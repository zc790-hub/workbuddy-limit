// workbuddy-limit 数据抓取：用持久化 profile 的无头 Chrome 调 WorkBuddy 积分接口
// 用法: node wb_fetch.js
// 输出: 积分 JSON（成功） / NEED_LOGIN（登录过期, exit 2） / ERR ...（exit 3）
const { chromium } = require("playwright-core");
const { resolveChrome, PROFILE } = require("./chrome");

(async () => {
  const executablePath = resolveChrome();
  if (!executablePath) {
    console.error(
      "ERR 未找到可用的 Chrome/Chromium。请安装 Google Chrome，" +
        "或用 WB_LIMIT_CHROME 指定浏览器可执行文件路径。"
    );
    process.exit(3);
  }
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    executablePath,
    headless: true,
    args: ["--no-first-run", "--disable-sync", "--disable-extensions", "--mute-audio"],
    timeout: 30000,
  });
  try {
    const page = await ctx.newPage();
    await page.goto("https://www.workbuddy.cn/app", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(2500);
    if (page.url().includes("/login")) {
      console.log("NEED_LOGIN");
      process.exitCode = 2;
      return;
    }
    const data = await page.evaluate(async () => {
      const r = await fetch("/billing/meter/get-user-resource-summary", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      return await r.text();
    });
    console.log(data);
  } finally {
    await ctx.close().catch(() => {});
  }
})().catch((e) => {
  console.error("ERR " + String(e.message || e).slice(0, 200));
  process.exit(3);
});
