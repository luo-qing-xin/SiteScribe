import { expect, test } from "@playwright/test";

const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64");

test("登录到现场记录并创建关联待办", async ({ page, context }) => {
  const taskTitle = `E2E 检查待办 ${Date.now()}`;
  await context.grantPermissions(["geolocation"], { origin: "http://localhost:3000" });
  await context.setGeolocation({ latitude: 23.1291, longitude: 113.2644, accuracy: 9 });
  await page.goto("/login");
  await page.getByRole("button", { name: "登录", exact: true }).click();
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
});

test("拒绝定位后仍可继续填写", async ({ page, context }) => {
  await context.clearPermissions();
  await page.goto("/login");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByText("海悦花园项目").first()).toBeVisible();
  await page.goto("/records/new");
  await page.getByRole("button", { name: "获取当前位置" }).click();
  await expect(page.getByText(/定位权限已被拒绝/)).toBeVisible();
  await expect(page.getByRole("button", { name: "保存现场记录" })).toBeEnabled();
});
