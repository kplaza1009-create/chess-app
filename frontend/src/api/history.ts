import { z } from "zod";
import type { BoardState } from "./board";

export const sourceSchema = z.enum(["online", "import"]);
const resultSchema = z.enum(["*", "1-0", "0-1", "1/2-1/2"]);
const fenSchema = z.string().max(160).refine(fen => {
  const [placement, turn, rights, ep, half, full, extra] = fen.split(" ");
  return placement !== undefined && placement.split("/").length === 8 &&
    placement.split("/").every(rank => /^[prnbqkPRNBQK1-8]+$/.test(rank) &&
      [...rank].reduce((size, char) => size + (/\d/.test(char) ? Number(char) : 1), 0) === 8) &&
    (turn === "w" || turn === "b") && /^(?:-|K?Q?k?q?)$/.test(rights ?? "") &&
    /^(?:-|[a-h][36])$/.test(ep ?? "") && /^\d+$/.test(half ?? "") &&
    /^[1-9]\d*$/.test(full ?? "") && extra === undefined;
}, "Invalid replay position");

export const historySchema = z.object({
  page: z.number().int().positive(), has_more: z.boolean(),
  items: z.array(z.object({
    id: z.uuid(), source: sourceSchema, white: z.string(), black: z.string(),
    result: resultSchema, status: z.string(), rated: z.boolean(),
    time_control: z.string().nullable(), ply_count: z.number().int().nonnegative(),
    created_at: z.iso.datetime({ offset: true }),
    rating_before: z.number().int().nonnegative().nullable(),
    rating_after: z.number().int().nonnegative().nullable(),
  })).max(20),
});
export const replaySchema = z.object({
  id: z.uuid(), source: sourceSchema, headers: z.record(z.string(), z.string()),
  initial_fen: fenSchema,
  moves: z.array(z.object({
    uci: z.string().regex(/^[a-h][1-8][a-h][1-8][qrbn]?$/),
    san: z.string().min(1).max(16), fen_after: fenSchema,
  })).max(20000),
  result: resultSchema, termination: z.string().nullable(), pgn: z.string(),
});
export type Replay = z.infer<typeof replaySchema>;

export function replayPosition(fen: string): BoardState {
  const parts = fen.split(" ");
  const board = (parts[0] ?? "").split("/").reverse().flatMap(rank =>
    [...rank].flatMap(char => /\d/.test(char) ? Array<string>(Number(char)).fill(".") : [char]));
  return { fen, board, turn: parts[1] === "b" ? "b" : "w", legal_moves: [], check: false, ending: "replay" };
}

export function resultLabel(result: string): string {
  return result === "1-0" ? "White wins" : result === "0-1" ? "Black wins" :
    result === "1/2-1/2" ? "Draw" : "Unfinished";
}
