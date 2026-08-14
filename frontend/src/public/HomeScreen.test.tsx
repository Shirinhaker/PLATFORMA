import type { ComponentProps } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../api/client";
import { HomeScreen } from "./HomeScreen";

type HomeStoryApi = NonNullable<ComponentProps<typeof HomeScreen>["storyApi"]>;

function renderHome(
  currentDistrict?: string,
  overrides: {
    searchPublic?: ApiClient["searchPublic"];
    storyApi?: HomeStoryApi;
  } = {},
) {
  const actions = {
    onSearch: vi.fn(),
    onOpenCatalog: vi.fn(),
    onOpenLocation: vi.fn(),
    onOpenPublicResult: vi.fn(),
  };

  const services = {
    getHomeMap: vi.fn().mockResolvedValue({
      businesses: [{
        id: 41,
        public_id: "biz_41",
        name: "Qumqo‘rg‘on ustalari",
        yon: "Maishiy xizmatlar",
        tur: "Usta",
        lat: 37.82,
        lng: 67.58,
        logo_file: "",
        logo_x: 50,
        logo_y: 50,
        logo_zoom: 1,
        address: "Qumqo‘rg‘on",
        source: "public",
      }],
      specialists: [],
    }),
    getDistrictOffers: vi.fn().mockResolvedValue({
      needs_district: false,
      items: [{
        kind: "service",
        business_id: 41,
        business_public_id: "biz_41",
        content_id: 51,
        content_public_id: "service_51",
        title: "Konditsioner ta’miri",
        business_name: "Qumqo‘rg‘on ustalari",
        image: "",
        business_logo: "",
        price: "100 000 so‘m",
        unit: "xizmat",
      }],
      slot: 1,
    }),
    getFollowedProfiles: vi.fn().mockResolvedValue([{
      kind: "business",
      public_id: "biz_41",
      name: "Qumqo‘rg‘on ustalari",
      image_url: "",
      crop_x: 50,
      crop_y: 50,
      crop_zoom: 1,
    }]),
    searchPublic: overrides.searchPublic ?? vi.fn().mockResolvedValue({
      items: [{
        kind: "business",
        public_id: "biz_41",
        name: "Qumqo‘rg‘on ustalari",
        public_username: "usta",
        description: "Konditsioner ta’miri",
        direction: "Maishiy xizmatlar",
        activity_type: "Usta",
        region: "Surxondaryo viloyati",
        district: "Qumqo‘rg‘on tumani",
        mahalla: "",
        image_url: "",
      }],
      page: 1,
      page_size: 20,
      total: 1,
      pages: 1,
    }),
    storyApi: overrides.storyApi,
  };

  render(
    <HomeScreen
      authenticated
      currentDistrict={currentDistrict}
      location={currentDistrict ? {
        region: "Surxondaryo viloyati",
        district: currentDistrict,
        neighborhood: "",
      } : null}
      {...services}
      {...actions}
    />,
  );

  return { ...actions, ...services };
}

describe("HomeScreen", () => {
  it("shows the approved modular discovery copy", () => {
    renderHome();

    expect(
      screen.getByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Hudud tanlanmagan")).toHaveLength(2);
  });

  it("searches a trimmed query from the Qidirish button", async () => {
    const { onSearch, searchPublic } = renderHome();

    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "  telefon ta’miri  ",
    );
    await userEvent.click(screen.getByRole("button", { name: "Qidirish" }));

    expect(searchPublic).toHaveBeenCalledWith({
      q: "telefon ta’miri",
      region: "",
      district: "",
      page: 1,
      page_size: 20,
    });
    expect(await screen.findByText("Natijalar — 1 ta")).toBeInTheDocument();
    expect(onSearch).not.toHaveBeenCalled();
  });

  it("uses the modular mobile focused-search class only while the query is focused", async () => {
    renderHome();
    const input = screen.getByPlaceholderText("Nima qidiryapsiz?");
    const card = document.querySelector(".home-search-card");

    await userEvent.click(input);
    expect(card).toHaveClass("mobile-search-focused");

    await userEvent.tab();
    expect(card).not.toHaveClass("mobile-search-focused");
  });

  it("searches from Enter", async () => {
    const { onSearch, searchPublic } = renderHome();

    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "usta{enter}",
    );

    expect(searchPublic).toHaveBeenCalledWith({
      q: "usta",
      region: "",
      district: "",
      page: 1,
      page_size: 20,
    });
    expect(onSearch).not.toHaveBeenCalled();
  });

  it("opens the catalog for a blank search, as modular does", async () => {
    const { onSearch, onOpenCatalog } = renderHome();

    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "   {enter}",
    );
    await userEvent.click(screen.getByRole("button", { name: "Qidirish" }));

    expect(onSearch).not.toHaveBeenCalled();
    expect(onOpenCatalog).toHaveBeenCalledTimes(2);
  });

  it("opens the full catalog", async () => {
    const { onOpenCatalog } = renderHome();

    await userEvent.click(
      screen.getByRole("button", { name: /^Katalog bo‘yicha/ }),
    );

    expect(onOpenCatalog).toHaveBeenCalledOnce();
  });

  it("shows the selected district in every modular Home location slot", () => {
    renderHome("Qumqo‘rg‘on tumani");

    expect(screen.getAllByText("Qumqo‘rg‘on tumani")).toHaveLength(3);
  });

  it("renders the complete modular home structure and district data", async () => {
    const { getHomeMap, getDistrictOffers, getFollowedProfiles } = renderHome(
      "Qumqo‘rg‘on tumani",
    );

    expect(document.querySelector(".home-discovery")).toBeInTheDocument();
    expect(document.querySelector(".home-discovery"))
      .toHaveAttribute("id", "homeDiscovery");
    expect(document.querySelector(".home-search-card")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Katalog bo‘yicha/ }))
      .toHaveAttribute("id", "homeCatalogOpen");
    expect(document.querySelector("#homeCatalogLocation"))
      .toHaveTextContent("Qumqo‘rg‘on tumani");
    expect(document.querySelector("#homeLocationNote"))
      .toHaveTextContent("Joriy hudud: Qumqo‘rg‘on tumani");
    expect(document.querySelector(".home-map-pane")).toBeInTheDocument();
    expect(document.querySelector("#leafletMap")).toBeInTheDocument();
    expect(screen.getByText("Yaqin atrofdagilar")).toBeInTheDocument();
    expect(screen.getByText("Joriy hudud:")).toBeInTheDocument();
    expect((await screen.findAllByRole("button", {
      name: /Qumqo‘rg‘on ustalari/i,
    })).length).toBeGreaterThan(0);
    expect(await screen.findByText("Konditsioner ta’miri"))
      .toBeInTheDocument();
    expect(getHomeMap).toHaveBeenCalledWith({
      district: "Qumqo‘rg‘on tumani",
    });
    expect(getDistrictOffers).toHaveBeenCalledWith({
      district: "Qumqo‘rg‘on tumani",
    });
    expect(getFollowedProfiles).toHaveBeenCalledOnce();
  });

  it("opens own and followed stories from the single square profile strip", async () => {
    const followedStory = {
      id: 7,
      owner_type: "business" as const,
      owner_public_id: "biz_41",
      media_type: "image" as const,
      media_url: "/media/story.webp",
      thumbnail_url: "/media/story.webp",
      caption: "Yangi xizmat",
      duration_seconds: 0,
      created_at: "2026-08-08T08:00:00Z",
      expires_at: "2026-08-09T08:00:00Z",
      viewed: false,
      state: "active" as const,
    };
    const storyApi: HomeStoryApi = {
      getStoryFeed: vi.fn().mockResolvedValue([{
        owner_type: "user",
        owner_public_id: "u_self",
        name: "Men",
        avatar_url: "",
        is_own: true,
        is_followed: false,
        has_unseen: true,
        distance_km: null,
        stories: [{
          ...followedStory,
          id: 6,
          owner_type: "user",
          owner_public_id: "u_self",
          caption: "Mening istoriyam",
        }],
      }, {
        owner_type: "business",
        owner_public_id: "biz_41",
        name: "Qumqo‘rg‘on ustalari",
        avatar_url: "",
        is_own: false,
        is_followed: true,
        has_unseen: true,
        distance_km: null,
        stories: [followedStory],
      }]),
      recordStoryView: vi.fn().mockResolvedValue({ ok: true, counted: true }),
      getStoryViewers: vi.fn().mockResolvedValue([]),
      deleteStory: vi.fn().mockResolvedValue({ ok: true }),
      reportStory: vi.fn().mockResolvedValue({ ok: true }),
    };
    const { onOpenPublicResult } = renderHome(undefined, { storyApi });

    const storyButton = await screen.findByRole("button", {
      name: "Qumqo‘rg‘on ustalari istoriyasini ko‘rish",
    });
    const ownStoryButton = screen.getByRole("button", {
      name: "Sizning istoriyangizni ko‘rish",
    });
    expect(document.querySelectorAll("#followedProfileStrip")).toHaveLength(1);
    expect(document.querySelector(".story-rail-modular")).not.toBeInTheDocument();
    expect(ownStoryButton).toHaveClass("story-card", "unseen");
    expect(ownStoryButton.querySelector(".story-thumb")).toBeInTheDocument();
    expect(ownStoryButton.querySelector(".story-name")).toHaveTextContent("Siz");
    expect(storyButton).toHaveClass("story-card", "unseen");
    expect(storyButton.querySelector(".story-thumb")).toBeInTheDocument();
    expect(screen.queryByText("Mening istoriyam")).not.toBeInTheDocument();

    await userEvent.click(ownStoryButton);

    expect(screen.getByRole("dialog", { name: "Istoriya ko‘ruvchisi" }))
      .toBeInTheDocument();
    expect(screen.getByText("Mening istoriyam")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Yopish" }));

    await userEvent.click(storyButton);

    expect(screen.getByRole("dialog", { name: "Istoriya ko‘ruvchisi" }))
      .toBeInTheDocument();
    expect(screen.getByText("Yangi xizmat")).toBeInTheDocument();
    expect(onOpenPublicResult).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", {
      name: "Qumqo‘rg‘on ustalari profilini ochish",
    }));

    expect(screen.queryByRole("dialog", { name: "Istoriya ko‘ruvchisi" }))
      .not.toBeInTheDocument();
    expect(onOpenPublicResult).toHaveBeenCalledWith("business", "biz_41");
  });

  it("keeps search results on Home and updates the exact count", async () => {
    const { onSearch, searchPublic } = renderHome("Qumqo‘rg‘on tumani");

    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "usta{enter}",
    );

    expect(await screen.findByText("Natijalar — 1 ta")).toBeInTheDocument();
    expect(screen.getAllByText("Qumqo‘rg‘on ustalari").length)
      .toBeGreaterThan(0);
    expect(searchPublic).toHaveBeenCalledWith({
      q: "usta",
      region: "Surxondaryo viloyati",
      district: "Qumqo‘rg‘on tumani",
      page: 1,
      page_size: 20,
    });
    expect(onSearch).not.toHaveBeenCalled();
  });

  it("renders a business with the exact modular section and card classes", async () => {
    renderHome();

    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "usta{enter}",
    );

    expect(await screen.findByText("🏪 Bizneslar")).toHaveClass("list-sub");
    expect(document.querySelector("#resList .biz-name")?.closest(".biz-card"))
      .toBeInTheDocument();
  });

  it("renders a searchable E'lon and opens its migrated detail target", async () => {
    const searchPublic = vi.fn().mockResolvedValue({
      items: [{
        kind: "listing" as const,
        public_id: "l_flat",
        name: "3 xonali kvartira",
        public_username: "",
        description: "Markazda",
        direction: "E'lonlar",
        activity_type: "Uy-joy",
        region: "Surxondaryo viloyati",
        district: "Qumqo'rg'on tumani",
        mahalla: "",
        image_url: "",
        price_text: "250 000 000 so'm",
        owner_label: "Muhr",
        map_point: null,
      }],
      page: 1,
      page_size: 20,
      total: 1,
      pages: 1,
    });
    const { onOpenPublicResult } = renderHome(undefined, { searchPublic });

    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "kvartira{enter}",
    );
    expect(await screen.findByText("📣 E'lonlar")).toHaveClass("list-sub");
    await userEvent.click(screen.getByRole("button", { name: /3 xonali kvartira/ }));

    expect(onOpenPublicResult).toHaveBeenCalledWith("listing", "l_flat");
  });

  it("loads the next modular search page from Yana ko'rsatish", async () => {
    const searchPublic = vi.fn().mockImplementation(async ({ page = 1 }) => ({
      items: [{
        kind: "business" as const,
        public_id: `b_${page}`,
        name: page === 1 ? "Birinchi biznes" : "Ikkinchi biznes",
        public_username: "",
        description: "",
        direction: "Savdo",
        activity_type: "",
        region: "",
        district: "",
        mahalla: "",
        image_url: "",
      }],
      page,
      page_size: 1,
      total: 2,
      pages: 2,
    }));
    renderHome(undefined, { searchPublic });
    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "savdo{enter}",
    );

    await userEvent.click(await screen.findByRole("button", {
      name: "Yana ko'rsatish",
    }));

    expect(await screen.findByText("Ikkinchi biznes")).toBeInTheDocument();
    expect(screen.getByText("Birinchi biznes")).toBeInTheDocument();
    expect(screen.getByText("Natijalar — 2 ta")).toBeInTheDocument();
    expect(searchPublic).toHaveBeenLastCalledWith({
      q: "savdo",
      region: "",
      district: "",
      page: 2,
      page_size: 20,
    });
  });

  it("keeps current results and shows the modular toast when more results fail", async () => {
    const searchPublic = vi.fn()
      .mockResolvedValueOnce({
        items: [{
          kind: "business" as const,
          public_id: "b_first",
          name: "Birinchi biznes",
          public_username: "",
          description: "",
          direction: "Savdo",
          activity_type: "",
          region: "",
          district: "",
          mahalla: "",
          image_url: "",
        }],
        page: 1,
        page_size: 20,
        total: 21,
        pages: 2,
      })
      .mockRejectedValueOnce(new Error("Keyingi sahifa yuklanmadi"));
    renderHome(undefined, { searchPublic });
    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "savdo{enter}",
    );

    await userEvent.click(await screen.findByRole("button", {
      name: "Yana ko'rsatish",
    }));

    expect(await screen.findByText("Keyingi sahifa yuklanmadi"))
      .toHaveClass("app-toast", "on");
    expect(screen.getByText("Birinchi biznes")).toBeInTheDocument();
  });

  it("shows the exact modular loading state while a search is pending", async () => {
    const searchPublic = vi.fn(() => new Promise<never>(() => undefined));
    renderHome(undefined, { searchPublic });

    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "usta{enter}",
    );

    expect(screen.getByRole("heading", { name: "Qidirilmoqda…" }))
      .toBeInTheDocument();
    expect(screen.getByText("Iltimos, biroz kuting.")).toBeInTheDocument();
    expect(screen.getByText("Natijalar — 0 ta")).toBeInTheDocument();
  });

  it("shows the server error in the exact modular result container", async () => {
    const searchPublic = vi.fn().mockRejectedValue(new Error("Tarmoq xatosi"));
    renderHome(undefined, { searchPublic });

    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "usta{enter}",
    );

    expect(await screen.findByText("Tarmoq xatosi")).toHaveClass("elon-hint");
    expect(screen.getByText("Natijalar — 0 ta")).toBeInTheDocument();
  });

  it("keeps the newest result when an older request finishes later", async () => {
    let resolveFirst!: (value: Awaited<ReturnType<ApiClient["searchPublic"]>>) => void;
    let resolveSecond!: (value: Awaited<ReturnType<ApiClient["searchPublic"]>>) => void;
    const first = new Promise<Awaited<ReturnType<ApiClient["searchPublic"]>>>(
      (resolve) => { resolveFirst = resolve; },
    );
    const second = new Promise<Awaited<ReturnType<ApiClient["searchPublic"]>>>(
      (resolve) => { resolveSecond = resolve; },
    );
    const searchPublic = vi.fn()
      .mockReturnValueOnce(first)
      .mockReturnValueOnce(second);
    renderHome(undefined, { searchPublic });
    const input = screen.getByPlaceholderText("Nima qidiryapsiz?");

    await userEvent.type(input, "eski{enter}");
    await userEvent.clear(input);
    await userEvent.type(input, "yangi{enter}");
    resolveSecond({
      items: [{
        kind: "business",
        public_id: "b_new",
        name: "Yangi natija",
        public_username: "",
        description: "",
        direction: "Savdo",
        activity_type: "",
        region: "",
        district: "",
        mahalla: "",
        image_url: "",
      }],
      page: 1,
      page_size: 20,
      total: 1,
      pages: 1,
    });
    expect(await screen.findByText("Yangi natija")).toBeInTheDocument();

    resolveFirst({
      items: [{
        kind: "business",
        public_id: "b_old",
        name: "Eski natija",
        public_username: "",
        description: "",
        direction: "Savdo",
        activity_type: "",
        region: "",
        district: "",
        mahalla: "",
        image_url: "",
      }],
      page: 1,
      page_size: 20,
      total: 1,
      pages: 1,
    });

    expect(screen.queryByText("Eski natija")).not.toBeInTheDocument();
    expect(screen.getByText("Yangi natija")).toBeInTheDocument();
  });

  it("clears and refocuses the Home query without closing active results", async () => {
    renderHome();
    const input = screen.getByPlaceholderText("Nima qidiryapsiz?");

    await userEvent.type(input, "usta{enter}");
    expect(await screen.findByText("Natijalar — 1 ta")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", {
      name: "Qidiruvni tozalash",
    }));

    expect(input).toHaveValue("");
    expect(input).toHaveFocus();
    expect(screen.getByText("Natijalar — 1 ta")).toBeInTheDocument();
  });
});
