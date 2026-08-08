import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";


describe("typed story API client", () => {
  it("feed, mine, view, viewers, delete va report endpointlarini ishlatadi", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        account_id: 3,
        account_type: "user",
        name: "Ali",
        login: "u_ali",
        csrf_token: "story-csrf",
        expires_at: "2026-08-09T08:00:00Z",
      }),
    }).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });
    const client = new ApiClient("https://api.test", fetcher, { kind: "web" });
    await client.getSession();

    await client.getStoryFeed({ lat: 41.3, lng: 69.2 });
    await client.getMyStories("archived");
    await client.recordStoryView(7);
    await client.getStoryViewers(7);
    await client.deleteStory(7);
    await client.reportStory(7, "Bu nomaqbul kontent");

    expect(fetcher.mock.calls.slice(1).map(([url]) => url)).toEqual([
      "https://api.test/api/v1/stories/feed?lat=41.3&lng=69.2",
      "https://api.test/api/v1/stories/mine?state=archived",
      "https://api.test/api/v1/stories/7/view",
      "https://api.test/api/v1/stories/7/viewers",
      "https://api.test/api/v1/stories/7",
      "https://api.test/api/v1/stories/7/reports",
    ]);
  });
});
