import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";


const userIdentity = {
  account_id: 5,
  account_type: "user" as const,
  name: "Ali",
  login: "u_ali",
  csrf_token: "csrf",
  expires_at: "2026-08-27T08:00:00Z",
};

const businessIdentity = {
  account_id: 7,
  account_type: "business" as const,
  name: "Turon",
  login: "b_turon",
  csrf_token: "csrf",
  expires_at: "2026-08-27T08:00:00Z",
};

const userProfile = {
  account_id: 5,
  name: "Ali",
  phone: "",
  public_username: "",
  region: "",
  district: "",
  mahalla: "",
  latitude: null,
  longitude: null,
  location_exact: false,
  avatar_object_key: "",
  avatar_x: 50,
  avatar_y: 50,
  avatar_zoom: 1,
  followers_count: 0,
  following_count: 0,
  has_business: false,
  dashboard_snapshot: {},
  recent_activity: [],
  specialist_profile: {},
  cabinet_payload: {},
};

const businessProfile = {
  account_id: 7,
  name: "Turon",
  phone: "",
  description: "",
  public_username: "",
  direction: "",
  activity_type: "",
  address: "",
  latitude: null,
  longitude: null,
  work_hours: {},
  pay_card: "",
  pay_holder: "",
  pay_qr_object_key: "",
  director: "",
  tax_id: "",
  logo_object_key: "",
  logo_x: 50,
  logo_y: 50,
  logo_zoom: 1,
  followers_count: 0,
  following_count: 0,
  rating_sum: 0,
  rating_count: 0,
  map_visible: false,
  dashboard_snapshot: {},
  recent_activity: [],
  cabinet_payload: {},
};

function unauthorized() {
  return Object.assign(new Error("unauthorized"), { status: 401 });
}

function guestApi() {
  return {
    getSession: vi.fn().mockRejectedValue(unauthorized()),
    startRegistration: vi.fn(),
    startLogin: vi.fn(),
    verifyRegistration: vi.fn(),
    verifyLogin: vi.fn(),
    resendChallenge: vi.fn(),
  };
}

function saveHomeLocation() {
  window.localStorage.setItem(
    "koprik_home_location_v1",
    JSON.stringify({
      region: "Surxondaryo viloyati",
      district: "Qumqo‘rg‘on tumani",
      mahalla: "",
      lat: 37.82,
      lng: 67.58,
      exact: false,
    }),
  );
}

function profileApi(identity = userIdentity) {
  return {
    getSession: vi.fn().mockResolvedValue(identity),
    getUserProfile: vi.fn().mockResolvedValue(userProfile),
    updateUserProfile: vi.fn().mockResolvedValue(userProfile),
    getBusinessProfile: vi.fn().mockResolvedValue(businessProfile),
    updateBusinessProfile: vi.fn().mockResolvedValue(businessProfile),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    attachUserAvatar: vi.fn().mockResolvedValue(userProfile),
    attachBusinessLogo: vi.fn().mockResolvedValue(businessProfile),
    switchCabinet: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
  };
}


describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("requires a district before opening Home for the first time", async () => {
    render(<App api={guestApi()} />);

    expect(
      await screen.findByRole("heading", { name: "Hududingizni tanlang" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kabinet" }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Koprik’ga kirish" }))
      .not.toBeInTheDocument();
  });

  it("starts a returning guest on the public Home", async () => {
    saveHomeLocation();
    render(<App api={guestApi()} />);

    expect(
      await screen.findByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kabinet" }))
      .toBeInTheDocument();
  });

  it("opens the migrated E’lonlar screen while still hiding unowned actions", async () => {
    const user = userEvent.setup();
    saveHomeLocation();
    const api = {
      ...guestApi(),
      getPublicFeatures: vi.fn().mockResolvedValue({
        listings: true,
        stories: false,
        chat: false,
        systemization: false,
        taxi: true,
      }),
      getListingCounts: vi.fn().mockResolvedValue({ uy: 1 }),
      getPublicListings: vi.fn().mockResolvedValue([]),
      toggleListingSave: vi.fn(),
    };
    render(<App api={api} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });

    const listings = screen.getByRole("button", { name: "E’lonlar" });
    await user.click(listings);
    expect(screen.getByRole("heading", { name: "E’lonlar" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Savat" }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Taxi bo'limi" }))
      .not.toBeInTheDocument();
  });

  it("opens a district listing offer in the migrated detail screen", async () => {
    const user = userEvent.setup();
    saveHomeLocation();
    const detail = {
      public_id: "l_1234567890abcdef",
      cat: "uy" as const,
      title: "3 xonali kvartira",
      price: "Kelishilgan",
      descr: "Markazda",
      address: "Qumqo‘rg‘on",
      lat: 37.82,
      lng: 67.58,
      visibility: "all" as const,
      status: "active" as const,
      created_at: "2026-08-02T10:00:00Z",
      media: [],
      owner_kind: "business" as const,
      owner_public_id: "b_1234567890abcdef",
      owner_name: "Muhr",
      is_saved: false,
    };
    const api = {
      ...guestApi(),
      getDistrictOffers: vi.fn().mockResolvedValue({
        needs_district: false,
        items: [{
          kind: "listing" as const,
          business_id: 7,
          business_public_id: "b_1234567890abcdef",
          content_id: 31,
          content_public_id: detail.public_id,
          title: detail.title,
          business_name: "Muhr",
          image: "",
          business_logo: "",
          price: detail.price,
          unit: "",
        }],
      }),
      getPublicListing: vi.fn().mockResolvedValue(detail),
      toggleListingSave: vi.fn(),
    };

    render(<App api={api} />);
    await user.click(await screen.findByRole("button", { name: /3 xonali kvartira/ }));

    expect(await screen.findByRole("heading", { name: "3 xonali kvartira" }))
      .toBeInTheDocument();
    expect(api.getPublicListing).toHaveBeenCalledWith(detail.public_id);
  });

  it("switches the v1656 theme palette and icon from the Home header", async () => {
    saveHomeLocation();
    document.documentElement.dataset.theme = "light";
    render(<App api={guestApi()} />);
    const button = await screen.findByRole("button", {
      name: "Rang rejimini almashtirish",
    });

    expect(button.querySelector("path"))
      .toHaveAttribute("d", "M21 12.8A8.5 8.5 0 1 1 11.2 3a6.6 6.6 0 0 0 9.8 9.8z");
    await userEvent.click(button);

    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(button.querySelector("circle")).toHaveAttribute("r", "4.5");
  });

  it("opens the existing authentication flow from the public header", async () => {
    const user = userEvent.setup();
    saveHomeLocation();
    render(<App api={guestApi()} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.click(screen.getByRole("button", { name: "Kabinet" }));

    expect(
      screen.getByRole("heading", { name: "Koprik’ga kirish" }),
    ).toBeInTheDocument();
  });

  it("opens the matching cabinet after a completed login", async () => {
    const user = userEvent.setup();
    saveHomeLocation();
    const api = guestApi();
    api.getSession
      .mockRejectedValueOnce(unauthorized())
      .mockResolvedValue(businessIdentity);
    api.startLogin.mockResolvedValue({
      request_id: 13,
      deep_link: "https://t.me/koprik_bot?start=login-token",
      code_sent: true,
      expires_in: 300,
      resend_after: 0,
    });
    api.verifyLogin.mockResolvedValue({
      account_id: 7,
      account_type: "business",
      csrf_token: "csrf",
      expires_at: "2026-08-27T08:00:00Z",
    });

    render(<App api={api} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.click(screen.getByRole("button", { name: "Kabinet" }));
    await user.click(
      screen.getAllByRole("button", { name: "Kirish" }).at(-1)!,
    );
    await user.type(screen.getByLabelText("Login"), "b_turon");
    await user.type(screen.getByLabelText("Parol"), "secret-42");
    await user.click(screen.getByRole("button", { name: "Davom etish" }));
    await user.type(await screen.findByLabelText("6 xonali kod"), "123456");
    await user.click(screen.getByRole("button", { name: "Tasdiqlash" }));

    expect(
      await screen.findByRole("heading", { name: "Biznes kabinet" }),
    ).toBeInTheDocument();
  });

  it("starts an authenticated session on Home and opens Cabinet on demand", async () => {
    const user = userEvent.setup();
    saveHomeLocation();
    const api = {
      getSession: vi.fn().mockResolvedValue(businessIdentity),
    };

    render(<App api={api} />);

    expect(
      await screen.findByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Biznes kabinet" }))
      .not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Kabinet" }));
    expect(
      screen.getByRole("heading", { name: "Biznes kabinet" }),
    ).toBeInTheDocument();
  });

  it("returns to the public home after cabinet logout", async () => {
    const user = userEvent.setup();
    saveHomeLocation();
    const api = profileApi();
    render(<App api={api} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.click(screen.getByRole("button", { name: "Kabinet" }));
    await screen.findByRole("heading", { name: "Ali" });
    await user.click(screen.getByRole("button", { name: "Chiqish" }));

    expect(api.logout).toHaveBeenCalledOnce();
    expect(
      await screen.findByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kabinet" }))
      .toBeInTheDocument();
  });

  it("keeps Home search results inline", async () => {
    const user = userEvent.setup();
    saveHomeLocation();
    const api = {
      ...guestApi(),
      searchPublic: vi.fn().mockResolvedValue({
        items: [{
          kind: "business",
          public_id: "biz_41",
          name: "Telefon ustasi",
          public_username: "telefon-ustasi",
          description: "Telefon ta’miri",
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
    };
    render(<App api={api} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.type(screen.getByPlaceholderText("Nima qidiryapsiz?"), "telefon");
    await user.click(screen.getByRole("button", { name: "Qidirish" }));

    expect(await screen.findByText("Natijalar — 1 ta")).toBeInTheDocument();
    expect(document.querySelector(".app-shell"))
      .toHaveClass("search-results-active");
    expect(document.querySelector("#resList"))
      .toHaveTextContent("Telefon ustasi");
    expect(document.querySelector("#leafletMap .leaflet-pin"))
      .not.toBeInTheDocument();
    expect(api.searchPublic).toHaveBeenCalledWith({
      q: "telefon",
      region: "Surxondaryo viloyati",
      district: "Qumqo‘rg‘on tumani",
      page: 1,
      page_size: 20,
    });
    expect(
      screen.getByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      }),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Qidiruvni tozalash" }),
    );
    expect(document.querySelector(".app-shell"))
      .toHaveClass("search-results-active");
    await user.click(
      screen.getByRole("button", { name: /Qidiruv natijalari/ }),
    );
    expect(document.querySelector(".app-shell"))
      .not.toHaveClass("search-results-active");
  });

  it("opens an followed business profile from its Home card", async () => {
    const user = userEvent.setup();
    saveHomeLocation();
    const api = {
      ...profileApi(),
      getFollowedProfiles: vi.fn().mockResolvedValue([
        {
          kind: "business",
          public_id: "b_first",
          name: "Birinchi biznes",
          image_url: "",
          crop_x: 50,
          crop_y: 50,
          crop_zoom: 1,
        },
        {
          kind: "business",
          public_id: "b_second",
          name: "Ikkinchi biznes",
          image_url: "",
          crop_x: 50,
          crop_y: 50,
          crop_zoom: 1,
        },
      ]),
      getPublicProfile: vi.fn().mockResolvedValue({
        kind: "business",
        public_id: "b_second",
        name: "Ikkinchi biznes",
        public_username: "ikkinchi",
        description: "",
        direction: "Savdo",
        activity_type: "Do‘kon",
        address: "Qumqo‘rg‘on",
        phone: "",
        image_url: "",
        crop_x: 50,
        crop_y: 50,
        crop_zoom: 1,
        followers_count: 2,
        specialist: null,
        items: [],
        listings: [],
      }),
    };

    render(<App api={api} />);

    await user.click(await screen.findByRole("button", {
      name: "Ikkinchi biznes profilini ochish",
    }));

    expect(await screen.findByText("Savdo · Do‘kon")).toBeInTheDocument();
    expect(api.getPublicProfile).toHaveBeenCalledWith(
      "business",
      "b_second",
    );
  });

  it("navigates Catalog to Category and back", async () => {
    const user = userEvent.setup();
    saveHomeLocation();
    render(<App api={guestApi()} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.click(
      screen.getByRole("button", { name: /^Katalog bo‘yicha/ }),
    );
    await user.click(
      screen.getByRole("button", { name: /^Savdo —/ }),
    );
    expect(screen.getByRole("heading", { name: "Savdo" }))
      .toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Orqaga" }));
    expect(
      screen.getByRole("heading", { name: "Faoliyat yo‘nalishlari" }),
    ).toBeInTheDocument();
  });

  it("updates the Home district after location save", async () => {
    const user = userEvent.setup();
    render(<App api={guestApi()} />);

    await screen.findByRole("heading", { name: "Hududingizni tanlang" });
    await user.selectOptions(
      screen.getByLabelText("Viloyat / shahar"),
      "Toshkent shahri",
    );
    await user.selectOptions(screen.getByLabelText("Tuman"), "Chilonzor");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect((await screen.findAllByText("Chilonzor")).length)
      .toBeGreaterThanOrEqual(2);
  });

  it("keeps public location usable when session bootstrap fails", async () => {
    const user = userEvent.setup();
    const api = {
      getSession: vi.fn().mockRejectedValue(new TypeError("offline")),
    };

    render(<App api={api} />);

    expect(
      await screen.findByRole("heading", { name: "Hududingizni tanlang" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps the retryable session error on account views", async () => {
    const user = userEvent.setup();
    saveHomeLocation();
    const api = {
      getSession: vi.fn()
        .mockRejectedValueOnce(new TypeError("offline"))
        .mockResolvedValueOnce(userIdentity),
    };

    render(<App api={api} />);

    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    });
    await user.click(screen.getByRole("button", { name: "Kabinet" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Server bilan bog‘lanib bo‘lmadi.",
    );

    await user.click(screen.getByRole("button", { name: "Qayta urinish" }));

    expect(
      await screen.findByRole("heading", { name: "Oddiy kabinet" }),
    ).toBeInTheDocument();
    expect(api.getSession).toHaveBeenCalledTimes(2);
  });
});
