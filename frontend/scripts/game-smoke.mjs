import assert from "node:assert/strict";
import { chromium } from "playwright";

const base = process.env.GAME_URL ?? "http://localhost:5173";
const browser = await chromium.launch({
  ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}),
});
const suffix = Date.now().toString(36);
const names = [`white_${suffix}`, `black_${suffix}`];
const contexts = await Promise.all([browser.newContext(), browser.newContext()]);
const pages = await Promise.all(contexts.map(context => context.newPage()));
const errors = [];
for (const page of pages) page.on("pageerror", error => errors.push(error.message));

async function account(context, name) {
  const csrf = await context.request.get(`${base}/api/v1/auth/csrf`);
  const response = await context.request.post(`${base}/api/v1/auth/register`, {
    headers: { Origin: base, "X-CSRF-Token": (await csrf.json()).csrf_token },
    data: { username: name, email: `${name}@example.com`, password: "Smoke-test-password-123" },
  });
  assert.equal(response.status(), 201, await response.text());
}
async function connected(page) { await page.getByText("Connected", { exact: true }).waitFor(); }
async function move(page, from, to) {
  await page.locator(`[data-square="${from}"]`).click();
  await page.locator(`[data-square="${to}"]`).click();
}
try {
  await account(contexts[0], names[0]); await account(contexts[1], names[1]);
  await pages[0].goto(`${base}/games`);
  await pages[0].getByLabel("Opponent’s username").fill(names[1]);
  await pages[0].getByLabel("Time control").selectOption("3+2");
  await pages[0].getByRole("button", { name: "Create game" }).click();
  await pages[0].waitForURL(/\/games\/[0-9a-f-]{36}$/);
  await connected(pages[0]);
  await pages[0].getByRole("timer", { name: "White time remaining" }).waitFor();
  await pages[0].getByRole("timer", { name: "Black time remaining" }).waitFor();
  await pages[1].goto(pages[0].url()); await connected(pages[1]);
  await move(pages[0], "e2", "e4");
  await pages[1].getByRole("heading", { name: "Black to move" }).waitFor();
  await move(pages[1], "e7", "e5");
  await pages[0].getByRole("heading", { name: "White to move" }).waitFor();
  await pages[0].reload(); await connected(pages[0]);
  assert.equal(await pages[0].getByRole("list", { name: "Move history" }).locator("li").count(), 2);
  await contexts[0].setOffline(true);
  await pages[0].getByText("Reconnecting…", { exact: true }).waitFor({ timeout: 60000 });
  await contexts[0].setOffline(false); await connected(pages[0]);
  await move(pages[0], "g1", "f3");
  await pages[1].getByRole("heading", { name: "Black to move" }).waitFor();
  for (const [width, height] of [[1280, 720], [390, 844], [320, 720]]) {
    await pages[0].setViewportSize({ width, height });
    assert(await pages[0].evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  }
  assert.deepEqual(errors, []);
  console.log("Game browser checks passed: timed room, two clocks, two accounts, moves, reload, offline reconnect, responsive widths.");
} finally { await browser.close(); }
