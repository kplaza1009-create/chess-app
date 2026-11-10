import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { START_FEN } from "../api/board";
import { GamePage } from "../pages/GamePage";

const gameId = "d34b8367-7ab5-4e6f-b55a-613562b9c9f1";
const authorized = vi.fn().mockResolvedValue({ token: "access-token" });
const session = { authorized };
vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => ({
    user: { id: "a470bb38-cf2d-428f-a238-8aa8fc16aaca", username: "white" },
    status: "authenticated",
    session,
  }),
}));

const sockets: FakeSocket[] = [];
class FakeSocket {
  static readonly OPEN = 1;
  readonly sent: string[] = [];
  readyState = FakeSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public readonly url: string) { sockets.push(this); }
  send(value: string): void { this.sent.push(value); }
  close(): void { this.readyState = 3; }
}
const position = {
  fen: START_FEN,
  board: [..."RNBQKBNRPPPPPPPP................................pppppppprnbqkbnr"],
  turn: "w" as const,
  legal_moves: ["e2e3", "e2e4"],
  check: false,
  ending: null,
};

beforeEach(() => {
  sockets.length = 0;
  authorized.mockClear();
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal("crypto", {
    randomUUID: () => "38a98108-a632-4446-816b-cc6bd08c1f86",
  });
  vi.spyOn(Math, "random").mockReturnValue(0);
  HTMLElement.prototype.setPointerCapture = vi.fn();
});
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function renderGame(): void {
  render(<MemoryRouter initialEntries={[`/games/${gameId}`]}><Routes>
    <Route path="games/:id" element={<GamePage />} />
  </Routes></MemoryRouter>);
}

it("authenticates, renders state and sends a versioned move", async () => {
  renderGame();
  await waitFor(() => expect(sockets).toHaveLength(1));
  const ws = sockets[0];
  if (!ws) throw new Error("Socket missing");
  act(() => ws.onopen?.());
  expect(JSON.parse(ws.sent[0] ?? "null")).toEqual({ type: "auth", token: "access-token" });
  act(() => ws.onmessage?.({ data: JSON.stringify({
    type: "state", id: gameId, version: 0, color: "w", result: "*", position, moves: [],
  }) } as MessageEvent));
  expect(await screen.findByRole("heading", { name: "White to move" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "e2, White pawn" }));
  await userEvent.click(screen.getByRole("button", { name: "e4, empty, legal destination" }));
  expect(JSON.parse(ws.sent[1] ?? "null")).toEqual({
    type: "move",
    version: 0,
    request_id: "38a98108-a632-4446-816b-cc6bd08c1f86",
    uci: "e2e4",
  });
});

it("requests a fresh ticket after a dropped connection", async () => {
  vi.useFakeTimers();
  renderGame();
  await act(async () => { await Promise.resolve(); });
  expect(sockets).toHaveLength(1);
  act(() => sockets[0]?.onclose?.({ code: 1006 } as CloseEvent));
  await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
  expect(sockets).toHaveLength(2);
  expect(authorized).toHaveBeenCalledTimes(2);
});

it("names the opponent and renders an abort without calling it a draw", async () => {
  renderGame();
  await waitFor(() => expect(sockets).toHaveLength(1));
  act(() => sockets[0]?.onmessage?.({ data: JSON.stringify({
    type: "state", id: gameId, version: 1, color: "w", result: "*",
    status: "aborted", opponent: "blackplayer", position: { ...position, ending: "aborted", legal_moves: [] }, moves: [],
  }) } as MessageEvent));
  expect(await screen.findByRole("heading", { name: "Game aborted — first move missed" })).toBeVisible();
  expect(screen.getByText("blackplayer")).toBeVisible();
});

it("shows reconnecting immediately when the browser goes offline", async () => {
  renderGame();
  await waitFor(() => expect(sockets).toHaveLength(1));
  window.dispatchEvent(new Event("offline"));
  expect(await screen.findByText("Reconnecting…", { exact: true })).toBeVisible();
});

it("shows the server-confirmed rating change after a rated game", async () => {
  renderGame();
  await waitFor(() => expect(sockets).toHaveLength(1));
  act(() => sockets[0]?.onmessage?.({ data: JSON.stringify({
    type: "state", id: gameId, version: 4, color: "w", result: "0-1",
    status: "finished", rated: true, rating_change: { before: 1200, after: 1184 },
    position: { ...position, ending: "checkmate", legal_moves: [] }, moves: [],
  }) } as MessageEvent));
  expect(screen.getByText(/Rated ·/)).toBeVisible();
  expect(screen.getByText("Your rating: 1200 → 1184 (-16)")).toBeVisible();
});
