import { z } from "zod";

export const ratingSchema = z.object({
  speed: z.enum(["bullet", "blitz", "rapid"]),
  rating: z.number().int().nonnegative(),
  wins: z.number().int().nonnegative(),
  losses: z.number().int().nonnegative(),
  draws: z.number().int().nonnegative(),
});

export const userSchema = z.object({
  id: z.string().uuid(),
  username: z.string(),
  email: z.string().email(),
  avatar_key: z.string().nullable(),
  created_at: z.string().datetime({ offset: true }),
  ratings: z.array(ratingSchema),
});

export const authSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.literal("bearer"),
  expires_in: z.number().int().positive(),
  session_id: z.string().uuid(),
  user: userSchema,
});

export const csrfSchema = z.object({ csrf_token: z.string().min(1) });
export const messageSchema = z.object({ message: z.string() });
export type User = z.infer<typeof userSchema>;
export type AuthResponse = z.infer<typeof authSchema>;
export type LoginInput = { email: string; password: string };
export type RegisterInput = LoginInput & { username: string };
