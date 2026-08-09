import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";


function response(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  };
}


describe("typed general message API client", () => {
  it("uses public profile ids and protects all message writes with CSRF", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response({
        account_id: 5,
        account_type: "user",
        name: "Ali",
        login: "u_ali",
        csrf_token: "message-csrf",
        expires_at: "2026-08-09T08:00:00Z",
      }))
      .mockResolvedValue(response([]));
    const client = new ApiClient("https://api.test", fetcher, { kind: "web" });
    await client.getSession();

    await client.getMessageConversations();
    await client.getMessageThread("business", "b_0123456789abcdef");
    await client.sendMessage({
      target_kind: "business",
      target_public_id: "b_0123456789abcdef",
      text: "Salom",
    });
    await client.sendMessageImage({
      target_kind: "business",
      target_public_id: "b_0123456789abcdef",
      object_key: "private/user/5/chat_image/photo.webp",
      file_name: "photo.webp",
    });
    await client.editMessage(17, "Yangilandi");
    await client.deleteMessage(17);
    await client.getMessageUnreadCount();

    expect(fetcher.mock.calls.slice(1).map(([url]) => url)).toEqual([
      "https://api.test/api/v1/messages/conversations",
      "https://api.test/api/v1/messages/with/business/b_0123456789abcdef",
      "https://api.test/api/v1/messages/send",
      "https://api.test/api/v1/messages/image",
      "https://api.test/api/v1/messages/17",
      "https://api.test/api/v1/messages/17",
      "https://api.test/api/v1/messages/unread-count",
    ]);
    for (const call of fetcher.mock.calls.slice(3, 7)) {
      expect(call[1]?.headers).toMatchObject({
        "X-CSRF-Token": "message-csrf",
      });
    }
    expect(fetcher.mock.calls[1]?.[1]?.headers)
      .not.toHaveProperty("X-CSRF-Token");
    expect(fetcher.mock.calls[2]?.[1]?.headers)
      .not.toHaveProperty("X-CSRF-Token");
    expect(fetcher.mock.calls[7]?.[1]?.headers)
      .not.toHaveProperty("X-CSRF-Token");
  });
});
