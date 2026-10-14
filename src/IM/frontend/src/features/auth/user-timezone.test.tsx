import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { authFetchJson } from "./auth-fetch";
import { useAuthStore, type BrowserSession } from "./auth-store";
import { useUserTimezone } from "./user-timezone";

vi.mock("./auth-fetch", () => ({ authFetchJson: vi.fn() }));
afterEach(() => { useAuthStore.getState().clear(); vi.restoreAllMocks(); vi.clearAllMocks(); });

it("reports foreground system changes and leaves background or unchanged timezone alone", async () => {
  let visibility: DocumentVisibilityState = "hidden";
  vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
  const zone = vi.spyOn(Intl.DateTimeFormat.prototype, "resolvedOptions")
    .mockReturnValue({ timeZone: "Asia/Shanghai" } as Intl.ResolvedDateTimeFormatOptions);
  useAuthStore.getState().setSession({ access_token: "token", user: { id: "u", timezone: null } } as BrowserSession);
  vi.mocked(authFetchJson).mockImplementation(async (_path, options) => JSON.parse(String(options?.body)));
  const { unmount } = renderHook(() => useUserTimezone());
  expect(authFetchJson).not.toHaveBeenCalled();
  visibility = "visible";
  act(() => document.dispatchEvent(new Event("visibilitychange")));
  await waitFor(() => expect(useAuthStore.getState().user?.timezone).toBe("Asia/Shanghai"));
  expect(authFetchJson).toHaveBeenCalledTimes(1);
  act(() => window.dispatchEvent(new Event("focus")));
  expect(authFetchJson).toHaveBeenCalledTimes(1);
  zone.mockReturnValue({ timeZone: "Asia/Tokyo" } as Intl.ResolvedDateTimeFormatOptions);
  visibility = "hidden";
  act(() => document.dispatchEvent(new Event("visibilitychange")));
  expect(authFetchJson).toHaveBeenCalledTimes(1);
  visibility = "visible";
  act(() => document.dispatchEvent(new Event("visibilitychange")));
  await waitFor(() => expect(useAuthStore.getState().user?.timezone).toBe("Asia/Tokyo"));
  expect(authFetchJson).toHaveBeenLastCalledWith("/im/v1/me/timezone", {
    method: "PATCH", body: JSON.stringify({ timezone: "Asia/Tokyo" }),
  });
  unmount();
});
