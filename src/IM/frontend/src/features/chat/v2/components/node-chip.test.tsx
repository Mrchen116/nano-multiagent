import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../../../i18n";
import { NodeChip } from "./node-chip";

describe("NodeChip", () => {
  it("renders the node name with online state styling when online", () => {
    render(<NodeChip nodeName="laptop-prod" status="online" />);
    const chip = screen.getByText("laptop-prod");
    expect(chip).toBeInTheDocument();
    expect(chip.closest(".chat-node-chip")).toHaveClass("chat-node-chip--online");
  });

  it("renders the offline variant when status is offline", () => {
    render(<NodeChip nodeName="laptop-prod" status="offline" />);
    expect(screen.getByText("laptop-prod").closest(".chat-node-chip")).not.toHaveClass(
      "chat-node-chip--online"
    );
  });

  it("renders nothing when there is no node name", () => {
    const { container } = render(<NodeChip nodeName={null} status="offline" />);
    expect(container.firstChild).toBeNull();
  });
});
