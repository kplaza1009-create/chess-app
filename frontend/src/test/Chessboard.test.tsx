import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { Chessboard } from "../components/Chessboard";
import { START_FEN, type BoardState } from "../api/board";

const state: BoardState = {
  fen: START_FEN, board: [..."RNBQKBNRPPPPPPPP................................pppppppprnbqkbnr"],
  turn: "w", legal_moves: ["e2e3", "e2e4", "g1f3", "g1h3"], check: false, ending: null,
};
function setup(overrides: Partial<BoardState> = {}, busy = false, flipped = false) {
  const onMove = vi.fn();
  render(<Chessboard state={{ ...state, ...overrides }} busy={busy} flipped={flipped} lastMove={null} onMove={onMove} />);
  return onMove;
}
beforeAll(() => {
  window.PointerEvent = MouseEvent as typeof PointerEvent;
  HTMLElement.prototype.setPointerCapture = vi.fn();
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});
describe("Chessboard", () => {
  it.each(["e4", "e5", "outside", "cancel"])("handles pointer drop at %s", target => {
    const move = setup();
    const source = screen.getByRole("button", { name: "e2, White pawn" });
    const destination = target === "outside" ? document.body : screen.getByRole("button", { name: `${target === "e4" ? "e4" : "e5"}, empty` });
    Object.defineProperty(document, "elementFromPoint", { configurable: true, value: vi.fn(() => destination) });
    fireEvent.pointerDown(source, { button: 0, clientX: 10, clientY: 10 });
    fireEvent.pointerMove(source, { clientX: 10, clientY: 150 });
    if (target === "cancel") fireEvent.pointerCancel(source);
    else fireEvent.pointerUp(source, { clientX: 10, clientY: 150 });
    if (target === "e4") expect(move).toHaveBeenCalledWith("e2e4");
    else expect(move).not.toHaveBeenCalled();
  });
  it("shows 64 named squares and selects only legal destinations", async () => {
    const user = userEvent.setup(); const move = setup();
    expect(screen.getByRole("group").querySelectorAll("button")).toHaveLength(64);
    await user.click(screen.getByRole("button", { name: "e2, White pawn" }));
    expect(screen.getByRole("button", { name: "e4, empty, legal destination" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "e5, empty" }));
    expect(move).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "e2, White pawn" }));
    await user.click(screen.getByRole("button", { name: "e4, empty, legal destination" }));
    expect(move).toHaveBeenCalledWith("e2e4");
  });
  it("supports arrows, Enter, and Escape", async () => {
    const user = userEvent.setup(); setup();
    screen.getByRole("button", { name: "e2, White pawn" }).focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: "e2, White pawn" })).toHaveAttribute("aria-pressed", "true");
    await user.keyboard("{ArrowUp}");
    expect(screen.getByRole("button", { name: "e3, empty, legal destination" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "e2, White pawn" })).toHaveAttribute("aria-pressed", "false");
  });
  it("flips coordinates", () => { setup({}, false, true); expect(screen.getByRole("group").firstElementChild).toHaveAttribute("data-square", "h1"); });
  it.each([true, false])("blocks moves when busy or ended (%s)", async busy => {
    const move = setup(busy ? {} : { ending: "checkmate" }, busy);
    await userEvent.click(screen.getByRole("button", { name: "e2, White pawn" }));
    expect(screen.getByRole("button", { name: "e2, White pawn" })).toHaveAttribute("aria-pressed", "false");
    expect(move).not.toHaveBeenCalled();
  });
  it("requires a promotion choice and supports underpromotion", async () => {
    const board = [...state.board]; board[48] = "P"; board[56] = ".";
    const move = setup({ board, legal_moves: ["a7a8q", "a7a8r", "a7a8b", "a7a8n"] });
    await userEvent.click(screen.getByRole("button", { name: "a7, White pawn" }));
    await userEvent.click(screen.getByRole("button", { name: "a8, empty, legal destination" }));
    expect(move).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "knight" }));
    expect(move).toHaveBeenCalledWith("a7a8n");
  });
  it("marks check accessibly", () => { setup({ check: true }); expect(screen.getByRole("button", { name: "e1, White king, in check" })).toHaveClass("checked"); });
  it("does not wrap arrow keys across board edges", () => {
    setup(); const edge = screen.getByRole("button", { name: "a8, Black rook" }); edge.focus();
    fireEvent.keyDown(edge, { key: "ArrowLeft" }); expect(edge).toHaveFocus();
  });
});
