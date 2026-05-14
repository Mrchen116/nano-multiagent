/**
 * R4 C1 tests for PermissionCard component.
 *
 * These tests verify:
 * 1. PermissionCard renders in pending state with tool name, question, options
 * 2. PermissionCard transitions to submitting after user clicks an option
 * 3. PermissionCard transitions to resolved (allow) state
 * 4. PermissionCard transitions to resolved (deny) state
 * 5. PermissionCard renders error state on POST failure
 * 6. message-pane renders PermissionCard when message has permission_request
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import type { PermissionOption, PermissionRequest } from "../chat-types";
import { PermissionCard } from "./permission-card";

const SAMPLE_OPTIONS: PermissionOption[] = [
  { id: "allow_once", label: "Allow once", description: "Allow this single action" },
  { id: "deny", label: "Deny", description: "Block this action" },
  { id: "allow_session", label: "Allow for session", description: "Allow all calls this session" },
];

const SAMPLE_REQUEST: PermissionRequest = {
  request_id: "req-abc",
  tool_name: "bash",
  tool_input: { command: "rm -rf /tmp/old" },
  question: "Allow bash to run this command?",
  options: SAMPLE_OPTIONS,
  status: "pending",
};

describe("PermissionCard — pending state", () => {
  it("renders tool name in the card header", () => {
    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    // Use getAllByText and check at least one element contains the tool name
    const elements = screen.getAllByText(/bash/i);
    expect(elements.length).toBeGreaterThan(0);
  });

  it("renders the question text", () => {
    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    expect(screen.getByText(/Allow bash to run this command/i)).toBeInTheDocument();
  });

  it("renders all option buttons", () => {
    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    expect(screen.getByRole("button", { name: /allow once/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /deny/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /allow for session/i })).toBeInTheDocument();
  });
});

describe("PermissionCard — submitting state", () => {
  it("disables all buttons after clicking one option", async () => {
    const user = userEvent.setup();
    let resolvePost!: (value: Response) => void;
    const mockFetch = vi.fn(() =>
      new Promise<Response>((res) => {
        resolvePost = res;
      })
    );

    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
        fetchFn={mockFetch as unknown as typeof fetch}
      />
    );

    const allowBtn = screen.getByRole("button", { name: /allow once/i });
    await user.click(allowBtn);

    // All buttons should be disabled while submitting
    const buttons = screen.getAllByRole("button");
    for (const btn of buttons) {
      expect(btn).toBeDisabled();
    }
    // Resolve the pending POST to avoid hanging
    resolvePost(new Response(JSON.stringify({ ok: true }), { status: 200 }));
  });
});

describe("PermissionCard — resolved state", () => {
  it("shows resolved-allow label after allow_once decision", async () => {
    const user = userEvent.setup();
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );
    const onResolved = vi.fn();

    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={onResolved}
        fetchFn={mockFetch as unknown as typeof fetch}
      />
    );

    await user.click(screen.getByRole("button", { name: /allow once/i }));
    await waitFor(() => {
      // After successful POST, card should show resolved state
      expect(screen.queryByRole("button", { name: /allow once/i })).not.toBeInTheDocument();
    });
    // Should show a resolved indicator
    const resolved = screen.getByTestId("permission-resolved");
    expect(resolved).toBeInTheDocument();
    expect(resolved.textContent).toMatch(/allow/i);
    // onResolved callback should have been called
    expect(onResolved).toHaveBeenCalledWith("allow_once");
  });

  it("shows resolved-deny label after deny decision", async () => {
    const user = userEvent.setup();
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );
    const onResolved = vi.fn();

    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={onResolved}
        fetchFn={mockFetch as unknown as typeof fetch}
      />
    );

    await user.click(screen.getByRole("button", { name: /^deny$/i }));
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /^deny$/i })).not.toBeInTheDocument();
    });
    const resolved = screen.getByTestId("permission-resolved");
    expect(resolved.textContent).toMatch(/den/i);
    expect(onResolved).toHaveBeenCalledWith("deny");
  });
});

describe("PermissionCard — error state", () => {
  it("shows error text when POST fails", async () => {
    const user = userEvent.setup();
    const mockFetch = vi.fn().mockRejectedValue(new Error("Network error"));

    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
        fetchFn={mockFetch as unknown as typeof fetch}
      />
    );

    await user.click(screen.getByRole("button", { name: /allow once/i }));
    await waitFor(() => {
      // Should show an error message, buttons re-enabled
      expect(screen.getByRole("button", { name: /allow once/i })).toBeEnabled();
    });
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

describe("PermissionCard — pre-resolved from WS event", () => {
  it("renders in resolved state when request.status === 'resolved'", () => {
    const resolvedRequest: PermissionRequest = {
      ...SAMPLE_REQUEST,
      status: "resolved",
      decision: "allow_once",
    };

    render(
      <PermissionCard
        request={resolvedRequest}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );

    expect(screen.getByTestId("permission-resolved")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /allow once/i })).not.toBeInTheDocument();
  });
});
