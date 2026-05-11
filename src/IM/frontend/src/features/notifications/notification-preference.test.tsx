import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  NOTIFICATION_PREFERENCE_STORAGE_KEY,
  getNotificationPreference,
  setNotificationPreference,
  useNotificationPreference
} from "./notification-preference";

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("notification-preference", () => {
  it("defaults to disabled when nothing is stored", () => {
    expect(getNotificationPreference()).toBe(false);
  });

  it("persists preference to localStorage and notifies hook subscribers", () => {
    const { result } = renderHook(() => useNotificationPreference());
    expect(result.current[0]).toBe(false);

    act(() => {
      result.current[1](true);
    });

    expect(localStorage.getItem(NOTIFICATION_PREFERENCE_STORAGE_KEY)).toBe("1");
    expect(getNotificationPreference()).toBe(true);
    expect(result.current[0]).toBe(true);

    act(() => {
      setNotificationPreference(false);
    });
    expect(localStorage.getItem(NOTIFICATION_PREFERENCE_STORAGE_KEY)).toBe("0");
    expect(result.current[0]).toBe(false);
  });
});
