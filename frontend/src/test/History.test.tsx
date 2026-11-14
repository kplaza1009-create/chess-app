import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { START_FEN } from "../api/board";
import { replaySchema, type Replay } from "../api/history";
import { ReplayBoard } from "../components/ReplayBoard";
import { HistoryPage } from "../pages/HistoryPage";
import { ImportPage } from "../pages/ImportPage";
import { ReplayPage } from "../pages/ReplayPage";
import { authResult } from "./fixtures";

const { authorized, auth } = vi.hoisted(() => ({
  authorized: vi.fn(), auth: { user: null as typeof authResult.user | null },
}));
const session = { authorized };
vi.mock("../auth/AuthProvider", () => ({ useAuth: () => ({ user: auth.user, status: "authenticated", session }) }));
const id = "33333333-3333-4333-8333-333333333333";
const game: Replay = {
  id, source: "import", headers: { White: "Ada", Black: "Grace", Result: "*" },
  initial_fen: START_FEN, result: "*", termination: null, pgn: "1. e4 e5 *\n",
  moves: [
    { uci: "e2e4", san: "e4", fen_after: "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1" },
    { uci: "e7e5", san: "e5", fen_after: "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2" },
  ],
};
const item = {
  id, source: "import", white: "Ada", black: "Grace", result: "*", status: "imported",
  rated: false, time_control: null, ply_count: 2, created_at: "2026-11-13T12:00:00Z",
  rating_before: null, rating_after: null,
};
beforeEach(() => { authorized.mockReset(); auth.user = authResult.user; });

function page(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/history" element={<HistoryPage />} />
    <Route path="/history/import" element={<ImportPage />} />
    <Route path="/history/:source/:id" element={<ReplayPage />} />
    <Route path="/play" element={<h1>Play</h1>} />
  </Routes></MemoryRouter>);
}

it("loads history, paginates and resets the page when filtering", async () => {
  authorized.mockResolvedValueOnce({ items: [item], page: 1, has_more: true })
    .mockResolvedValueOnce({ items: [item], page: 2, has_more: false })
    .mockResolvedValueOnce({ items: [], page: 1, has_more: false });
  page("/history");
  expect(await screen.findByRole("link", { name: "Replay Ada versus Grace" })).toHaveAttribute("href", `/history/import/${id}?page=1&source=all`);
  expect(screen.getByText("PGN import · Unrated")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Next page" }));
  expect(await screen.findByText("Page 2")).toBeVisible();
  expect(authorized).toHaveBeenLastCalledWith("/history?page=2&source=all", expect.anything());
  await userEvent.selectOptions(screen.getByLabelText("Show"), "online");
  expect(await screen.findByText("No games here yet")).toBeVisible();
  expect(authorized).toHaveBeenLastCalledWith("/history?page=1&source=online", expect.anything());
});

it("shows a retryable history error", async () => {
  authorized.mockRejectedValueOnce(new Error("Database unavailable")).mockResolvedValueOnce({ items: [], page: 1, has_more: false });
  page("/history");
  expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("No games here yet")).toBeVisible();
});

it("preserves the history filter and page across replay and its return link", async () => {
  const listing = { items: [item], page: 3, has_more: false };
  authorized.mockResolvedValueOnce(listing).mockResolvedValueOnce(game).mockResolvedValueOnce(listing);
  page("/history?source=import&page=3");
  await userEvent.click(await screen.findByRole("link", { name: "Replay Ada versus Grace" }));
  await screen.findByRole("heading", { name: "Ada vs Grace" });
  expect(screen.getByRole("link", { name: "Back to your games" })).toHaveAttribute("href", "/history?page=3&source=import");
  await userEvent.click(screen.getByRole("link", { name: "Back to your games" }));
  expect(await screen.findByText("Page 3")).toBeVisible();
  expect(screen.getByLabelText("Show")).toHaveValue("import");
});

it("keeps replay return context after a direct load and focuses once after loading", async () => {
  let finish: ((value: Replay) => void) | undefined;
  authorized.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  page(`/history/import/${id}?source=import&page=3`);
  expect(screen.getByRole("heading", { name: "Game replay" })).toHaveAttribute("tabindex", "-1");
  await act(async () => { finish?.(game); });
  expect(screen.getByRole("heading", { name: "Ada vs Grace" })).toHaveFocus();
  expect(screen.getByRole("link", { name: "Back to your games" })).toHaveAttribute("href", "/history?source=import&page=3");
  await userEvent.click(screen.getByRole("button", { name: "Next move" }));
  expect(screen.getByRole("button", { name: "Next move" })).toHaveFocus();
  expect(screen.getByRole("heading", { name: "Ada vs Grace" })).not.toHaveFocus();
});

it("never displays old history after an account change", async () => {
  let finish: ((value: unknown) => void) | undefined;
  authorized.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }))
    .mockResolvedValueOnce({ items: [], page: 1, has_more: false });
  const view = render(<MemoryRouter><HistoryPage /></MemoryRouter>);
  auth.user = { ...authResult.user, id: id };
  view.rerender(<MemoryRouter><HistoryPage /></MemoryRouter>);
  await act(async () => { finish?.({ items: [item], page: 1, has_more: false }); });
  expect(await screen.findByText("No games here yet")).toBeVisible();
  expect(screen.queryByText("Ada")).not.toBeInTheDocument();
});

it("replays exact positions forward, backward, by move and keyboard", async () => {
  render(<ReplayBoard game={game} />);
  expect(screen.getByRole("button", { name: "Back one move" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "e2, White pawn" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Next move" }));
  expect(screen.getByRole("button", { name: "e4, White pawn" })).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent("Ply 1 of 2 · e4");
  await userEvent.click(screen.getByRole("button", { name: "Go to move 1... e5" }));
  expect(screen.getByRole("button", { name: "e5, Black pawn" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Next move" })).toBeDisabled();
  fireEvent.keyDown(screen.getByRole("button", { name: "Back one move" }), { key: "Home" });
  expect(screen.getByRole("status")).toHaveTextContent("Starting position");
  await userEvent.click(screen.getByRole("button", { name: "Last position" }));
  await userEvent.click(screen.getByRole("button", { name: "Back one move" }));
  expect(screen.getByRole("status")).toHaveTextContent("Ply 1 of 2");
  expect(screen.queryByText("Select a piece to see its legal moves.")).not.toBeInTheDocument();
  const calls = authorized.mock.calls.length;
  await userEvent.click(screen.getByRole("button", { name: "e4, White pawn" }));
  expect(authorized).toHaveBeenCalledTimes(calls);
  await userEvent.click(screen.getByRole("button", { name: "Flip board" }));
  expect(within(screen.getByRole("group", { name: "Chessboard" })).getAllByRole("button")[0]).toHaveAttribute("data-square", "h1");
});

it("numbers a black-to-move custom starting position correctly", () => {
  render(<ReplayBoard game={{ ...game, initial_fen: "4k3/8/8/8/8/8/7p/4K3 b - - 0 23",
    moves: [{ uci: "h2h1q", san: "h1=Q+", fen_after: "4k3/8/8/8/8/8/8/4K2q w - - 0 24" }] }} />);
  expect(screen.getByRole("button", { name: "Go to move 23... h1=Q+" })).toBeVisible();
});

it("downloads canonical PGN using a blob without putting auth tokens in URLs", async () => {
  const create = vi.fn<(blob: Blob) => string>(() => "blob:test");
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<ReplayBoard game={game} />);
  await userEvent.click(screen.getByRole("button", { name: "Download PGN" }));
  expect(create).toHaveBeenCalledOnce();
  expect(create.mock.calls[0]?.[0]).toBeInstanceOf(Blob);
  expect(click).toHaveBeenCalledOnce();
  expect(authorized).not.toHaveBeenCalled();
});

it("imports pasted PGN, disables duplicate submissions and opens the replay", async () => {
  let finish: ((value: Replay) => void) | undefined;
  authorized.mockReturnValueOnce(new Promise(resolve => { finish = resolve; })).mockResolvedValueOnce(game);
  page("/history/import");
  await userEvent.type(screen.getByLabelText("Or paste PGN"), "1. e4 e5 *");
  await userEvent.click(screen.getByRole("button", { name: "Import and replay" }));
  expect(screen.getByRole("button", { name: "Validating game…" })).toBeDisabled();
  expect(authorized).toHaveBeenCalledExactlyOnceWith("/history/import", expect.anything(), { method: "POST", body: JSON.stringify({ pgn: "1. e4 e5 *" }) });
  await act(async () => { finish?.(game); });
  expect(await screen.findByRole("heading", { name: "Ada vs Grace" })).toBeVisible();
});

it("reads an uploaded PGN file into the editor", async () => {
  page("/history/import");
  const file = new File(["1. e4 *"], "game.pgn", { type: "text/plain" });
  Object.defineProperty(file, "text", { value: async () => "1. e4 *" });
  await userEvent.upload(screen.getByLabelText("Choose a PGN file"), file);
  expect(await screen.findByDisplayValue("1. e4 *")).toBeVisible();
});

it("rejects oversized files and focuses server validation errors", async () => {
  authorized.mockRejectedValueOnce(new Error("Invalid move at ply 3: e4"));
  page("/history/import");
  const file = new File(["a".repeat(65537)], "large.pgn", { type: "text/plain" });
  await userEvent.upload(screen.getByLabelText("Choose a PGN file"), file);
  expect(screen.getByRole("alert")).toHaveTextContent("64 KiB");
  fireEvent.change(screen.getByLabelText("Or paste PGN"), { target: { value: "1. e4 e5 2. e4 *" } });
  await userEvent.click(screen.getByRole("button", { name: "Import and replay" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("ply 3");
  expect(screen.getByRole("alert")).toHaveFocus();
});

it("does not open a late import after navigation away", async () => {
  let finish: ((value: Replay) => void) | undefined;
  authorized.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }))
    .mockResolvedValueOnce({ items: [], page: 1, has_more: false });
  page("/history/import");
  await userEvent.type(screen.getByLabelText("Or paste PGN"), "*");
  await userEvent.click(screen.getByRole("button", { name: "Import and replay" }));
  await userEvent.click(screen.getByRole("link", { name: "Back to your games" }));
  await act(async () => { finish?.(game); });
  expect(screen.getByRole("heading", { name: "Your games" })).toBeVisible();
});

it("rejects malformed replay responses and bad route IDs", async () => {
  expect(replaySchema.safeParse({ ...game, initial_fen: "8/8 w - - 0 1" }).success).toBe(false);
  page("/history/online/not-a-uuid");
  expect(screen.getByRole("alert")).toHaveTextContent("Invalid replay link");
  expect(authorized).not.toHaveBeenCalled();
});

it("gates history behind authentication", () => {
  auth.user = null;
  page("/history");
  expect(screen.getByRole("link", { name: "Sign in to view your games" })).toBeVisible();
  expect(authorized).not.toHaveBeenCalled();
});
