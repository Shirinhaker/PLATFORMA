import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HomeAdvertisements } from "./HomeAdvertisements";


describe("HomeAdvertisements", () => {
  afterEach(() => {
    vi.useRealTimers();
    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: false,
    });
  });

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

    const image = await screen.findByRole("img", { name: "Reklama" });
    expect(image).toHaveAttribute("src", "/media/desktop.webp");
    expect(image.previousElementSibling).toHaveAttribute(
      "srcset",
      "/media/mobile.webp",
    );
    expect(getAdvertisements).toHaveBeenCalledWith({
      placement: "home",
      region: "Surxondaryo",
      district: "Qumqo‘rg‘on",
    });
  });

  it("falls back to the five exact v1656 demo advertisements", async () => {
    render(
      <HomeAdvertisements
        getAdvertisements={vi.fn().mockResolvedValue([])}
        location={null}
      />,
    );

    expect(await screen.findByText("Orzu Mebel")).toBeVisible();
    expect(document.querySelectorAll(".dots-row span[data-home-ad-dot]"))
      .toHaveLength(5);
    expect(screen.queryByText("Hozir faol reklama yo‘q"))
      .not.toBeInTheDocument();
  });

  it("keeps the exact v1656 banner element structure", async () => {
    render(
      <HomeAdvertisements
        getAdvertisements={vi.fn().mockResolvedValue([])}
        location={null}
      />,
    );

    await screen.findByText("Orzu Mebel");
    expect(document.querySelector("#adBox > .ad-overlay")?.tagName)
      .toBe("DIV");
    expect(document.querySelector("#adBox > .ad-copy")?.tagName)
      .toBe("DIV");
    expect(document.querySelector("#adBox > .blob")?.tagName)
      .toBe("DIV");
  });

  it("shows the exact v1656 toast when a demo advertisement is clicked", async () => {
    render(
      <HomeAdvertisements
        getAdvertisements={vi.fn().mockResolvedValue([])}
        location={null}
      />,
    );

    await screen.findByText("Orzu Mebel");
    await userEvent.click(document.querySelector("#adBox")!);

    expect(screen.getByText("Bu namoyish uchun joylangan demo reklama."))
      .toHaveClass("app-toast", "on");
  });

  it("records a real advertisement click and opens its owner", async () => {
    const recordAdvertisementClick = vi.fn().mockResolvedValue(undefined);
    const onOpenOwner = vi.fn();
    render(
      <HomeAdvertisements
        getAdvertisements={vi.fn().mockResolvedValue([{
          public_id: "a_public",
          title: "Turon Savdo",
          caption: "Yangi mebellar",
          owner_public_id: "biz_public",
          owner_kind: "business",
          desktop_image_url: "/media/desktop.webp",
          mobile_image_url: "",
          crop_x: 50,
          crop_y: 50,
          crop_zoom: 1,
        }])}
        location={null}
        onOpenOwner={onOpenOwner}
        recordAdvertisementClick={recordAdvertisementClick}
      />,
    );

    await screen.findByText("Turon Savdo");
    await userEvent.click(document.querySelector("#adBox")!);

    expect(recordAdvertisementClick).toHaveBeenCalledWith("a_public");
    expect(onOpenOwner).toHaveBeenCalledWith("business", "biz_public");
  });

  it("uses the exact one-second v1656 fade before changing slides", async () => {
    vi.useFakeTimers();
    render(
      <HomeAdvertisements
        getAdvertisements={vi.fn().mockResolvedValue([
          {
            public_id: "a_one",
            title: "Birinchi reklama",
            caption: "Birinchi matn",
            owner_public_id: "",
            desktop_image_url: "/media/one.webp",
            mobile_image_url: "",
            crop_x: 50,
            crop_y: 50,
            crop_zoom: 1,
          },
          {
            public_id: "a_two",
            title: "Ikkinchi reklama",
            caption: "Ikkinchi matn",
            owner_public_id: "",
            desktop_image_url: "/media/two.webp",
            mobile_image_url: "",
            crop_x: 50,
            crop_y: 50,
            crop_zoom: 1,
          },
        ])}
        location={null}
      />,
    );
    await act(async () => undefined);

    await act(async () => {
      document.querySelector<HTMLElement>("[data-home-ad-dot='1']")?.click();
    });
    expect(document.querySelector("#adBox")).toHaveClass("ad-transitioning");
    expect(screen.getByText("Birinchi reklama")).toBeInTheDocument();

    await act(async () => { vi.advanceTimersByTime(999); });
    expect(screen.getByText("Birinchi reklama")).toBeInTheDocument();
    await act(async () => { vi.advanceTimersByTime(1); });
    expect(screen.getByText("Ikkinchi reklama")).toBeInTheDocument();
  });

  it("batches a two-second view until the page becomes hidden", async () => {
    vi.useFakeTimers();
    const recordAdvertisementViews = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: false,
    });
    render(
      <HomeAdvertisements
        getAdvertisements={vi.fn().mockResolvedValue([{
          public_id: "a_public",
          title: "Turon Savdo",
          caption: "Yangi mebellar",
          owner_public_id: "",
          desktop_image_url: "/media/desktop.webp",
          mobile_image_url: "",
          crop_x: 50,
          crop_y: 50,
          crop_zoom: 1,
        }])}
        location={null}
        recordAdvertisementViews={recordAdvertisementViews}
      />,
    );
    await act(async () => undefined);

    await act(async () => { vi.advanceTimersByTime(2_000); });
    expect(recordAdvertisementViews).not.toHaveBeenCalled();

    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));
    await act(async () => undefined);

    expect(recordAdvertisementViews).toHaveBeenCalledWith(["a_public"]);
  });
});
