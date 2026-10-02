import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
const fetch = vi.hoisted(() => vi.fn());
vi.mock("../auth/auth-fetch", () => ({ authFetch: fetch }));
import { BindConfirmPage } from "./bind-confirm-page";
function page(url: string) {
  return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[url]}><BindConfirmPage /></MemoryRouter></QueryClientProvider>);
}
describe("local device acceptance", () => {
  it("uses the fragment in POST and waits for terminal confirmation", async () => {
    fetch.mockResolvedValueOnce({ok:true,json:async()=>({node_id:"node",node_name:"Device",agents:["a","b"],state:"awaiting_account"})}).mockResolvedValue({ok:true,json:async()=>({node_id:"node",node_name:"Device",agents:["a","b"],state:"awaiting_local_confirmation"})});
    page("/bind/confirm#token=secret");
    await waitFor(()=>expect(screen.getByRole("button",{name:"Accept complete device"})).toBeEnabled());
    await userEvent.click(screen.getByRole("button",{name:"Accept complete device"}));
    expect(fetch).toHaveBeenCalledWith("/im/v1/device-binding/accept", expect.objectContaining({body:JSON.stringify({browser_token:"secret"})}));
    expect(await screen.findByRole("status")).toHaveTextContent("local Gateway terminal");
    expect(screen.getByText("Agents: a, b")).toBeInTheDocument();
  });
  it("does not consume legacy query tokens", () => {
    page("/bind/confirm?token=legacy");
    expect(screen.getByRole("button",{name:"Accept complete device"})).toBeDisabled();
  });
});
