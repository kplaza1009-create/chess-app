import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { BoardPage } from "../pages/BoardPage";
import { loadPosition, START_FEN, type BoardState } from "../api/board";

vi.mock("../api/board", async importOriginal => ({ ...await importOriginal<typeof import("../api/board")>(), loadPosition: vi.fn() }));
const state: BoardState = { fen: START_FEN, board: [..."RNBQKBNRPPPPPPPP................................pppppppprnbqkbnr"], turn: "w", check: false, ending: null, legal_moves: ["e2e3", "e2e4"] };
beforeEach(() => { vi.mocked(loadPosition).mockReset(); HTMLElement.prototype.setPointerCapture = vi.fn(); });
it.each([
  [null, "w", "White to move"],
  ["checkmate", "w", "Checkmate — Black wins"],
  ["checkmate", "b", "Checkmate — White wins"],
  ["stalemate", "w", "Draw — stalemate"],
  ["insufficient_material", "w", "Draw — insufficient material"],
] as const)("announces %s with a semantic heading", async (ending, turn, title) => {
  vi.mocked(loadPosition).mockResolvedValue({ ...state, ending, turn });
  render(<BoardPage />);
  const heading = await screen.findByRole("heading", { name: title });
  expect(heading.closest('[role="status"]')).not.toBeNull();
});
it("recovers after initial failure", async () => {
  vi.mocked(loadPosition).mockRejectedValueOnce(new Error("Connection failed")).mockResolvedValue(state);
  render(<BoardPage />);
  await screen.findByRole("alert");
  await userEvent.click(screen.getByRole("button", { name: "Reload position" }));
  await screen.findByRole("button", { name: "e2, White pawn" });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
it("keeps the current board when the server rejects a move", async () => {
  vi.mocked(loadPosition).mockResolvedValueOnce(state).mockRejectedValueOnce(new Error("Server unavailable"));
  render(<BoardPage />);
  await userEvent.click(await screen.findByRole("button", { name: "e2, White pawn" }));
  await userEvent.click(screen.getByRole("button", { name: "e4, empty, legal destination" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "e2, White pawn" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Undo move" })).toBeDisabled();
});
it("ignores a response after unmount", async () => {
  let resolve: (state: BoardState) => void = () => { throw Error("Promise not initialized"); };
  vi.mocked(loadPosition).mockImplementation(() => new Promise(done => { resolve = done; }));
  const view = render(<BoardPage />);
  view.unmount(); resolve(state);
  await waitFor(() => expect(screen.queryByRole("group", { name: "Chessboard" })).not.toBeInTheDocument());
});
