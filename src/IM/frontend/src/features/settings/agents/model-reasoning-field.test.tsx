import userEvent from "@testing-library/user-event";
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { i18n } from "../../../i18n";
import type { ModelOption } from "./im-agent-config-api";
import {
  ModelReasoningField,
  reasoningEffortAfterModelChange,
} from "./model-reasoning-field";

const OPTIONS: ModelOption[] = [
  {
    name: "adjustable",
    provider: "provider-a",
    reasoning: {
      kind: "selectable",
      default: "high",
      levels: ["low", "high", "custom-tier"],
    },
  },
  {
    name: "fixed",
    provider: "provider-b",
    reasoning: { kind: "fixed" },
  },
  { name: "plain", provider: "provider-c" },
];

afterEach(async () => {
  await act(async () => {
    await i18n.changeLanguage("en");
  });
});

describe("ModelReasoningField", () => {
  it("renders only declared levels, localizes known labels, and preserves unknown labels", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ModelReasoningField
        idPrefix="test"
        modelOptions={OPTIONS}
        selectedModel="adjustable"
        value={null}
        onChange={onChange}
      />,
    );

    const select = screen.getByLabelText("Reasoning effort");
    expect(select).toHaveValue("high");
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Low",
      "High",
      "custom-tier",
    ]);

    await user.selectOptions(select, "custom-tier");
    expect(onChange).toHaveBeenCalledWith("custom-tier");
  });

  it("shows the fixed, platform-default, and absent-descriptor explanations", async () => {
    const { rerender } = render(
      <ModelReasoningField
        idPrefix="test"
        modelOptions={OPTIONS}
        selectedModel={null}
        value={null}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/Select a model before configuring reasoning effort/i)).toBeInTheDocument();

    rerender(
      <ModelReasoningField
        idPrefix="test"
        modelOptions={OPTIONS}
        selectedModel="plain"
        value={null}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/does not expose configurable reasoning settings/i)).toBeInTheDocument();

    await act(async () => {
      await i18n.changeLanguage("zh");
    });
    rerender(
      <ModelReasoningField
        idPrefix="test"
        modelOptions={OPTIONS}
        selectedModel="fixed"
        value={null}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText("始终开启思考，由模型决定")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "推理强度" })).not.toBeInTheDocument();
  });

  it("keeps a stale draft visible and explains why it cannot be saved", () => {
    render(
      <ModelReasoningField
        idPrefix="test"
        modelOptions={OPTIONS}
        selectedModel="adjustable"
        value="retired-tier"
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Reasoning effort")).toHaveValue("retired-tier");
    expect(screen.getByRole("alert")).toHaveTextContent(/available efforts changed/i);
  });

  it("preserves a compatible effort across models and otherwise selects the declared default", () => {
    const nextOptions: ModelOption[] = [
      ...OPTIONS,
      {
        name: "second-adjustable",
        provider: "provider-d",
        reasoning: { kind: "selectable", default: "medium", levels: ["medium", "high"] },
      },
    ];

    expect(reasoningEffortAfterModelChange(nextOptions, "second-adjustable", "high")).toBe("high");
    expect(reasoningEffortAfterModelChange(nextOptions, "second-adjustable", "low")).toBe("medium");
    expect(reasoningEffortAfterModelChange(nextOptions, "fixed", "high")).toBeNull();
  });
});
