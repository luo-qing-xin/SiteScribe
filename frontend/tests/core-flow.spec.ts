import { expect, test, type Page } from "@playwright/test";

const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64");
async function login(page: Page) {
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.waitForURL("**/", { waitUntil: "domcontentloaded" });
}
function wavFixture() {
  const samples = 3200; const dataSize = samples * 2; const buffer = Buffer.alloc(44 + dataSize);
  buffer.write("RIFF", 0); buffer.writeUInt32LE(36 + dataSize, 4); buffer.write("WAVE", 8); buffer.write("fmt ", 12);
  buffer.writeUInt32LE(16, 16); buffer.writeUInt16LE(1, 20); buffer.writeUInt16LE(1, 22); buffer.writeUInt32LE(16000, 24);
  buffer.writeUInt32LE(32000, 28); buffer.writeUInt16LE(2, 32); buffer.writeUInt16LE(16, 34); buffer.write("data", 36); buffer.writeUInt32LE(dataSize, 40);
  return buffer;
}

test("登录到现场记录并创建关联待办", async ({ page, context }) => {
  const taskTitle = `E2E 检查待办 ${Date.now()}`;
  await context.grantPermissions(["geolocation"], { origin: "http://127.0.0.1:3100" });
  await context.setGeolocation({ latitude: 23.1291, longitude: 113.2644, accuracy: 9 });
  await page.goto("/login");
  const loginRequest = page.waitForRequest((request) => new URL(request.url()).pathname === "/api/auth/login");
  await login(page);
  expect(new URL((await loginRequest).url()).origin).toBe("http://127.0.0.1:3100");
  await expect(page.getByText("海悦花园项目").first()).toBeVisible();
  await page.getByRole("link", { name: "新建现场记录" }).click();
  await page.getByLabel("现场描述").fill("E2E 现场记录：3号楼六层西侧检查完成。");
  await page.getByRole("button", { name: "获取当前位置" }).click();
  await expect(page.getByText(/定位成功/)).toBeVisible();
  await page.getByLabel("楼栋").selectOption({ label: "3号楼" });
  await page.getByLabel("楼层").selectOption({ label: "6层" });
  await page.getByLabel("区域").selectOption({ label: "西侧" });
  await page.locator('input[type="file"]').setInputFiles({ name: "site.png", mimeType: "image/png", buffer: png });
  await page.getByRole("button", { name: "保存现场记录" }).click();
  await expect(page.getByText("现场记录已保存")).toBeVisible();
  await page.getByRole("link", { name: "创建待办" }).click();
  await page.getByLabel("待办标题").fill(taskTitle);
  await page.getByLabel("待办描述").fill("复核记录中描述的现场情况。");
  await page.getByLabel("责任人").selectOption({ label: "王强 · 施工员" });
  await page.getByRole("button", { name: "保存待办" }).click();
  await expect(page.getByText("待办已创建")).toBeVisible();
  await page.getByRole("link", { name: /返回待办中心/ }).click();
  await expect(page.getByText(taskTitle)).toBeVisible();
});

test("375px 手机页面无横向溢出且触控区域足够", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/login");
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    controls: [...document.querySelectorAll("button,input")].map((item) => item.getBoundingClientRect().height),
  }));
  expect(dimensions.viewport).toBe(375);
  expect(dimensions.document).toBe(375);
  expect(Math.min(...dimensions.controls)).toBeGreaterThanOrEqual(44);
  await login(page);
  await expect(page.locator("nav.fixed")).toBeVisible();
  const home = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    bottomNav: document.querySelector("nav.fixed")?.getBoundingClientRect().height ?? 0,
  }));
  expect(home.document).toBeLessThanOrEqual(home.viewport);
  expect(home.bottomNav).toBeGreaterThanOrEqual(56);
});

test("1440×900 录屏首屏展示品牌、采集入口、指标与证据闭环", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/login");
  await login(page);
  const targets = [
    page.getByRole("heading", { name: "现场说一次，资料自动成" }),
    page.getByRole("link", { name: "新建现场记录" }),
    page.getByRole("region", { name: "项目关键指标" }),
    page.getByRole("heading", { name: "一条现场事实，驱动完整工作闭环" }),
  ];
  for (const target of targets) {
    await expect(target).toBeVisible();
    const box = await target.boundingBox();
    expect(box && box.y + box.height).toBeLessThanOrEqual(900);
  }
});

test("拒绝定位后仍可继续填写", async ({ page, context }) => {
  await context.clearPermissions();
  await page.goto("/login");
  await login(page);
  await expect(page.getByText("海悦花园项目").first()).toBeVisible();
  await page.goto("/records/new");
  await page.getByRole("button", { name: "获取当前位置" }).click();
  await expect(page.getByText(/定位权限已被拒绝/)).toBeVisible();
  await expect(page.getByRole("button", { name: "保存现场记录" })).toBeEnabled();
});

test("语音转写经人工修改确认后创建记录和显式待办", async ({ page }) => {
  const taskTitle = `语音 E2E 待办 ${Date.now()}`;
  await page.goto("/login");
  await login(page);
  await page.getByRole("link", { name: "新建现场记录" }).click();
  await page.getByRole("button", { name: "语音记录" }).click();
  await page.locator('input[accept*=".wav"]').setInputFiles({ name: "voice-fixture.wav", mimeType: "audio/wav", buffer: wavFixture() });
  await page.locator('input[accept^="image/jpeg"]').setInputFiles({ name: "voice-site.png", mimeType: "image/png", buffer: png });
  await page.getByRole("button", { name: "上传并开始转写" }).click();
  await expect(page.getByLabel("用户修订文本")).toBeVisible();
  await page.getByLabel("用户修订文本").fill("施工进度大约八成，防护有问题。");
  await page.getByRole("button", { name: "生成 Event 草稿" }).click();
  await expect(page.getByText("识别到的问题")).toBeVisible();
  await page.getByLabel("楼栋").selectOption({ label: "3号楼" });
  await page.getByLabel("楼层").selectOption({ label: "6层" });
  await page.getByLabel("区域").selectOption({ label: "西侧" });
  await page.getByLabel("确认对此问题创建待办").check();
  await page.getByLabel("待办标题").fill(taskTitle);
  await page.getByRole("combobox", { name: "责任人", exact: true }).selectOption({ label: "王强 · 施工员" });
  await page.getByRole("textbox", { name: "截止时间", exact: true }).fill("2026-08-30T18:00");
  await page.getByRole("button", { name: "最终确认并创建记录" }).click();
  await expect(page.getByText("现场记录已保存")).toBeVisible();
  await expect(page.getByText("语音与 AI 证据链")).toBeVisible();
  await expect(page.getByText("施工进度大约八成，防护有问题。").first()).toBeVisible();
  await expect(page.getByText(taskTitle)).toBeVisible();
  await page.getByRole("link", { name: "待办中心" }).last().click();
  await expect(page.getByText(taskTitle)).toBeVisible();
});

test("既有记录 AI 结构化可修改确认且刷新后保留证据链", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/login");
  await login(page);
  await page.getByRole("link", { name: "新建现场记录" }).click();
  await page.getByLabel("现场描述").fill("今天3号楼六层钢筋绑扎完成大约80%，现场12名钢筋工。西侧材料堆放比较乱，影响通道，通知李班长今天下午处理。");
  await page.getByLabel("楼栋").selectOption({ label: "3号楼" });
  await page.getByLabel("楼层").selectOption({ label: "6层" });
  await page.getByLabel("区域").selectOption({ label: "西侧" });
  await page.getByRole("button", { name: "保存现场记录" }).click();
  await expect(page.getByText("AI 结构化结果")).toBeVisible();
  await page.getByRole("button", { name: "开始 AI 结构化" }).click();
  await expect(page.getByText("草稿待确认")).toBeVisible();
  await expect(page.getByLabel("施工活动")).toHaveValue("钢筋绑扎");
  await expect(page.getByLabel("人数")).toHaveValue("12");
  await expect(page.getByLabel("进度（%）")).toHaveValue("80");
  await expect(page.getByText(/证据：/).first()).toBeVisible();
  await page.getByLabel("施工活动").fill("钢筋绑扎（人工核对）");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "确认 Event" }).click();
  await expect(page.getByText(/此 Event 已由人工确认/)).toBeVisible();
  await page.reload();
  await expect(page.getByText(/此 Event 已由人工确认/)).toBeVisible();
  await expect(page.getByLabel("施工活动")).toHaveValue("钢筋绑扎（人工核对）");
  await page.getByText("查看 AI 原始结果与审计记录").click();
  await expect(page.getByText(/AI 原始结果不会被人工编辑覆盖/)).toBeVisible();
  const dimensions = await page.evaluate(() => ({ viewport: window.innerWidth, document: document.documentElement.scrollWidth }));
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
});

test("已确认 Event 生成施工与安全日志，可人工确认、打印并刷新版本", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/login");
  await login(page);
  await page.getByRole("link", { name: "新建现场记录" }).click();
  await page.getByLabel("现场描述").fill("今天3号楼六层钢筋绑扎完成大约80%，现场12名钢筋工。西侧材料堆放影响通道，通知李班长处理。");
  await page.getByLabel("楼栋").selectOption({ label: "3号楼" });
  await page.getByLabel("楼层").selectOption({ label: "6层" });
  await page.getByLabel("区域").selectOption({ label: "西侧" });
  await page.getByRole("button", { name: "保存现场记录" }).click();
  await page.getByRole("button", { name: "开始 AI 结构化" }).click();
  await expect(page.getByText("草稿待确认")).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "确认 Event" }).click();
  await expect(page.getByText(/此 Event 已由人工确认/)).toBeVisible();

  await page.getByRole("link", { name: "日志" }).last().click();
  await expect(page.getByRole("heading", { name: "施工日志", exact: true, level: 2 })).toBeVisible();
  await page.getByRole("heading", { name: "施工日志", exact: true, level: 2 }).click();
  await expect(page.getByRole("heading", { name: "自动带入的现场事实" })).toBeVisible();
  const initialRefresh = page.getByRole("button", { name: "更新日志" });
  if (await initialRefresh.isVisible()) await initialRefresh.click();
  await expect(page.getByText("钢筋绑扎", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("12 人", { exact: true }).first()).toBeVisible();
  await page.getByLabel("天气").fill("晴（E2E 人工填写）");
  await page.getByRole("button", { name: "保存草稿" }).click();
  const firstLogUrl = page.url();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "确认日志" }).click();
  await expect(page.getByText("已确认", { exact: true }).first()).toBeVisible();
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("link", { name: "打印预览" }).click();
  const printPage = await popupPromise;
  await expect(printPage.getByRole("heading", { name: "施工日志" })).toBeVisible();
  await expect(printPage.getByText("晴（E2E 人工填写）")).toBeVisible();
  await printPage.close();

  await page.goto("/records/new");
  await page.getByLabel("现场描述").fill("今天3号楼六层模板安装完成，现场5名工人。");
  await page.getByLabel("楼栋").selectOption({ label: "3号楼" });
  await page.getByLabel("楼层").selectOption({ label: "6层" });
  await page.getByLabel("区域").selectOption({ label: "西侧" });
  await page.getByRole("button", { name: "保存现场记录" }).click();
  await page.getByRole("button", { name: "开始 AI 结构化" }).click();
  await expect(page.getByText("草稿待确认")).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "确认 Event" }).click();
  await page.goto(firstLogUrl);
  await expect(page.getByText(/新增 1 条已确认 Event/)).toBeVisible();
  await page.getByRole("button", { name: "更新日志" }).click();
  await expect(page).not.toHaveURL(firstLogUrl);
  await expect(page.locator("p").filter({ hasText: /版本 v\d+/ }).first()).toBeVisible();
  await expect(page.getByText("晴（E2E 人工填写）")).toBeVisible();

  await page.getByRole("link", { name: "返回日志中心" }).click();
  await page.getByRole("heading", { name: "施工安全日志", exact: true, level: 2 }).click();
  await expect(page.getByRole("heading", { name: "自动带入的现场事实" })).toBeVisible();
  const safetyRefresh = page.getByRole("button", { name: "更新日志" });
  if (await safetyRefresh.isVisible()) {
    const refreshed = page.waitForResponse((response) => response.url().endsWith("/refresh") && response.request().method() === "POST");
    await safetyRefresh.click();
    await refreshed;
    await page.waitForLoadState("networkidle");
  }
  const classifications = page.getByRole("combobox", { name: /问题归类/ });
  await expect(classifications.first()).toBeVisible();
  for (let index = 0; index < await classifications.count(); index += 1) await classifications.nth(index).selectOption("GENERAL");
  await page.getByRole("button", { name: "保存草稿" }).click();
  await expect(page.getByRole("button", { name: "确认日志" })).toBeEnabled();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "确认日志" }).click();
  await expect(page.getByText("已确认", { exact: true }).first()).toBeVisible();
  const dimensions = await page.evaluate(() => ({ viewport: window.innerWidth, document: document.documentElement.scrollWidth }));
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
});

test("安全问题经项目资料引用和人工确认形成可复核整改闭环", async ({ page }) => {
  const unique = Date.now();
  await page.goto("/login");
  await login(page);

  await page.getByRole("link", { name: "知识库" }).last().click();
  await page.locator('#knowledge-file').setInputFiles({
    name: `通道管理-${unique}.md`,
    mimeType: "text/markdown",
    buffer: Buffer.from(`# 通道管理\n材料堆放影响通道时，应及时清理障碍并留存整改前后照片。\n文档标识 ${unique}`),
  });
  await page.getByRole("button", { name: "上传并解析" }).click();
  await expect(page.getByRole("heading", { name: `通道管理-${unique}`, exact: true })).toBeVisible();

  await page.goto("/records/new");
  await page.getByLabel("现场描述").fill("今天3号楼六层钢筋绑扎完成80%，西侧材料堆放影响通道，通知王强处理。");
  await page.getByLabel("楼栋").selectOption({ label: "3号楼" });
  await page.getByLabel("楼层").selectOption({ label: "6层" });
  await page.getByLabel("区域").selectOption({ label: "西侧" });
  await page.getByRole("button", { name: "保存现场记录" }).click();
  await page.getByRole("button", { name: "开始 AI 结构化" }).click();
  await expect(page.getByText("草稿待确认")).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "确认 Event" }).click();
  await page.getByRole("link", { name: "查询项目资料依据" }).click();
  await page.getByText("材料堆放影响通道", { exact: true }).first().click();
  await page.getByRole("button", { name: "开始查询" }).click();
  await expect(page.getByText("逐条引用")).toBeVisible();
  await expect(page.getByText(/材料堆放影响通道时/).first()).toBeVisible();
  await page.getByLabel("最终问题描述").fill(`通道材料清理 ${unique}`);
  await page.getByLabel("整改措施").fill("清理通道并上传整改照片，由安全员复核。");
  await page.getByLabel("责任人").selectOption({ label: "王强 · 施工员" });
  await page.getByLabel("截止时间").fill("2026-09-01T18:00");
  await page.getByRole("button", { name: "确认并建单" }).click();
  await expect(page.getByText(/整改任务已创建/)).toBeVisible();
  const taskUrl = page.url();

  await page.getByRole("button", { name: "退出" }).click();
  await page.getByRole("button", { name: "王强" }).click();
  await login(page);
  await expect(page.getByText("海悦花园项目").first()).toBeVisible();
  await page.goto(taskUrl);
  await page.getByRole("button", { name: "开始任务" }).click();
  await page.getByLabel("整改说明").fill("已清理通道，现场复核条件具备。");
  await page.locator('input[type="file"]').setInputFiles({ name: "rectified.png", mimeType: "image/png", buffer: png });
  await page.getByRole("button", { name: "提交复核" }).click();
  await expect(page.getByText("等待复核")).toBeVisible();

  await page.getByRole("button", { name: "退出" }).click();
  await page.getByRole("button", { name: "张伟" }).click();
  await login(page);
  await expect(page.getByText("海悦花园项目").first()).toBeVisible();
  await page.goto(taskUrl);
  await page.getByRole("button", { name: "通过" }).click();
  await expect(page.getByText("已闭环").first()).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  const dimensions = await page.evaluate(() => ({ viewport: window.innerWidth, document: document.documentElement.scrollWidth }));
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
});
