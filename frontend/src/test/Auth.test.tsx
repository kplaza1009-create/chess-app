import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";
import { AuthProvider } from "../auth/AuthProvider";
import { AuthSession } from "../auth/session";
import { authResult, json, mockServer } from "./fixtures";

beforeEach(() => { vi.stubGlobal("BroadcastChannel", undefined); });
afterEach(() => { vi.unstubAllGlobals(); });

function renderPage(path: string): void {
  render(<MemoryRouter initialEntries={[path]}>
    <AuthProvider session={new AuthSession()}><App /></AuthProvider>
  </MemoryRouter>);
}

it("registers an account and renders the authenticated dashboard", async () => {
  const fetchMock = mockServer();
  renderPage("/register");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Username"), "kevin");
  await user.type(screen.getByLabelText("Email address"), "kevin@example.com");
  await user.type(screen.getByLabelText("Password"), "a safe passphrase");
  await user.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByRole("heading", { name: "Welcome, kevin." })).toBeInTheDocument();
  expect(screen.getAllByText("1200")).toHaveLength(3);
  const registration = fetchMock.mock.calls.find(([path]) => String(path).endsWith("/register"));
  expect(registration?.[1]?.credentials).toBe("same-origin");
  expect(new Headers(registration?.[1]?.headers).get("X-CSRF-Token")).toBe("test-csrf");
});

it("shows invalid credentials and keeps the user on the login page", async () => {
  mockServer({ rejectLogin: true });
  renderPage("/login");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Email address"), "kevin@example.com");
  await user.type(screen.getByLabelText("Password"), "incorrect password");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
  expect(screen.getByRole("heading", { name: "Welcome back." })).toBeInTheDocument();
});

it("toggles password visibility without submitting the form", async () => {
  const fetchMock = mockServer();
  renderPage("/login");
  const user = userEvent.setup();
  const password = await screen.findByLabelText("Password");
  expect(password).toHaveAttribute("type", "password");
  await user.click(screen.getByRole("button", { name: "Show password" }));
  expect(password).toHaveAttribute("type", "text");
  expect(fetchMock.mock.calls.some(([path]) => String(path).endsWith("/login"))).toBe(false);
});

it("signs out through the server and returns to the public homepage", async () => {
  mockServer();
  renderPage("/login");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Email address"), "kevin@example.com");
  await user.type(screen.getByLabelText("Password"), "a safe passphrase");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await user.click(await screen.findByRole("button", { name: "Sign out" }));
  await waitFor(() => expect(screen.queryByText("Welcome, kevin.")).not.toBeInTheDocument());
  expect(screen.getByRole("heading", { name: /Your next move/ })).toBeInTheDocument();
});

it("describes invalid fields and focuses the first one without submitting", async () => {
  const fetchMock = mockServer();
  renderPage("/register");
  const user = userEvent.setup();
  await screen.findByLabelText("Username");
  await user.click(screen.getByRole("button", { name: "Create account" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Check the highlighted fields");
  expect(screen.getByLabelText("Username")).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByLabelText("Username")).toHaveFocus();
  expect(screen.getByLabelText("Email address")).toHaveAccessibleDescription("Enter a valid email address.");
  expect(fetchMock.mock.calls.some(([path]) => String(path).endsWith("/register"))).toBe(false);
});

it("connects server validation errors to their field", async () => {
  const fetchMock = mockServer();
  renderPage("/login");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Email address"), "kevin@example.com");
  await user.type(screen.getByLabelText("Password"), "a safe passphrase");
  fetchMock.mockImplementation(async (input) => String(input).endsWith("/csrf")
    ? json({ csrf_token: "test-csrf" })
    : json({ detail: [{ loc: ["body", "email"], msg: "Invalid email", type: "value_error" }] }, 422));
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(screen.getByLabelText("Email address")).toHaveAttribute("aria-invalid", "true"));
  expect(screen.getByLabelText("Email address")).toHaveFocus();
  expect(screen.getByLabelText("Email address")).toHaveAccessibleDescription("Enter a valid email address.");
});

it("disables the form while a login is pending", async () => {
  const fetchMock = mockServer();
  renderPage("/login");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Email address"), "kevin@example.com");
  await user.type(screen.getByLabelText("Password"), "a safe passphrase");
  let finish = (_response: Response): void => { throw new Error("Not initialized"); };
  const delayed = new Promise<Response>((resolve) => { finish = resolve; });
  fetchMock.mockImplementation(async (input) => String(input).endsWith("/csrf")
    ? json({ csrf_token: "test-csrf" }) : delayed);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(screen.getByRole("button", { name: "Signing in..." })).toBeDisabled();
  expect(screen.getByLabelText("Password")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Show password" })).toBeDisabled();
  finish(json(authResult));
  expect(await screen.findByRole("heading", { name: "Welcome, kevin." })).toBeInTheDocument();
});

it("moves focus to the heading after keyboard navigation between auth pages", async () => {
  mockServer();
  renderPage("/login");
  const user = userEvent.setup();
  await screen.findByLabelText("Email address");
  const links = screen.getAllByRole("link", { name: "Create account" });
  const link = links.at(-1);
  if (!link) throw new Error("Missing registration link");
  link.focus();
  await user.keyboard("{Enter}");
  const heading = await screen.findByRole("heading", { name: "Take your seat." });
  expect(heading).toHaveFocus();
  expect(document.title).toBe("Create account | Chess Room");
});

it.each([
  ["😀".repeat(6), "at least 12 characters"],
  ["😀".repeat(19), "too long"],
])("validates Unicode passwords by characters and encoded size", async (password, message) => {
  const fetchMock = mockServer();
  renderPage("/register");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Username"), "kevin");
  await user.type(screen.getByLabelText("Email address"), "kevin@example.com");
  await user.click(screen.getByLabelText("Password"));
  await user.paste(password);
  await user.click(screen.getByRole("button", { name: "Create account" }));
  expect(screen.getByLabelText("Password")).toHaveAccessibleDescription(expect.stringContaining(message));
  expect(screen.getByLabelText("Password")).toHaveFocus();
  expect(fetchMock.mock.calls.some(([path]) => String(path).endsWith("/register"))).toBe(false);
});
