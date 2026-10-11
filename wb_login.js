// workbuddy-limit 登录助手：弹出可见浏览器，用户扫码后自动等待登录完成
// 用法: node wb_login.js
// 成功（检测到回到 /app）输出 LOGIN_OK；超时输出 LOGIN_TIMEOUT（exit 2）
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
    headless: false,
    viewport: { width: 1100, height: 760 },
    args: ["--no-first-run", "--disable-sync"],
    timeout: 30000,
  });
  const page = await ctx.newPage();
  try {
    await page.goto("https://www.workbuddy.cn/app", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(2000);
    if (!page.url().includes("/login")) {
      console.log("LOGIN_OK");
      return;
    }
    // 登录页：自动点「同意」调出二维码
    try {
      await page.getByRole("button", { name: "同意" }).click({ timeout: 5000 });
    } catch (e) {}
    console.log("WAITING_FOR_SCAN");
    // 最多等 4 分钟，每 2 秒查一次是否已回到 /app
    const deadline = Date.now() + 4 * 60 * 1000;
    while (Date.now() < deadline) {
      await page.waitForTimeout(2000);
      if (page.url().includes("/login")) continue;
      // /app 有时带 query；确认 localStorage loggedIn
      const ok = await page.evaluate(() => localStorage.getItem("loggedIn") === "1" || !location.href.includes("/login")).catch(() => false);
      if (ok) {
        console.log("LOGIN_OK");
        return;
      }
    }
    console.log("LOGIN_TIMEOUT");
    process.exitCode = 2;
  } finally {
    await ctx.close().catch(() => {});
  }
})().catch((e) => {
  console.error("ERR " + String(e.message || e).slice(0, 200));
  process.exit(3);
});
