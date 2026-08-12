import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import dashboardParityCss from "./BusinessCabinetDashboardParityV1656.css?raw";
import businessProfileSource from "./BusinessProfileV3.tsx?raw";
import {
  BusinessProfileV3,
  type BusinessProfileApiV3,
} from "./BusinessProfileV3";


const identity = {
  account_id: 7,
  account_type: "business" as const,
  actor_type: "owner" as const,
  name: "Muhr",
  login: "b_muhr",
  csrf_token: "csrf",
  expires_at: "2026-08-30T00:00:00Z",
};

const profile = {
  account_id: 7,
  name: "Muhr",
  phone: "912377784",
  description: "",
  public_username: "muhr1",
  direction: "Savdo",
  activity_type: "Oziq-ovqat do'koni",
  address: "Qumqo‘rg‘on tumani",
  latitude: 37.8,
  longitude: 67.5,
  work_hours: { raw: "09:00-20:00" },
  pay_card: "",
  pay_holder: "",
  pay_qr_object_key: "",
  pay_qr_url: "",
  director: "",
  tax_id: "",
  logo_object_key: "private/business/7/logo/logo.png",
  logo_url: "https://media.example/logo.png",
  logo_x: 50,
  logo_y: 50,
  logo_zoom: 1,
  followers_count: 2,
  following_count: 1,
  rating_sum: 0,
  rating_count: 0,
  map_visible: true,
  dashboard_snapshot: {
    revenue: 214500,
    new_orders: 1,
    debt_total: 0,
    low_stock: 0,
    active_orders: 1,
  },
  recent_activity: [],
  cabinet_payload: {},
};

function api() {
  return {
    getSession: vi.fn().mockResolvedValue({
      ...identity,
      account_type: "user" as const,
      actor_type: "user" as const,
    }),
    getBusinessProfile: vi.fn().mockResolvedValue(profile),
    updateBusinessProfile: vi.fn(),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    attachBusinessLogo: vi.fn(),
    switchCabinet: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
  } as unknown as BusinessProfileApiV3;
}

function menuTexts(section: HTMLElement) {
  return within(section)
    .getAllByRole("button")
    .map((button) => button.querySelector("b")?.textContent?.trim() ?? "");
}


describe("v1656 business cabinet dashboard parity", () => {
  it("keeps the dashboard CSS scoped and restores the v1656 three-column menu", () => {
    expect(businessProfileSource)
      .toContain('import "./BusinessCabinetDashboardParityV1656.css";');
    expect(dashboardParityCss).toContain(".business-cabinet__menu-grid");
    expect(dashboardParityCss)
      .toContain("grid-template-columns: repeat(3, minmax(0, 1fr));");
    expect(dashboardParityCss)
      .toContain("grid-template-columns: minmax(0, 1.55fr) minmax(260px, .8fr);");
  });

  it("shows the owner dashboard with the exact v1656 group hierarchy", async () => {
    render(
      <BusinessProfileV3
        api={api()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Muhr" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Boshqaruv bo‘limlari" }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Profilni ko‘rish" }))
      .toBeInTheDocument();

    const onlineHeading = screen.getByRole("heading", { name: "Onlaynlashtirish" });
    const systemHeading = screen.getByRole("heading", { name: "Tizimlashtirish" });
    expect(onlineHeading).toBeInTheDocument();
    expect(systemHeading).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Ma’muriyat" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Yo‘nalishga xos bo‘limlar" }))
      .not.toBeInTheDocument();

    const onlineSection = onlineHeading.closest("section");
    const systemSection = systemHeading.closest("section");
    expect(onlineSection).not.toBeNull();
    expect(systemSection).not.toBeNull();

    expect(menuTexts(onlineSection as HTMLElement)).toEqual(expect.arrayContaining([
      "Profil ma’lumotlari",
      "Obuna va tarifim",
      "To‘lovlar",
      "Mahsulot / Xizmatlar",
      "Buyurtmalarim",
      "Xizmat buyurtmalari",
      "Suhbatlar",
      "Mijoz fikrlari",
      "Reklamalarim",
      "Istoriyalar",
      "Bildirishnomalar",
    ]));
    expect(within(onlineSection as HTMLElement).queryByRole("button", { name: /E’lonlarim/ }))
      .not.toBeInTheDocument();
    expect(within(onlineSection as HTMLElement).queryByRole("button", { name: /Oshpaz buyurtmalari/ }))
      .not.toBeInTheDocument();

    expect(menuTexts(systemSection as HTMLElement)).toEqual(expect.arrayContaining([
      "Kassa",
      "Kassa tahlili",
      "Xodimlar",
      "Buyurtmalar",
      "Ombor",
      "Xarajatlar",
      "Qarz",
      "Hujjatlar",
      "AI yordamchi",
      "Ma’muriyat",
    ]));
  });

  it("has one v1656 Ordinary cabinet action and keeps logout out of the dashboard", async () => {
    const user = userEvent.setup();
    const client = api();
    const onSwitched = vi.fn();
    render(
      <BusinessProfileV3
        api={client}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={onSwitched}
      />,
    );

    const switchButton = await screen.findByRole("button", { name: "Oddiy kabinet" });
    expect(screen.getAllByRole("button", { name: "Oddiy kabinet" })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Chiqish" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Oddiy kabinetga qaytish/ }))
      .not.toBeInTheDocument();

    await user.click(switchButton);
    expect(client.switchCabinet).toHaveBeenCalledWith("user");
    expect(onSwitched).toHaveBeenCalledTimes(1);
  });
});
