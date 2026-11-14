import assert from "node:assert/strict";
import { readFile, mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const base = process.env.GAME_URL ?? "http://localhost:5173";
const browser = await chromium.launch({
  ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}),
});
const context = await browser.newContext({ acceptDownloads: true });
const page = await context.newPage();
const errors = [];
page.on("pageerror", error => errors.push(error.message));
const suffix = Date.now().toString(36);
const pgn = '[White "Ada"] [Black "Grace"] [Result "0-1"]\n1. f3 e5 2. g4 Qh4# 0-1';
try {
  const csrf = await context.request.get(`${base}/api/v1/auth/csrf`);
  const account = await context.request.post(`${base}/api/v1/auth/register`, {
    headers: { Origin: base, "X-CSRF-Token": (await csrf.json()).csrf_token },
    data: { username: `history_${suffix}`, email: `history_${suffix}@example.com`, password: "History-smoke-password-123" },
  });
  assert.equal(account.status(), 201, await account.text());
  await page.goto(`${base}/history`);
  await page.getByRole("heading", { name: "No games here yet" }).waitFor();
  await page.getByRole("link", { name: "Import PGN", exact: true }).click();
  await page.getByLabel("Or paste PGN").fill("1. e4 e5 2. e4 *");
  await page.getByRole("button", { name: "Import and replay" }).click();
  await page.getByRole("alert").filter({ hasText: "ply 3" }).waitFor();
  await page.getByLabel("Choose a PGN file").setInputFiles({ name: "mate.pgn", mimeType: "text/plain", buffer: Buffer.from(pgn) });
  await page.waitForFunction(value => document.querySelector("#pgn-text")?.value === value, pgn);
  assert.equal(await page.getByLabel("Or paste PGN").inputValue(), pgn);
  await page.getByRole("button", { name: "Import and replay" }).click();
  await page.waitForURL(/\/history\/import\/[0-9a-f-]{36}$/);
  await page.getByRole("heading", { name: "Ada vs Grace" }).waitFor();
  await page.getByRole("button", { name: "Next move", exact: true }).click();
  await page.getByRole("button", { name: "f3, White pawn", exact: true }).waitFor();
  await page.getByRole("button", { name: "Last position" }).click();
  await page.getByRole("button", { name: "h4, Black queen", exact: true }).waitFor();
  await page.getByRole("button", { name: "Back one move", exact: true }).click();
  await page.getByRole("button", { name: "d8, Black queen", exact: true }).waitFor();
  await page.getByRole("button", { name: "Go to move 2... Qh4#" }).click();
  await page.getByRole("button", { name: "Back one move", exact: true }).focus();
  await page.keyboard.press("Home");
  await page.getByRole("status").filter({ hasText: "Starting position" }).waitFor();
  await page.keyboard.press("End");
  await page.getByRole("button", { name: "Flip board" }).click();
  assert.equal(await page.locator(".chessboard button").first().getAttribute("data-square"), "h1");
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PGN" }).click();
  const file = await downloaded;
  const text = await readFile(await file.path(), "utf8");
  assert(text.endsWith("1. f3 e5 2. g4 Qh4# 0-1\n"));
  for (const [width, height] of [[1440, 900], [1280, 720], [390, 844], [320, 720], [844, 390], [667, 375], [320, 568]]) {
    await page.setViewportSize({ width, height });
    await page.evaluate(() => { window.scrollTo(0, 0); });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `overflow at ${width}`);
    const controls = await page.getByRole("group", { name: "Replay controls" }).boundingBox();
    assert(controls, `missing replay controls at ${width}x${height}`);
    if (height >= 720) assert(controls.y + controls.height <= height, `replay controls below fold at ${width}`);
    const board = await page.getByRole("group", { name: "Chessboard" }).boundingBox();
    assert(board && board.width >= 240, `unusable board at ${width}x${height}`);
    const buttons = await page.getByRole("group", { name: "Replay controls" }).getByRole("button").all();
    for (const button of buttons) {
      const box = await button.boundingBox();
      assert(box && box.width >= 44 && box.height >= 42, `unusable control at ${width}x${height}`);
    }
    if (process.env.HISTORY_SCREENSHOTS) {
      await mkdir(process.env.HISTORY_SCREENSHOTS, { recursive: true });
      await page.screenshot({ path: `${process.env.HISTORY_SCREENSHOTS}/replay-${width}.png`, fullPage: true });
    }
  }
  await page.emulateMedia({ colorScheme: "dark" });
  await page.getByRole("link", { name: "Back to your games" }).click();
  await page.getByRole("link", { name: "Replay Ada versus Grace" }).waitFor();
  await page.reload();
  await page.getByRole("link", { name: "Replay Ada versus Grace" }).waitFor();
  assert.deepEqual(errors, []);
  console.log("History browser checks passed: imports, errors, persistence, replay controls, keyboard, flip, PGN download, responsive widths and dark mode.");
} finally {
  await context.close();
  await browser.close();
}
