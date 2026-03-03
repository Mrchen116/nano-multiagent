import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { render, screen } from "@testing-library/react";

import { appRoutes } from "./router";

describe("app routes", () => {
  it("contains chat and settings root routes", () => {
    const router = createMemoryRouter(appRoutes, {
      initialEntries: ["/chat"]
    });

    render(<RouterProvider router={router} />);

    expect(screen.getByText("Conversations")).toBeInTheDocument();
  });
});
