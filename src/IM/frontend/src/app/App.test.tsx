import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "./App";
import { AppProviders } from "./providers";

describe("App shell", () => {
  it("renders workspace switch", () => {
    render(
      <AppProviders>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </AppProviders>
    );

    expect(screen.getByRole("tab", { name: "Chat" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Settings" })).toBeInTheDocument();
  });

  it("uses fixed viewport height so the flex chain is capped and inner panels scroll", () => {
    const { container } = render(
      <AppProviders>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </AppProviders>
    );

    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("h-screen");
    expect(root.className).toContain("min-h-0");
  });
});
