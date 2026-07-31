import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BusinessProfile } from "./BusinessProfile";


const identity = {
  account_id: 7,
  account_type: "business" as const,
  name: "Muhr",
  login: "muhr1",
  csrf_token: "csrf",
  expires_at: "2026-08-30T08:00:00Z",
};

function profile(direction: string) {
  return {
    account_id: 7,
    name: "Muhr",
    phone: "",
    description: "",
    public_username: "muhr1",
    direction,
    activity_type: "",
    address: "",
    latitude: null,
    longitude: null,
    work_hours: {},
    pay_card: "",
    pay_holder: "",
    pay_qr_object_key: "",
    pay_qr_url: "",
    director: "",
    tax_id: "",
    logo_object_key: "",
    logo_url: "",
    logo_x: 50,
    logo_y: 50,
    logo_zoom: 1,
    followers_count: 0,
    following_count: 0,
    rating_sum: 0,
    rating_count: 0,
    map_visible: true,
    dashboard_snapshot: {},
    recent_activity: [],
    cabinet_payload: {},
  };
}

function renderDirection(direction: string) {
  const current = profile(direction);
  render(
    <BusinessProfile
      api={{
        getSession: vi.fn().mockResolvedValue(identity),
        getBusinessProfile: vi.fn().mockResolvedValue(current),
        updateBusinessProfile: vi.fn().mockResolvedValue(current),
        createUploadGrant: vi.fn(),
        uploadGrantedFile: vi.fn(),
        attachBusinessLogo: vi.fn().mockResolvedValue(current),
        switchCabinet: vi.fn(),
        logout: vi.fn(),
      }}
      identity={identity}
      onLogout={vi.fn()}
      onSwitched={vi.fn()}
    />,
  );
}

describe("CAB_PLANS render pariteti", () => {
  it("ovqatlanishda Stollar va xonalarni chiqarib, begona yo'nalish ekranlarini yashiradi", async () => {
    renderDirection("Umumiy ovqatlanish");
    expect(await screen.findByRole("button", { name: /Stollar va xonalar/ }))
      .toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Navbat boshqaruvi/ }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Kursga yozilishlar/ }))
      .not.toBeInTheDocument();
  });

  it("tibbiyotda Shifokorlar va Navbat boshqaruvini chiqaradi", async () => {
    renderDirection("Tibbiy xizmatlar");
    expect(await screen.findByRole("button", { name: /Shifokorlar/ }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Navbat boshqaruvi/ }))
      .toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Stollar va xonalar/ }))
      .not.toBeInTheDocument();
  });

  it("ta'limda Kursga yozilishlarni chiqarib, buyurtma va navbatni yashiradi", async () => {
    renderDirection("Ta'lim faoliyati");
    expect(await screen.findByRole("button", { name: /Kursga yozilishlar/ }))
      .toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Buyurtmalar/ }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Navbat boshqaruvi/ }))
      .not.toBeInTheDocument();
  });
});
