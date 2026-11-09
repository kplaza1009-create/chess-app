import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { formatClock, GameClock } from "../components/GameClock";

afterEach(() => vi.useRealTimers());

it("formats boundaries without negative time", () => {
  expect(formatClock(-10)).toBe("0:00");
  expect(formatClock(1)).toBe("0:01");
  expect(formatClock(60000)).toBe("1:00");
  expect(formatClock(901000)).toBe("15:01");
});

it("counts elapsed monotonic time and stops on a server result", () => {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "performance"] });
  const view = render(<GameClock milliseconds={3000} receivedAt={performance.now()} running color="White" />);
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.getByRole("timer")).toHaveTextContent("0:02");
  view.rerender(<GameClock milliseconds={2000} receivedAt={performance.now()} running={false} color="White" />);
  act(() => vi.advanceTimersByTime(5000));
  expect(screen.getByRole("timer")).toHaveTextContent("0:02");
});
