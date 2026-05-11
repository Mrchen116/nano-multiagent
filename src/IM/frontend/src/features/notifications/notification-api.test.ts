import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ensureNotificationPermission,
  isNotificationSupported,
  showAgentNotification
} from "./notification-api";

interface FakeNotificationInstance {
  onclick: ((this: FakeNotificationInstance) => void) | null;
  close: () => void;
}

interface FakeNotificationCtor {
  (title: string, options?: NotificationOptions): FakeNotificationInstance;
  permission: NotificationPermission;
  requestPermission: () => Promise<NotificationPermission>;
}

function installFakeNotification(initial: NotificationPermission, resolveTo: NotificationPermission = "granted") {
  const created: { title: string; options?: NotificationOptions; instance: FakeNotificationInstance }[] = [];
  const fake = vi.fn(function (this: unknown, title: string, options?: NotificationOptions) {
    const instance: FakeNotificationInstance = {
      onclick: null,
      close: vi.fn()
    };
    created.push({ title, options, instance });
    return instance;
  }) as unknown as FakeNotificationCtor;
  fake.permission = initial;
  fake.requestPermission = vi.fn(async () => {
    fake.permission = resolveTo;
    return resolveTo;
  });
  (globalThis as unknown as { Notification: FakeNotificationCtor }).Notification = fake;
  return { fake, created };
}

afterEach(() => {
  delete (globalThis as unknown as { Notification?: unknown }).Notification;
});

describe("notification-api", () => {
  describe("isNotificationSupported", () => {
    it("returns false when Notification global is absent", () => {
      expect(isNotificationSupported()).toBe(false);
    });

    it("returns true when Notification global is present", () => {
      installFakeNotification("default");
      expect(isNotificationSupported()).toBe(true);
    });
  });

  describe("ensureNotificationPermission", () => {
    it("returns 'denied' when API is unavailable", async () => {
      expect(await ensureNotificationPermission()).toBe("denied");
    });

    it("returns existing permission without re-prompting when granted", async () => {
      const { fake } = installFakeNotification("granted");
      expect(await ensureNotificationPermission()).toBe("granted");
      expect(fake.requestPermission).not.toHaveBeenCalled();
    });

    it("requests permission when status is default", async () => {
      const { fake } = installFakeNotification("default", "granted");
      expect(await ensureNotificationPermission()).toBe("granted");
      expect(fake.requestPermission).toHaveBeenCalledTimes(1);
    });

    it("does not re-prompt when previously denied", async () => {
      const { fake } = installFakeNotification("denied");
      expect(await ensureNotificationPermission()).toBe("denied");
      expect(fake.requestPermission).not.toHaveBeenCalled();
    });
  });

  describe("showAgentNotification", () => {
    it("constructs a Notification with title and body and wires onclick", () => {
      const { fake, created } = installFakeNotification("granted");
      const onClick = vi.fn();
      const handle = showAgentNotification({ title: "Assistant", body: "Done", onClick });
      expect(fake).toHaveBeenCalledTimes(1);
      expect(created[0].title).toBe("Assistant");
      expect(created[0].options?.body).toBe("Done");
      // simulate click
      created[0].instance.onclick?.call(created[0].instance);
      expect(onClick).toHaveBeenCalledTimes(1);
      expect(handle).not.toBeNull();
    });

    it("returns null when permission is not granted", () => {
      installFakeNotification("denied");
      expect(showAgentNotification({ title: "x", body: "y", onClick: vi.fn() })).toBeNull();
    });

    it("returns null when API is unavailable", () => {
      expect(showAgentNotification({ title: "x", body: "y", onClick: vi.fn() })).toBeNull();
    });
  });
});

beforeEach(() => {
  delete (globalThis as unknown as { Notification?: unknown }).Notification;
});
