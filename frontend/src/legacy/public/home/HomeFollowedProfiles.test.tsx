import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { HomeFollowedProfilesV1656 } from "./HomeFollowedProfiles";
import type { StoryGroup } from "../../../api/types";


const followedBusiness = {
  kind: "business" as const,
  public_id: "b_41",
  name: "Nafis salon",
  image_url: "/media/logo.webp",
  crop_x: 62,
  crop_y: 48,
  crop_zoom: 1.2,
};

const followedStory: StoryGroup = {
  owner_type: "business",
  owner_public_id: "b_41",
  name: "Nafis salon",
  avatar_url: "/media/logo.webp",
  is_own: false,
  is_followed: true,
  has_unseen: true,
  distance_km: null,
  stories: [{
    id: 7,
    owner_type: "business",
    owner_public_id: "b_41",
    media_type: "image",
    media_url: "/media/story.webp",
    thumbnail_url: "/media/story.webp",
    caption: "Yangilik",
    duration_seconds: 0,
    created_at: "2026-08-08T08:00:00Z",
    expires_at: "2026-08-09T08:00:00Z",
    viewed: false,
    state: "active",
  }],
};

const ownStory: StoryGroup = {
  ...followedStory,
  owner_type: "user",
  owner_public_id: "u_self",
  name: "Savdo",
  avatar_url: "/media/my-avatar.webp",
  is_own: true,
  is_followed: false,
  stories: [{
    ...followedStory.stories[0]!,
    id: 8,
    owner_type: "user",
    owner_public_id: "u_self",
  }],
};


describe("HomeFollowedProfilesV1656", () => {
  it("keeps the v1656 hidden mount when there are no followed profiles", () => {
    render(
      <HomeFollowedProfilesV1656 items={[]} onOpenProfile={vi.fn()} />,
    );

    expect(document.querySelector("#followedProfileStrip"))
      .toHaveAttribute("hidden");
    expect(document.querySelector("#followedProfileRail"))
      .toBeInTheDocument();
  });

  it("keeps the exact v1656 label, image, and fallback", async () => {
    const onOpenProfile = vi.fn();
    render(
      <HomeFollowedProfilesV1656
        items={[followedBusiness]}
        onOpenProfile={onOpenProfile}
      />,
    );

    const button = screen.getByRole("button", {
      name: "Nafis salon profilini ochish",
    });
    expect(button.closest("#followedProfileRail")).toBeInTheDocument();
    expect(button.querySelector("img")).toHaveAttribute("loading", "lazy");
    expect(button.querySelector(".story-fallback")).toHaveTextContent("N");
    await userEvent.click(button);
    expect(onOpenProfile).toHaveBeenCalledWith("business", "b_41");
  });

  it("opens a matching story from the same square followed-profile card", async () => {
    const onOpenProfile = vi.fn();
    const onOpenStory = vi.fn();
    render(
      <HomeFollowedProfilesV1656
        items={[followedBusiness]}
        storyGroups={[followedStory]}
        onOpenProfile={onOpenProfile}
        onOpenStory={onOpenStory}
      />,
    );

    const button = screen.getByRole("button", {
      name: "Nafis salon istoriyasini ko‘rish",
    });
    expect(button).toHaveClass("story-card", "unseen");
    expect(button.querySelector(".story-thumb")).toBeInTheDocument();
    await userEvent.click(button);
    expect(onOpenStory).toHaveBeenCalledWith(0);
    expect(onOpenProfile).not.toHaveBeenCalled();
  });

  it("shows the own story first even when there are no followed profiles", async () => {
    const onOpenProfile = vi.fn();
    const onOpenStory = vi.fn();
    render(
      <HomeFollowedProfilesV1656
        items={[]}
        storyGroups={[followedStory, ownStory]}
        onOpenProfile={onOpenProfile}
        onOpenStory={onOpenStory}
      />,
    );

    expect(document.querySelector("#followedProfileStrip"))
      .not.toHaveAttribute("hidden");
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toHaveAccessibleName("Sizning istoriyangizni ko‘rish");
    expect(buttons[0]).toHaveClass("story-card", "unseen");
    expect(buttons[0]?.querySelector(".story-thumb img"))
      .toHaveAttribute("src", "/media/my-avatar.webp");
    expect(buttons[0]?.querySelector(".story-name")).toHaveTextContent("Siz");
    await userEvent.click(buttons[0]!);
    expect(onOpenStory).toHaveBeenCalledWith(1);
    expect(onOpenProfile).not.toHaveBeenCalled();
  });

  it("keeps the own story before followed profile cards", () => {
    render(
      <HomeFollowedProfilesV1656
        items={[followedBusiness]}
        storyGroups={[ownStory, followedStory]}
        onOpenProfile={vi.fn()}
        onOpenStory={vi.fn()}
      />,
    );

    const buttons = screen.getAllByRole("button");
    expect(buttons[0]).toHaveAccessibleName("Sizning istoriyangizni ko‘rish");
    expect(buttons[1]).toHaveAccessibleName("Nafis salon istoriyasini ko‘rish");
  });

  it("does not add cards for story owners outside the followed list", () => {
    render(
      <HomeFollowedProfilesV1656
        items={[followedBusiness]}
        storyGroups={[{
          ...followedStory,
          owner_public_id: "b_not_followed",
          name: "Begona profil",
        }]}
        onOpenProfile={vi.fn()}
        onOpenStory={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(screen.queryByText("Begona profil")).not.toBeInTheDocument();
    expect(screen.getByRole("button", {
      name: "Nafis salon profilini ochish",
    })).not.toHaveClass("unseen", "seen");
  });
});
