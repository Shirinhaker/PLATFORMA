import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";


function response(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  };
}


describe("typed v1656 reviews API client", () => {
  it("uses public ids and applies CSRF only to writes", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response({
        account_id: 5,
        account_type: "user",
        name: "Ali",
        login: "u_ali",
        csrf_token: "review-csrf",
        expires_at: "2026-08-10T08:00:00Z",
      }))
      .mockResolvedValue(response({ reviews: [], avg: 0, count: 0 }));
    const client = new ApiClient("https://api.test", fetcher, { kind: "web" });
    await client.getSession();

    await client.getReviews("business", "b_0123456789abcdef");
    await client.saveReview({
      target_kind: "business",
      target_public_id: "b_0123456789abcdef",
      stars: 5,
      comment: "Zo‘r",
    });
    await client.deleteReview("business", "b_0123456789abcdef");
    await client.getReceivedReviews();
    await client.replyToReview(17, "Rahmat");

    expect(fetcher.mock.calls.slice(1).map(([url]) => url)).toEqual([
      "https://api.test/api/v1/reviews/business/b_0123456789abcdef",
      "https://api.test/api/v1/reviews",
      "https://api.test/api/v1/reviews/business/b_0123456789abcdef",
      "https://api.test/api/v1/reviews/received",
      "https://api.test/api/v1/reviews/17/reply",
    ]);
    expect(fetcher.mock.calls[1]?.[1]?.headers)
      .not.toHaveProperty("X-CSRF-Token");
    expect(fetcher.mock.calls[4]?.[1]?.headers)
      .not.toHaveProperty("X-CSRF-Token");
    for (const call of [fetcher.mock.calls[2], fetcher.mock.calls[3], fetcher.mock.calls[5]]) {
      expect(call?.[1]?.headers).toMatchObject({
        "X-CSRF-Token": "review-csrf",
      });
    }
  });
});
