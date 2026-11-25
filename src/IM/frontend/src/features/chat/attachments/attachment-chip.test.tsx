import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { AttachmentChip } from "./attachment-chip";

describe("AttachmentChip", () => {
  test("renders image preview with src=url for image content_type", () => {
    render(
      <AttachmentChip
        attachment={{ url: "http://im.local/im/uploads/x.png", content_type: "image/png", file_name: "x.png" }}
      />
    );
    const img = screen.getByRole("img", { name: "x.png" });
    expect(img).toHaveAttribute("src", "http://im.local/im/uploads/x.png");
  });

  test("renders document chip with file_name for non-image content_type", () => {
    render(
      <AttachmentChip
        attachment={{
          url: "http://im.local/im/uploads/y.pdf",
          content_type: "application/pdf",
          file_name: "report.pdf"
        }}
      />
    );
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  test("renders SVG attachment as document download chip rather than inline img", () => {
    render(
      <AttachmentChip
        attachment={{
          url: "http://im.local/im/v1/conversations/c1/attachments/diagram",
          content_type: "image/svg+xml",
          file_name: "diagram.svg"
        }}
      />
    );
    expect(screen.getByText("diagram.svg")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  test("calls onRemove when remove button clicked", async () => {
    const onRemove = vi.fn();
    render(
      <AttachmentChip
        attachment={{ url: "http://im.local/x.png", content_type: "image/png", file_name: "x.png" }}
        onRemove={onRemove}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /remove/i }));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  test("hides remove button when onRemove not provided (rendered in bubble)", () => {
    render(
      <AttachmentChip
        attachment={{ url: "http://im.local/x.png", content_type: "image/png", file_name: "x.png" }}
      />
    );
    expect(screen.queryByRole("button", { name: /remove/i })).not.toBeInTheDocument();
  });
});
