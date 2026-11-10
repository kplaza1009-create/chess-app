import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MatchmakingPage } from "../pages/MatchmakingPage";

const { authorized } = vi.hoisted(() => ({ authorized: vi.fn() }));
const session = { authorized };
vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => ({ user: { id: "player" }, status: "authenticated", session }),
}));

const ticket = "11111111-1111-4111-8111-111111111111";
const queued = { state: "queued", ticket_id: ticket, time_control: "3+2" };
const match = { state: "matched", game_id: "22222222-2222-4222-8222-222222222222" };
const idle = { state: "idle" };

beforeEach(() => { authorized.mockReset(); });
afterEach(() => { vi.useRealTimers(); });

function renderLobby() {
  return render(<MemoryRouter initialEntries={["/play"]}><Routes>
    <Route path="/play" element={<MatchmakingPage />} />
    <Route path="/games/:id" element={<h1>Matched game</h1>} />
  </Routes></MemoryRouter>);
}

it("joins the selected queue and enters the game returned by the heartbeat", async () => {
  vi.useFakeTimers();
  authorized.mockResolvedValueOnce(idle).mockResolvedValueOnce(queued).mockResolvedValueOnce(match);
  renderLobby();
  await act(async () => {});
  fireEvent.change(screen.getByLabelText("Time control"), { target: { value: "3+2" } });
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Find opponent" })); });
  expect(authorized).toHaveBeenNthCalledWith(2, "/matchmaking", expect.anything(), {
    method: "POST", body: JSON.stringify({ time_control: "3+2" }),
  });
  expect(screen.getByRole("heading", { name: "Searching for an opponent" })).toBeVisible();
  await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
  expect(authorized).toHaveBeenNthCalledWith(3, `/matchmaking/${ticket}`, expect.anything(), { method: "PUT" });
  expect(screen.getByRole("heading", { name: "Matched game" })).toBeVisible();
});

it("resumes a live search and ignores a heartbeat response after cancellation", async () => {
  vi.useFakeTimers();
  let finishHeartbeat: ((state: typeof queued) => void) | undefined;
  const pendingHeartbeat = new Promise<typeof queued>(resolve => { finishHeartbeat = resolve; });
  authorized.mockResolvedValueOnce(queued).mockReturnValueOnce(pendingHeartbeat).mockResolvedValueOnce(idle);
  renderLobby();
  await act(async () => {});
  await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Cancel search" })); });
  expect(authorized).toHaveBeenLastCalledWith(`/matchmaking/${ticket}`, expect.anything(), { method: "DELETE" });
  await act(async () => { finishHeartbeat?.(queued); });
  expect(screen.getByRole("status")).toHaveTextContent("Search canceled.");
  expect(screen.getByRole("button", { name: "Find opponent" })).toBeEnabled();
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(authorized).toHaveBeenCalledTimes(3);
});

it("opens an existing match on reload", async () => {
  authorized.mockResolvedValueOnce(match);
  renderLobby();
  expect(await screen.findByRole("heading", { name: "Matched game" })).toBeVisible();
  expect(authorized).toHaveBeenCalledTimes(1);
});

it("offers a retry when initial queue status is unavailable", async () => {
  authorized.mockRejectedValueOnce(new Error("Could not reach the server.")).mockResolvedValueOnce(idle);
  renderLobby();
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server.");
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("button", { name: "Find opponent" })).toBeEnabled();
});
