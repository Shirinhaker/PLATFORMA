import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FollowLists } from "./FollowLists";


const rows = [{
  kind: "business" as const,
  public_id: "b_1234567890abcdef",
  name: "Turon Savdo",
  info: "Savdo",
  image_url: "/media/turon.webp",
  crop_x: 62,
  crop_y: 48,
  crop_zoom: 1.2,
  followed_at: 1_785_200_000,
}];


describe("FollowLists", () => {
  it("loads the typed followers list and opens the selected profile", async () => {
    const user = userEvent.setup();
    const onOpenProfile = vi.fn();
    const api = {
      getFollowers: vi.fn().mockResolvedValue({ items: rows, count: 1 }),
      getFollowing: vi.fn(),
    };

    render(
      <FollowLists
        api={api}
        kind="followers"
        onBack={vi.fn()}
        onOpenProfile={onOpenProfile}
      />,
    );

    expect(await screen.findByText("1 ta obunachi")).toBeInTheDocument();
    const profile = screen.getByRole("button", { name: /Turon Savdo/ });
    expect(profile.querySelector("img")).toHaveAttribute(
      "src",
      "/media/turon.webp",
    );
    await user.click(profile);

    expect(api.getFollowers).toHaveBeenCalledOnce();
    expect(api.getFollowing).not.toHaveBeenCalled();
    expect(onOpenProfile).toHaveBeenCalledWith(
      "business",
      "b_1234567890abcdef",
    );
  });

  it("keeps the exact modular following empty state", async () => {
    const api = {
      getFollowers: vi.fn(),
      getFollowing: vi.fn().mockResolvedValue({ items: [], count: 0 }),
    };

    render(
      <FollowLists
        api={api}
        kind="following"
        onBack={vi.fn()}
        onOpenProfile={vi.fn()}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Kuzatayotganlar yo'q" }),
    ).toBeInTheDocument();
    expect(screen.getByText(
      "Biznes yoki mutaxassisni kuzatganingizda shu yerda ko'rinadi.",
    )).toBeInTheDocument();
  });
});
