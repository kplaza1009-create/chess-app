import { z } from "zod";
import { request } from "./client";

export const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
export const boardSchema = z.object({
  fen: z.string().min(1),
  board: z.array(z.string().regex(/^[prnbqkPRNBQK.]$/)).length(64),
  turn: z.enum(["w", "b"]),
  legal_moves: z.array(z.string().regex(/^[a-h][1-8][a-h][1-8][qrbn]?$/)),
  check: z.boolean(),
  ending: z.string().nullable(),
});
export type BoardState = z.infer<typeof boardSchema>;
export function loadPosition(fen: string, move?: string): Promise<BoardState> {
  return request("/board/position", boardSchema, {
    method: "POST", body: JSON.stringify({ fen, ...(move ? { move } : {}) }),
  });
}
export function squareName(index: number): string {
  return `${"abcdefgh"[index % 8]}${Math.floor(index / 8) + 1}`;
}
