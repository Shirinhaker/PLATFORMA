import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { UserProfile as UserProfileData } from "../api/types";
import { UserProfile } from "./UserProfile";

const identity = {
  account_id: 5,
  account_type: "user" as const,
  name: "Ali Valiyev",
  login: "u_ali",
  csrf_token: "csrf",
  expires_at: "2026-08-27T08:00:00Z",
};

const profile = {
  account_id: 5,
  public_id: "u_1234567890abcdef",
  name: "Ali Valiyev",
  phone: "+998 90 123 45 67",
  public_username: "ali",
  region: "Surxondaryo viloyati",
  district: "Qumqo‘rg‘on tumani",
  mahalla: "Bunyodkor",
  latitude: 37.8,
  longitude: 67.5,
  location_exact: true,
  avatar_object_key: "private/user/5/avatar/0123456789abcdef0123456789abcdef.webp",
  avatar_url: "https://media.example/ali.webp",
  avatar_x: 42,
  avatar_y: 58,
  avatar_zoom: 1.25,
  followers_count: 3,
  following_count: 2,
  has_business: true,
  dashboard_snapshot: {
    active_orders: 1,
    following: 2,
    saved: 4,
    unread: 5,
  },
  recent_activity: [
    {
      id: 46,
      kind: "order",
      title: "Muhr",
      status: "new",
      amount: 350000,
      created_at: 1722211200,
    },
  ],
  specialist_profile: {},
  cabinet_payload: {},
} satisfies UserProfileData;

const advertisement = {
  id: 12,
  title: "Oddiy profil reklamasi",
  caption: "Yangi taklif",
  targets: [
    {
      level: "district" as const,
      region: "Surxondaryo viloyati",
      district: "Qumqo‘rg‘on tumani",
    },
  ],
  placement: "home",
  status: "payment_pending",
  daily_all_day: true,
  daily_start: "00:00",
  daily_end: "00:00",
  duration_days: 1,
  district_count: 1,
  hours_per_day: 24,
  district_hour_rate: 20_000,
  billable_district_hours: 24,
  price: 480_000,
  price_code: "advertisement_district_hour",
  start_at: 1_786_000_000,
  end_at: 1_786_086_400,
  views: 0,
  clicks: 0,
  desktop_image_url: "https://media.example/ad.webp",
  mobile_image_url: "",
  created_at: 1_785_000_000,
};

const listing = {
  public_id: "l_1234567890abcdef",
  cat: "uy" as const,
  title: "Oddiy profil e'loni",
  price: "Kelishilgan",
  descr: "Tafsilot",
  address: "Qumqo‘rg‘on",
  lat: 37.82,
  lng: 67.58,
  visibility: "all" as const,
  status: "active" as const,
  created_at: "2026-08-02T10:00:00Z",
  media: [],
  owner_kind: "user" as const,
  owner_public_id: "u_1234567890abcdef",
  owner_name: "Ali Valiyev",
  is_saved: false,
};

function profileApi() {
  return {
    getSession: vi.fn().mockResolvedValue(identity),
    getUserProfile: vi.fn().mockResolvedValue(profile),
    updateUserProfile: vi.fn().mockImplementation(async (patch) => ({
      ...profile,
      ...patch,
    })),
    createUploadGrant: vi.fn().mockResolvedValue({
      object_key: "private/user/5/avatar/abcdefabcdefabcdefabcdefabcdefab.png",
      upload_url: "https://r2.example/upload",
      method: "PUT" as const,
      headers: { "Content-Type": "image/png" },
      expires_in_seconds: 900,
    }),
    uploadGrantedFile: vi.fn().mockResolvedValue(undefined),
    attachUserAvatar: vi.fn().mockImplementation(async (attachment) => ({
      ...profile,
      avatar_object_key: attachment.object_key,
      avatar_url: "https://media.example/new-avatar.png",
      avatar_x: attachment.x,
      avatar_y: attachment.y,
      avatar_zoom: attachment.zoom,
    })),
    switchCabinet: vi.fn(),
    logout: vi.fn(),
  };
}

describe("v1656 user cabinet and profile parity", () => {
  it("switches ordinary profile advertisements and listings tabs both ways", async () => {
    const user = userEvent.setup();
    const api = {
      ...profileApi(),
      getMyAdvertisements: vi.fn().mockResolvedValue([advertisement]),
      createAdvertisement: vi.fn().mockResolvedValue(advertisement),
      deleteAdvertisement: vi.fn().mockResolvedValue(undefined),
      quoteAdvertisement: vi.fn(),
      getMyListings: vi.fn().mockResolvedValue([listing]),
      createListing: vi.fn(),
      deleteListing: vi.fn(),
      getPaymentCatalog: vi.fn().mockResolvedValue({
        prices: [
          {
            price_code: "advertisement_district_hour",
            service_type: "advertisement" as const,
            amount_uzs: 20_000,
            currency: "UZS",
            plan_code: "",
            duration_months: 0,
            config: {},
          },
        ],
        methods: [
          {
            id: 1,
            method_type: "manual_card",
            name: "Bank kartasi",
            recipient_name: "Koprik",
            instructions: "",
            details: { card: "8600" },
          },
        ],
      }),
      createPaymentRequest: vi.fn(),
    };
    render(
      <UserProfile
        api={api}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: /Reklamalarim Bosh sahifa reklamalarini boshqarish/,
      }),
    );
    expect(await screen.findByText("Oddiy profil reklamasi")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reklamalarim" })).toHaveClass("on");
    expect(api.getPaymentCatalog).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "To‘lov qilish" }));
    expect(
      await screen.findByRole("dialog", {
        name: "To‘lov so‘rovini yuborish",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("480 000 so‘m")).toBeInTheDocument();
    expect(api.getPaymentCatalog).toHaveBeenCalledOnce();
    await user.click(screen.getByRole("button", { name: "Yopish" }));

    await user.click(screen.getByRole("button", { name: "E'lonlarim" }));
    expect(await screen.findByText("Oddiy profil e'loni")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "E'lonlarim" })).toHaveClass("on");

    await user.click(screen.getByRole("button", { name: "Reklamalarim" }));
    expect(await screen.findByText("Oddiy profil reklamasi")).toBeInTheDocument();
  });

  it("renders the exact v1656 dashboard labels and descriptions", async () => {
    render(
      <UserProfile
        api={profileApi()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Ali Valiyev" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Profil va faoliyatlar")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Profilim Ism, telefon, yashash tumani/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /Reklamalarim Bosh sahifa reklamalarini boshqarish/,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /Istoriya arxivi Faol va arxivdagi shaxsiy istoriyalar/,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "So‘nggi faollik" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Buyurtma #46 — Muhr")).toBeInTheDocument();
  });

  it("renders the v1656 profile card, fields and local share QR", async () => {
    const user = userEvent.setup();
    render(
      <UserProfile
        api={profileApi()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: /Profilim Ism, telefon, yashash tumani/,
      }),
    );

    expect(
      screen.getByRole("img", { name: "Ali Valiyev profil rasmi" }),
    ).toHaveAttribute("src", profile.avatar_url);
    expect(
      screen.getByText("Qumqo‘rg‘on tumani, Surxondaryo viloyati"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Ism familiya")).toHaveValue("Ali Valiyev");
    expect(screen.getByLabelText("Telefon")).toHaveValue("+998 90 123 45 67");
    expect(screen.getByLabelText("Username (sahifa manzili)")).toHaveValue("ali");
    expect(screen.getByText("🔗 Sahifa havolasi")).toBeInTheDocument();
    expect(
      (screen.getByLabelText("Foydalanuvchi sahifasi havolasi") as HTMLInputElement)
        .value,
    ).toContain("?user=u_1234567890abcdef");
    expect(screen.getByLabelText("Foydalanuvchi sahifasi QR kodi")).toBeInTheDocument();
    expect(screen.queryByLabelText("Viloyat")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Kenglik")).not.toBeInTheDocument();
    expect(screen.queryByText("Avatar kesimi")).not.toBeInTheDocument();
  });

  it("normalizes the username and saves only changed profile fields", async () => {
    const user = userEvent.setup();
    const api = profileApi();
    render(
      <UserProfile
        api={api}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: /Profilim Ism, telefon, yashash tumani/,
      }),
    );
    const username = screen.getByLabelText("Username (sahifa manzili)");
    await user.clear(username);
    await user.type(username, "@Ali-Test_2");
    expect(username).toHaveValue("alitest_2");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(api.updateUserProfile).toHaveBeenCalledWith({
      public_username: "alitest_2",
    });
    expect(await screen.findByText("Saqlandi ✅")).toBeInTheDocument();
  });

  it("uploads an avatar and persists the visual crop position", async () => {
    const user = userEvent.setup();
    const api = profileApi();
    const rendered = render(
      <UserProfile
        api={api}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );
    await user.click(
      await screen.findByRole("button", {
        name: /Profilim Ism, telefon, yashash tumani/,
      }),
    );
    const fileInput = rendered.container.querySelector(
      'input[type="file"][accept*="image/jpeg"]',
    );
    expect(fileInput).toBeInstanceOf(HTMLInputElement);
    await user.upload(
      fileInput as HTMLInputElement,
      new File(["image"], "avatar.png", { type: "image/png" }),
    );

    expect(api.uploadGrantedFile).toHaveBeenCalledOnce();
    expect(api.attachUserAvatar).toHaveBeenCalledWith(
      expect.objectContaining({
        object_key: "private/user/5/avatar/abcdefabcdefabcdefabcdefabcdefab.png",
      }),
    );
    const zoom = await screen.findByLabelText("Kattalashtirish");
    fireEvent.change(zoom, { target: { value: "1.8" } });
    await user.click(screen.getByRole("button", { name: "Rasm joylashuvini saqlash" }));
    expect(api.attachUserAvatar).toHaveBeenLastCalledWith(
      expect.objectContaining({
        zoom: 1.8,
      }),
    );
  });
});
