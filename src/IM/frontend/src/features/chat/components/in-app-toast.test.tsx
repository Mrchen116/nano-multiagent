import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, vi } from "vitest";

import { InAppToast } from "./in-app-toast";

describe("InAppToast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders sender name and message preview", () => {
    render(
      <MemoryRouter>
        <InAppToast senderName="OpsBot" preview="CI is green after the fix." conversationId="conv-1" onDismiss={() => undefined} />
      </MemoryRouter>
    );

    expect(screen.getByText("OpsBot")).toBeInTheDocument();
    expect(screen.getByText("CI is green after the fix.")).toBeInTheDocument();
  });

  it("calls onDismiss after the auto-dismiss timeout", () => {
    const onDismiss = vi.fn();

    render(
      <MemoryRouter>
        <InAppToast senderName="OpsBot" preview="Hello" conversationId="conv-1" onDismiss={onDismiss} />
      </MemoryRouter>
    );

    expect(onDismiss).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("navigates to the conversation when clicked", () => {
    const onDismiss = vi.fn();

    render(
      <MemoryRouter>
        <InAppToast senderName="OpsBot" preview="Hello" conversationId="conv-42" onDismiss={onDismiss} />
      </MemoryRouter>
    );

    const link = screen.getByRole("link", { name: /view message/i });
    expect(link).toHaveAttribute("href", "/chat/conv-42");

    // Click via DOM directly to avoid fake-timer / userEvent interaction issues
    link.click();
    expect(onDismiss).toHaveBeenCalled();
  });

  it("shows a dismiss button that calls onDismiss immediately", () => {
    const onDismiss = vi.fn();

    render(
      <MemoryRouter>
        <InAppToast senderName="OpsBot" preview="Hello" conversationId="conv-1" onDismiss={onDismiss} />
      </MemoryRouter>
    );

    screen.getByRole("button", { name: /dismiss/i }).click();
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
