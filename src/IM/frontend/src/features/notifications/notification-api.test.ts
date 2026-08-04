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
    it("reports support only when the Notification global is present", () => {
      expect(isNotificationSupported()).toBe(false);
      installFakeNotification("default");
      expect(isNotificationSupported()).toBe(true);
    });
  });

  describe("ensureNotificationPermission", () => {
    it("returns 'denied' when API is unavailable", async () => {
      expect(await ensureNotificationPermission()).toBe("denied");
    });

    it("returns a terminal permission without re-prompting", async () => {
      for (const permission of ["granted", "denied"] as const) {
        const { fake } = installFakeNotification(permission);
        expect(await ensureNotificationPermission()).toBe(permission);
        expect(fake.requestPermission).not.toHaveBeenCalled();
      }
    });

    it("requests permission when status is default", async () => {
      const { fake } = installFakeNotification("default", "granted");
      expect(await ensureNotificationPermission()).toBe("granted");
      expect(fake.requestPermission).toHaveBeenCalledTimes(1);
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
      expect(created[0].instance.close).toHaveBeenCalledTimes(1);
      expect(handle).not.toBeNull();
    });

    it("does not construct a notification unless the API is available and permission is granted", () => {
      const { fake } = installFakeNotification("denied");
      expect(showAgentNotification({ title: "x", body: "y", onClick: vi.fn() })).toBeNull();
      expect(fake).not.toHaveBeenCalled();
      delete (globalThis as unknown as { Notification?: unknown }).Notification;
      expect(showAgentNotification({ title: "x", body: "y", onClick: vi.fn() })).toBeNull();
    });
  });
});

beforeEach(() => {
  delete (globalThis as unknown as { Notification?: unknown }).Notification;
});
