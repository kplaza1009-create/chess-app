import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MatchmakingPage } from "../pages/MatchmakingPage";
import { authResult } from "./fixtures";

const { authorized, deleteOnExit } = vi.hoisted(() => ({
  authorized: vi.fn(),
  deleteOnExit: vi.fn(),
}));
const session = { authorized, deleteOnExit, reloadUser: async () => {} };
const user = {
  ...authResult.user,
  ratings: authResult.user.ratings.map(row => ({
    ...row,
    rating: row.speed === "blitz" ? 1325 : 1200,
  })),
};
vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => ({ user, status: "authenticated", session }),
}));

const ticket = "11111111-1111-4111-8111-111111111111";
const queued = { state: "queued", ticket_id: ticket, time_control: "3+2" };
const match = { state: "matched", game_id: "22222222-2222-4222-8222-222222222222" };
const idle = { state: "idle" };

beforeEach(() => { authorized.mockReset(); deleteOnExit.mockClear(); });
afterEach(() => { vi.useRealTimers(); });

function renderLobby() {
  return render(<MemoryRouter initialEntries={["/play"]}><Routes>
    <Route path="/play" element={<MatchmakingPage />} />
    <Route path="/games" element={<h1>Private rooms</h1>} />
    <Route path="/games/:id" element={<h1>Matched game</h1>} />
  </Routes></MemoryRouter>);
}

it("joins the selected queue and enters the game returned by the heartbeat", async () => {
  vi.useFakeTimers();
  authorized.mockResolvedValueOnce(idle).mockResolvedValueOnce(queued).mockResolvedValueOnce(match);
  renderLobby();
  await act(async () => {});
  expect(screen.getByText("Your rapid rating: 1200")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Time control"), { target: { value: "3+2" } });
  expect(screen.getByText("Your blitz rating: 1325")).toBeVisible();
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Find opponent" })); });
  expect(authorized).toHaveBeenNthCalledWith(2, "/matchmaking", expect.anything(), {
    method: "POST", body: JSON.stringify({ time_control: "3+2" }),
  });
  expect(screen.getByRole("heading", { name: "Searching for an opponent" })).toBeVisible();
  expect(screen.getByText("Your blitz rating: 1325")).toBeVisible();
  await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
  expect(authorized).toHaveBeenNthCalledWith(3, `/matchmaking/${ticket}`, expect.anything(), { method: "PUT" });
  expect(screen.getByRole("heading", { name: "Matched game" })).toBeVisible();
  expect(deleteOnExit).not.toHaveBeenCalled();
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

it("cancels the active ticket when navigating away from the lobby", async () => {
  authorized.mockResolvedValueOnce(queued);
  renderLobby();
  await screen.findByRole("heading", { name: "Searching for an opponent" });
  await userEvent.click(screen.getByRole("link", { name: "Create a private room" }));
  expect(screen.getByRole("heading", { name: "Private rooms" })).toBeVisible();
  expect(deleteOnExit).toHaveBeenCalledExactlyOnceWith(`/matchmaking/${ticket}`, user.id);
});

it("cancels a ticket returned by a join that finishes after navigation", async () => {
  let finishJoin: ((state: typeof queued) => void) | undefined;
  const pendingJoin = new Promise<typeof queued>(resolve => { finishJoin = resolve; });
  authorized.mockResolvedValueOnce(idle).mockReturnValueOnce(pendingJoin);
  renderLobby();
  await userEvent.click(await screen.findByRole("button", { name: "Find opponent" }));
  expect(screen.getByRole("button", { name: "Joining…" })).toBeDisabled();
  await userEvent.click(screen.getByRole("link", { name: "Create a private room" }));
  expect(deleteOnExit).not.toHaveBeenCalled();
  await act(async () => { finishJoin?.(queued); });
  expect(deleteOnExit).toHaveBeenCalledExactlyOnceWith(`/matchmaking/${ticket}`, user.id);
});

it("cancels on pagehide, stops polling and checks the queue on a cached return", async () => {
  vi.useFakeTimers();
  authorized.mockResolvedValueOnce(queued).mockResolvedValueOnce(idle);
  const view = renderLobby();
  await act(async () => {});
  expect(screen.getByRole("heading", { name: "Searching for an opponent" })).toBeVisible();
  act(() => { window.dispatchEvent(new Event("pagehide")); });
  expect(deleteOnExit).toHaveBeenCalledExactlyOnceWith(`/matchmaking/${ticket}`, user.id);
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(authorized).toHaveBeenCalledTimes(1);
  await act(async () => {
    window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true }));
  });
  expect(authorized).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("button", { name: "Find opponent" })).toBeEnabled();
  view.unmount();
  expect(deleteOnExit).toHaveBeenCalledTimes(1);
});
