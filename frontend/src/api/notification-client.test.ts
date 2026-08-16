import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";

function response(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  };
}

describe("typed v1656 notifications API client", () => {
  it("uses normalized endpoints and protects every write with CSRF", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        response({
          account_id: 5,
          account_type: "user",
          name: "Ali",
          login: "u_ali",
          csrf_token: "notification-csrf",
          expires_at: "2026-08-10T08:00:00Z",
        }),
      )
      .mockResolvedValue(response({}));
    const client = new ApiClient("https://api.test", fetcher, { kind: "web" });
    await client.getSession();

    await client.getNotifications();
    await client.getActionNotifications();
    await client.markNotificationRead(11);
    await client.markAllNotificationsRead();
    await client.getNotificationPreference();
    await client.saveNotificationPreference({ enabled: true, orders_enabled: true });
    await client.getNotificationFilters();
    await client.createNotificationFilter({
      cat: "uy",
      region: "",
      district: "",
      price_min: 0,
      price_max: 0,
      keyword: "",
    });
    await client.deleteNotificationFilter(3);
    await client.getPushStatus();
    await client.registerPushDevice({
      token: "firebase-token-1234567890",
      platform: "android",
      device_name: "Pixel",
      app_version: "1656",
    });
    await client.unregisterPushDevice("firebase-token-1234567890");

    expect(fetcher.mock.calls.slice(1).map(([url]) => url)).toEqual([
      "https://api.test/api/v1/notifications",
      "https://api.test/api/v1/notifications/actions",
      "https://api.test/api/v1/notifications/11/read",
      "https://api.test/api/v1/notifications/read-all",
      "https://api.test/api/v1/notifications/preferences",
      "https://api.test/api/v1/notifications/preferences",
      "https://api.test/api/v1/notifications/filters",
      "https://api.test/api/v1/notifications/filters",
      "https://api.test/api/v1/notifications/filters/3",
      "https://api.test/api/v1/notifications/push-status",
      "https://api.test/api/v1/notifications/devices",
      "https://api.test/api/v1/notifications/devices",
    ]);
    for (const index of [3, 4, 6, 8, 9, 11, 12]) {
      expect(fetcher.mock.calls[index]?.[1]?.headers).toMatchObject({
        "X-CSRF-Token": "notification-csrf",
      });
    }
    for (const index of [1, 2, 5, 7, 10]) {
      expect(fetcher.mock.calls[index]?.[1]?.headers).not.toHaveProperty(
        "X-CSRF-Token",
      );
    }
  });
});
