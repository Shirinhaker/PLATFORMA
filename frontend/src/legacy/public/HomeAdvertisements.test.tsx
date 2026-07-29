import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HomeAdvertisements } from "./HomeAdvertisements";


describe("HomeAdvertisements", () => {
  it("uses the mobile banner source on a narrow screen", async () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 390,
    });
    const getAdvertisements = vi.fn().mockResolvedValue([
      {
        public_id: "a_public",
        title: "Turon Savdo",
        caption: "Yangi mebellar",
        owner_public_id: "",
        desktop_image_url: "/media/desktop.webp",
        mobile_image_url: "/media/mobile.webp",
        crop_x: 50,
        crop_y: 50,
        crop_zoom: 1,
      },
    ]);

    render(
      <HomeAdvertisements
        getAdvertisements={getAdvertisements}
        location={{
          region: "Surxondaryo",
          district: "Qumqo‘rg‘on",
          neighborhood: "",
        }}
      />,
    );

    expect(await screen.findByRole("img", { name: "Turon Savdo" }))
      .toHaveAttribute("src", "/media/mobile.webp");
    expect(getAdvertisements).toHaveBeenCalledWith({
      placement: "home",
      region: "Surxondaryo",
      district: "Qumqo‘rg‘on",
    });
  });

  it("shows an empty state when no advertisement matches", async () => {
    render(
      <HomeAdvertisements
        getAdvertisements={vi.fn().mockResolvedValue([])}
        location={null}
      />,
    );

    expect(await screen.findByText("Hozir faol reklama yo‘q"))
      .toBeVisible();
  });
});
