import { expect, it, vi } from "vitest";
import { authFetch } from "../../features/auth/auth-fetch";
import { type AuthUser, useAuthStore } from "../../features/auth/auth-store";
import { confirmMessageDelivery } from "./delivery-receipts";

vi.mock("../../features/auth/auth-fetch", () => ({ authFetch: vi.fn() }));

it("retries transport and temporary auth failures without replaying the message", async () => {
  vi.useFakeTimers();
  useAuthStore.setState({ user: { id: "recipient" } as AuthUser });
  const post = vi.mocked(authFetch);
  post.mockRejectedValueOnce(new TypeError("network unavailable"));
  post.mockResolvedValueOnce(new Response(null, { status: 401 }));
  post.mockResolvedValueOnce(new Response(null, { status: 200 }));
  try {
    confirmMessageDelivery([{ id: "message", sender_user_id: "sender", receipts_requested: true }]);
    await vi.advanceTimersByTimeAsync(3000);
    const request = ["/im/v1/message-receipts", { method: "POST", body: '{"message_ids":["message"]}' }];
    expect(post.mock.calls).toEqual([request, request, request]);
  } finally {
    useAuthStore.getState().clear();
    vi.useRealTimers();
  }
});
