import { useEffect, useState } from "react";

export function formatClock(milliseconds: number): string {
  const seconds = Math.ceil(Math.max(0, milliseconds) / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function GameClock({ milliseconds, running, receivedAt, color, label }: {
  milliseconds: number; running: boolean; receivedAt: number; color: "White" | "Black"; label?: string;
}) {
  const [now, setNow] = useState(performance.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(performance.now()), 100);
    return () => window.clearInterval(timer);
  }, []);
  const left = Math.max(0, milliseconds - (running ? Math.max(0, now - receivedAt) : 0));
  return <span className={`game-clock${running ? " running" : ""}`} role="timer"
    aria-label={label ?? `${color} time remaining`} aria-live="off">
    {running && <span className="clock-active" aria-hidden="true">▶ </span>}{formatClock(left)}
  </span>;
}
