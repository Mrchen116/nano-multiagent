import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../../../i18n";
import { TokenChip } from "./token-chip";

describe("TokenChip", () => {
  it("renders low usage as the default variant", () => {
    render(<TokenChip usage={{ output: 312, context_used: 14_800, context_window: 200_000 }} />);
    const chip = screen.getByRole("button");
    expect(chip).toHaveClass("chat-token-chip");
    expect(chip).not.toHaveClass("chat-token-chip--warn");
    expect(chip).not.toHaveClass("chat-token-chip--critical");
    expect(chip.textContent).toMatch(/312/);
  });

  it("switches to the warning variant at 70% context usage", () => {
    render(<TokenChip usage={{ output: 50, context_used: 140_000, context_window: 200_000 }} />);
    expect(screen.getByRole("button")).toHaveClass("chat-token-chip--warn");
  });

  it("switches to the critical variant at 90% context usage", () => {
    render(<TokenChip usage={{ output: 50, context_used: 190_000, context_window: 200_000 }} />);
    expect(screen.getByRole("button")).toHaveClass("chat-token-chip--critical");
  });

  it("renders nothing when usage is missing", () => {
    const { container } = render(<TokenChip usage={null} />);
    expect(container.firstChild).toBeNull();
  });
});
