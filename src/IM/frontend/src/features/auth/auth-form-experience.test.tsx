import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { setLanguage } from "../../i18n";
import { LoginPage } from "./login-page";
import { RegisterPage } from "./register-page";
import { useAuthStore } from "./auth-store";

function renderPage(page: "login" | "register") {
  return render(
    <MemoryRouter>{page === "login" ? <LoginPage /> : <RegisterPage />}</MemoryRouter>
  );
}

function authResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("auth form experience", () => {
  beforeEach(() => {
    localStorage.clear();
    setLanguage("en");
    useAuthStore.getState().clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("keeps locally invalid registration input off the network and focuses the first error", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    renderPage("register");

    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    const username = screen.getByRole("textbox", { name: /username/i });
    const password = screen.getByLabelText(/^password/i);
    expect(fetchMock).not.toHaveBeenCalled();
    await waitFor(() => expect(username).toHaveFocus());
    expect(username).toHaveAttribute("aria-invalid", "true");
    expect(password).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Enter your username.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();

    await userEvent.type(username, "poppy");
    expect(username).toHaveAttribute("aria-invalid", "false");
    expect(screen.queryByText("Enter your username.")).not.toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();

    await userEvent.type(password, "1234");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(password).toHaveFocus();
    expect(screen.getByText("Password must be at least 8 characters.")).toBeInTheDocument();
  });

  it("keeps an empty login off the network and explains both required fields", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    renderPage("login");

    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox", { name: "Username" })).toHaveFocus();
    expect(screen.getByText("Enter your username.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
  });

  it("explains the password rule and can reveal the value without changing it", async () => {
    renderPage("register");
    const password = screen.getByLabelText(/^password/i);

    expect(screen.getByText("At least 8 characters.")).toBeInTheDocument();
    await userEvent.type(password, "secret12");
    await userEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");
    expect(password).toHaveValue("secret12");

    await userEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveValue("secret12");
  });

  it("projects a duplicate username onto the field and preserves the other input", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      authResponse(409, { detail: "username already exists" })
    );
    renderPage("register");

    await userEvent.type(screen.getByRole("textbox", { name: /username/i }), "poppy");
    await userEvent.type(screen.getByRole("textbox", { name: /display name/i }), "Poppy");
    await userEvent.type(screen.getByLabelText(/^password/i), "secret12");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    const username = await screen.findByRole("textbox", { name: /username/i });
    expect(username).toHaveAttribute("aria-invalid", "true");
    await waitFor(() => expect(username).toHaveFocus());
    expect(screen.getByText("That username is already taken.")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /display name/i })).toHaveValue("Poppy");
  });

  it("projects a correctable server rejection onto its field without exposing raw detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      authResponse(422, { detail: "password must be at least 8 characters" })
    );
    renderPage("register");

    await userEvent.type(screen.getByRole("textbox", { name: /username/i }), "poppy");
    await userEvent.type(screen.getByLabelText(/^password/i), "secret12");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    const password = screen.getByLabelText(/^password/i);
    expect(await screen.findByText("Password must be at least 8 characters.")).toBeInTheDocument();
    expect(password).toHaveAttribute("aria-invalid", "true");
    await waitFor(() => expect(password).toHaveFocus());
    expect(screen.queryByText("password must be at least 8 characters")).not.toBeInTheDocument();
  });

  it("keeps language available while one request is pending and prevents a duplicate submit", async () => {
    let resolveRequest!: (response: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      resolveRequest = resolve;
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockReturnValue(pending);
    renderPage("register");

    await userEvent.type(screen.getByRole("textbox", { name: /username/i }), "poppy");
    await userEvent.type(screen.getByLabelText(/^password/i), "secret12");
    const submit = screen.getByRole("button", { name: "Create account" });
    await userEvent.dblClick(submit);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Creating…" })).toBeDisabled();
    const language = screen.getByRole("group", { name: "Language" });
    const zh = within(language).getByRole("radio", { name: "中" });
    expect(zh).toBeEnabled();

    await userEvent.click(zh);
    expect(screen.getByRole("button", { name: "创建中…" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "用户名" })).toHaveValue("poppy");

    resolveRequest(authResponse(503, { detail: "unavailable" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("认证服务暂时不可用");
  });

  it("keeps invalid credentials distinct from a retryable service failure", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(authResponse(401, { detail: "invalid credentials" }))
      .mockResolvedValueOnce(authResponse(500, { detail: "database path /secret" }));
    renderPage("login");

    const username = screen.getByRole("textbox", { name: /username/i });
    const password = screen.getByLabelText(/^password/i);
    await userEvent.type(username, "alex");
    await userEvent.type(password, "wrongpass");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("username or password is incorrect");

    await userEvent.type(password, "2");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("temporarily unavailable");
    });
    expect(screen.queryByText(/database path|secret/i)).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(username).toHaveValue("alex");
  });
});
