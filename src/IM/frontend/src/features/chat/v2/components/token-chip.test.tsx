import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../../../i18n";
import { TokenChip } from "./token-chip";

describe("TokenChip", () => {
  it("renders low usage as the default variant", () => {
    // bugfix-390: total is backend-contract-guaranteed; fixtures must include it.
    render(<TokenChip usage={{ output: 312, context_used: 14_800, context_window: 200_000, total: 15_112 }} />);
    const chip = screen.getByRole("button");
    expect(chip).toHaveClass("chat-token-chip");
    expect(chip).not.toHaveClass("chat-token-chip--warn");
    expect(chip).not.toHaveClass("chat-token-chip--critical");
    // chip shows total (15_112 → "15.1k"), not just output
    expect(chip.textContent).toMatch(/15\.1k/);
  });

  it("switches to the warning variant at 70% context usage", () => {
    // bugfix-390 FIX-2: fixture must include total; without it displayed=usage.total!
    // renders "undefined tok" but the test only checked CSS class, hiding the defect.
    render(<TokenChip usage={{ output: 50, context_used: 140_000, context_window: 200_000, total: 140_050 }} />);
    expect(screen.getByRole("button")).toHaveClass("chat-token-chip--warn");
    expect(screen.getByRole("button").textContent).toMatch(/140\.1k/);
  });

  it("switches to the critical variant at 90% context usage", () => {
    // bugfix-390 FIX-2: fixture must include total for the same reason.
    render(<TokenChip usage={{ output: 50, context_used: 190_000, context_window: 200_000, total: 190_050 }} />);
    expect(screen.getByRole("button")).toHaveClass("chat-token-chip--critical");
    expect(screen.getByRole("button").textContent).toMatch(/190\.1k/);
  });

  it("renders nothing when usage is missing", () => {
    const { container } = render(<TokenChip usage={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("R8-3: displays token_usage.total (real prompt+completion sum) when present", () => {
    render(
      <TokenChip
        usage={{ output: 1, context_used: 2428, context_window: 200_000, total: 2429 }}
      />
    );
    const chip = screen.getByRole("button");
    // The chip shows the total (2429) formatted as "2.4k" via fmtK; textContent includes arrow + "tok" + dot + ctx%
    expect(chip.textContent).toMatch(/2\.4k/);
    // Ensure the formatted total appears before "tok"
    expect(chip.textContent).toMatch(/2\.4k\s+tok/);
  });
});
