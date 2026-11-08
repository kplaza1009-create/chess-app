import assert from "node:assert/strict";
import { chromium } from "playwright";

const browser = await chromium.launch({
  ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}),
  args: ["--no-sandbox"],
});
const page = await browser.newPage();
const errors = [];
page.on("pageerror", error => errors.push(error.message));
const square = name => page.locator(`[data-square="${name}"]`);
const waitTurn = color => page.getByRole("heading", { name: `${color} to move`, exact: true }).waitFor();
async function move(from, to) {
  await square(from).click(); await square(to).click();
}
async function load(fen) {
  await page.locator("details").evaluate(node => { node.open = true; });
  await page.getByLabel("FEN position").fill(fen);
  await page.getByRole("button", { name: "Load position", exact: true }).click();
  await page.waitForFunction(() => !document.querySelector('[aria-label="Chessboard"]')?.getAttribute("aria-busy")?.includes("true"));
}
try {
  await page.goto(process.env.BOARD_URL ?? "http://127.0.0.1:5173/practice");
  await waitTurn("White");
  for (const width of [320, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at ${width}`);
    assert.equal(await page.locator("[data-square]").count(), 64);
  }
  await page.screenshot({ path: "/tmp/chess-phase5-desktop.png", fullPage: true });
  await move("e2", "e4"); await waitTurn("Black");
  assert.match(await square("e4").getAttribute("aria-label"), /White pawn/);
  await page.getByRole("button", { name: "Undo move" }).click(); await waitTurn("White");
  // Real browser pointer capture and hit testing.
  const source = await square("e2").boundingBox(); const target = await square("e4").boundingBox();
  await page.mouse.move(source.x + source.width / 2, source.y + source.height / 2);
  await page.mouse.down();
  await page.mouse.move(target.x + target.width / 2, target.y + target.height / 2, { steps: 12 });
  await page.mouse.up(); await waitTurn("Black");
  await page.getByRole("button", { name: "Flip board" }).click();
  assert.equal(await page.locator("[data-square]").first().getAttribute("data-square"), "h1");
  await page.getByRole("button", { name: "Reset board" }).click(); await waitTurn("White");
  await page.getByRole("button", { name: "Flip board" }).click();
  await square("e2").focus(); await page.keyboard.press("Enter");
  await page.keyboard.press("ArrowUp"); await page.keyboard.press("ArrowUp"); await page.keyboard.press("Enter");
  await waitTurn("Black");
  await load("4k3/P7/8/8/8/8/8/4K3 w - - 0 1");
  await move("a7", "a8"); await page.getByRole("dialog").waitFor();
  await page.getByRole("button", { name: "knight", exact: true }).click();
  await page.getByRole("heading", { name: "insufficient material", exact: true }).waitFor();
  assert.match(await square("a8").getAttribute("aria-label"), /White knight/);
  await load("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1");
  await move("e1", "g1"); await waitTurn("Black");
  assert.match(await square("f1").getAttribute("aria-label"), /White rook/);
  await load("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1");
  await move("e5", "d6"); await waitTurn("Black");
  assert.match(await square("d5").getAttribute("aria-label"), /empty/);
  await page.getByRole("button", { name: "Reset board" }).click(); await waitTurn("White");
  await move("f2", "f3"); await waitTurn("Black"); await move("e7", "e5"); await waitTurn("White");
  await move("g2", "g4"); await waitTurn("Black"); await move("d8", "h4");
  await page.getByRole("heading", { name: "checkmate", exact: true }).waitFor();
  assert.match(await square("e1").getAttribute("aria-label"), /in check/);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await page.screenshot({ path: "/tmp/chess-phase5-mobile.png", fullPage: true });
  assert.deepEqual(errors, []);
  console.log("Browser checks passed: responsive widths, clicks, drag, keyboard, flip, undo, promotion, castling, en passant, checkmate, dark mode.");
} finally { await browser.close(); }
