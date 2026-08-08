import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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


describe("v1656 Istoriyalar pariteti", () => {
  it("rail ko‘rilmagan profilni ajratadi va viewer ochadi", () => {
    const open = vi.fn();
    render(<StoryRailV1656 groups={[group]} onOpen={open} />);

    const button = screen.getByRole("button", { name: /Ali istoriyasini ko‘rish/i });
    expect(button).toHaveClass("story-card--unseen");
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
});
