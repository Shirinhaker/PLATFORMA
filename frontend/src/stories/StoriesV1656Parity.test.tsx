import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../api/client";
import { OwnerStoriesV1656 } from "./OwnerStoriesV1656";
import { StoryComposerV1656 } from "./StoryComposerV1656";
import { StoryRailV1656 } from "./StoryRailV1656";
import { StoryViewerV1656 } from "./StoryViewerV1656";
import type { StoryGroup, StoryRead } from "../api/types";


const story: StoryRead = {
  id: 7,
  owner_type: "user",
  owner_public_id: "u_0123456789abcdef",
  media_type: "image",
  media_url: "https://media.test/story.jpg",
  thumbnail_url: "https://media.test/story.jpg",
  caption: "Bugungi yangilik",
  duration_seconds: 0,
  created_at: "2026-08-08T08:00:00Z",
  expires_at: "2026-08-09T08:00:00Z",
  viewed: false,
  state: "active",
};

const group: StoryGroup = {
  owner_type: "user",
  owner_public_id: "u_0123456789abcdef",
  name: "Ali",
  avatar_url: "",
  is_own: true,
  is_followed: false,
  has_unseen: true,
  distance_km: null,
  stories: [story],
};


function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}


describe("v1656 Istoriyalar pariteti", () => {
  it("rail ko‘rilmagan profilni ajratadi va viewer ochadi", () => {
    const open = vi.fn();
    render(<StoryRailV1656 groups={[group]} onOpen={open} />);

    const button = screen.getByRole("button", { name: /Ali istoriyasini ko‘rish/i });
    expect(button).toHaveClass("story-rail-card-v1656--unseen");
    fireEvent.click(button);
    expect(open).toHaveBeenCalledWith(0);
  });

  it("viewer ko‘rilishni yozadi va egasiga ko‘ruvchilarni ochadi", async () => {
    const recordView = vi.fn().mockResolvedValue({ ok: true, counted: false });
    const getViewers = vi.fn().mockResolvedValue([
      { account_public_id: "u_aaaaaaaaaaaaaaaa", name: "Vali", viewed_at: "2026-08-08T09:00:00Z" },
    ]);
    render(
      <StoryViewerV1656
        groups={[group]}
        initialGroupIndex={0}
        onClose={vi.fn()}
        recordView={recordView}
        getViewers={getViewers}
        deleteStory={vi.fn()}
        reportStory={vi.fn()}
      />,
    );

    expect(await screen.findByText("Bugungi yangilik")).toBeInTheDocument();
    await waitFor(() => expect(recordView).toHaveBeenCalledWith(7));
    fireEvent.click(screen.getByRole("button", { name: /Ko‘rganlar/i }));
    expect(await screen.findByText("Vali")).toBeInTheDocument();
  });

  it("composer 200 belgi va 60 soniya qoidalarini ko‘rsatadi", () => {
    render(
      <StoryComposerV1656
        createUploadGrant={vi.fn()}
        uploadGrantedFile={vi.fn()}
        createStory={vi.fn()}
        onCreated={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("0 / 200")).toBeInTheDocument();
    expect(screen.getByText(/Video 60 soniyadan oshmasin/i)).toBeInTheDocument();
  });

  it("owner composer ApiClient metodlarini obyektga bog‘langan holda chaqiradi", async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/session")) {
        return jsonResponse({
          account_id: 7,
          account_type: "user",
          name: "Ali",
          login: "ali",
          csrf_token: "story-csrf",
          expires_at: "2026-09-08T08:00:00Z",
        });
      }
      if (url.includes("/api/v1/stories/mine")) return jsonResponse([]);
      if (url.endsWith("/api/v1/media/upload-grants")) {
        return jsonResponse({
          object_key: "private/user/7/story/key.webp",
          upload_url: "https://r2.example/story-upload",
          method: "PUT",
          headers: { "Content-Type": "image/webp" },
          expires_in_seconds: 900,
        });
      }
      if (url === "https://r2.example/story-upload") {
        return new Response(null, { status: 200 });
      }
      if (url.endsWith("/api/v1/stories")) {
        return jsonResponse({ ok: true, story });
      }
      return jsonResponse({ message: "Topilmadi." }, 404);
    });
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();

    render(
      <OwnerStoriesV1656
        actor="user"
        api={client}
        ownerName="Ali"
        onBack={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "+ Istoriya" }));
    fireEvent.change(screen.getByLabelText("Rasm yoki video"), {
      target: {
        files: [new File(["image"], "story.webp", { type: "image/webp" })],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Joylash" }));

    await waitFor(() => expect(fetcher).toHaveBeenCalledWith(
      "https://api.example/api/v1/media/upload-grants",
      expect.objectContaining({ method: "POST" }),
    ));
    await waitFor(() => expect(fetcher).toHaveBeenCalledWith(
      "https://r2.example/story-upload",
      expect.objectContaining({ method: "PUT" }),
    ));
    await waitFor(() => expect(screen.queryByRole("dialog", {
      name: "Istoriya yaratish",
    })).not.toBeInTheDocument());
  });
});
