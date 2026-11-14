const { test, expect } = require("@playwright/test");
const { execFileSync } = require("node:child_process");
const { mkdtempSync, rmSync } = require("node:fs");
const { tmpdir } = require("node:os");
const { join } = require("node:path");
const { pathToFileURL } = require("node:url");
let temp, url;
test.beforeAll(() => {
  temp = mkdtempSync(join(tmpdir(), "hermes-audit-e2e-"));
  const db = join(temp, "state.db"),
    report = join(temp, "report.html");
  execFileSync("python", ["tests/fixture.py", db]);
  execFileSync("python", ["-m", "hermes_audit", "--db", db, "--out", report]);
  url = pathToFileURL(report).href;
});
test.afterAll(() => {
  if (temp) rmSync(temp, { recursive: true, force: true });
});

test("offline report filters by risk and keyword without executing transcript code", async ({
  page,
}) => {
  await page.goto(url);
  await expect(page.locator("#visible-count")).toContainText("6 records");
  await expect(page.locator(".entry")).toHaveCount(6);
  await expect(page.locator("#summary")).toContainText("critical");
  expect(await page.evaluate(() => window.HACKED)).toBeUndefined();
  await page.locator("#severity-filter").selectOption("critical");
  await expect(page.locator(".entry")).toHaveCount(1);
  await expect(page.locator(".entry")).toContainText("terminal");
  await page.locator("#severity-filter").selectOption("");
  await page.locator("#query").fill("Kimi official");
  await expect(page.locator(".entry")).toHaveCount(1);
  await expect(page.locator(".entry")).toContainText("web_search");
});

test("personal tags and overrides survive reload and can be filtered", async ({
  page,
}) => {
  await page.goto(url);
  await page
    .locator(".entry")
    .filter({ hasText: "web_search" })
    .first()
    .locator("summary")
    .click();
  const row = page.locator(".entry").filter({ hasText: "web_search" }).first();
  await row.locator(".annotation-tags").fill("review-later");
  await row.locator(".annotation-severity").selectOption("high");
  await row.locator(".save-annotation").click();
  await page.reload();
  await page.locator("#severity-filter").selectOption("high");
  await page.locator("#tag-filter").selectOption("review-later");
  await expect(page.locator(".entry")).toHaveCount(1);
  await expect(page.locator(".entry")).toContainText("web_search");
});
