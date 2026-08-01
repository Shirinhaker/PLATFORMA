import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { HomeFollowedProfilesV1656 } from "./HomeFollowedProfilesV1656";


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
        items={[{
          kind: "business",
          public_id: "b_41",
          name: "Nafis salon",
          image_url: "/media/logo.webp",
          crop_x: 62,
          crop_y: 48,
          crop_zoom: 1.2,
        }]}
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
});
