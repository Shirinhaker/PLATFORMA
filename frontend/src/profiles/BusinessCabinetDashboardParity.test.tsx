import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import frontendBootstrapSource from "../main.tsx?raw";
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
    getBusinessOnlineResource: vi.fn().mockImplementation(async (resource) => ({
      resource,
      items: [],
    })),
    createBusinessOnlineRecord: vi.fn(),
    patchBusinessOnlineRecord: vi.fn(),
    deleteBusinessOnlineRecord: vi.fn(),
    applyBusinessOnlineAction: vi.fn(),
    switchCabinet: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
  } as unknown as BusinessProfileApiV3;
}

function menuTexts(section: HTMLElement) {
  return within(section)
    .getAllByRole("button")
    .map((button) => button.querySelector("b")?.textContent?.trim() ?? "");
}


describe("modular business cabinet dashboard parity", () => {
  it("loads the active dashboard stylesheet globally without the obsolete V2 rules", () => {
    expect(frontendBootstrapSource)
      .toContain('import "./profiles/BusinessCabinetDashboardParity.css";');
    expect(frontendBootstrapSource)
      .not.toContain('import "./profiles/BusinessProfileV2.css";');
  });

  it("shows the owner dashboard with the exact modular group hierarchy", async () => {
    const { container } = render(
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
    expect(container.querySelectorAll(".business-cabinet__menu-grid").length)
      .toBeGreaterThanOrEqual(2);

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

    expect(menuTexts(onlineSection as HTMLElement)).toEqual([
      "Profil / Mening sahifam",
      "Obunalarim",
      "To‘lovlarim",
      "Mahsulotlar",
      "Buyurtmalar",
      "Xizmat buyurtmalari",
      "Suhbatlar",
      "Mijoz fikrlari",
      "Reklamalarim",
      "Istoriya arxivi",
      "Bildirishnomalarim",
    ]);
    expect(within(onlineSection as HTMLElement).queryByRole("button", { name: /E’lonlarim/ }))
      .not.toBeInTheDocument();
    expect(within(onlineSection as HTMLElement).queryByRole("button", { name: /Oshpaz buyurtmalari/ }))
      .not.toBeInTheDocument();

    expect(menuTexts(systemSection as HTMLElement)).toEqual([
      "Kassa",
      "Xarajatlar",
      "Qarz daftari",
      "Ombor",
      "Statistika",
      "Hisobotlar",
      "AI yordamchi",
      "Ma'muriyat",
      "Sozlamalar",
    ]);
  });

  it("keeps modular administration and promotion routes reachable from their hubs", async () => {
    const user = userEvent.setup();
    render(
      <BusinessProfileV3
        api={api()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /Ma'muriyat/ }));
    expect(screen.getByRole("heading", { name: "Ma’muriyat" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Mening hujjatlarim/ }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Xodimlar/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Hujjatlar/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Kabinetga qaytish/ }));
    await user.click(await screen.findByRole("button", { name: /Reklamalarim/ }));
    const promotionHeading = screen.getByRole("heading", {
      name: "E'lonlarim va reklamalarim",
    });
    expect(promotionHeading).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reklamalarim" })).toHaveClass("ad-tab", "on");
    await user.click(screen.getByRole("button", { name: "E'lonlarim" }));
    expect(await screen.findByRole("heading", {
      name: "E'lonlarim va reklamalarim",
    })).toBe(promotionHeading);
    expect(screen.getByRole("button", { name: "E'lonlarim" })).toHaveClass("ad-tab", "on");
    await user.click(screen.getByRole("button", { name: "Reklamalarim" }));
    expect(await screen.findByRole("heading", {
      name: "E'lonlarim va reklamalarim",
    })).toBe(promotionHeading);
    expect(screen.getByRole("button", { name: "Reklamalarim" })).toHaveClass("ad-tab", "on");
  });

  it("keeps the dining kitchen reachable without a separate main-grid card", async () => {
    const user = userEvent.setup();
    const client = api();
    client.getBusinessProfile = vi.fn().mockResolvedValue({
      ...profile,
      direction: "Umumiy ovqatlanish",
    });
    Object.assign(client, {
      getDiningOrders: vi.fn().mockResolvedValue([]),
      setDiningKitchenStatus: vi.fn(),
    });
    render(
      <BusinessProfileV3
        api={client}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    const dashboard = await screen.findByRole("heading", { name: "Muhr" });
    const main = dashboard.closest("main");
    expect(main).not.toBeNull();
    expect(within(main as HTMLElement).queryByRole(
      "button",
      { name: /Oshpaz buyurtmalari/ },
    )).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Stollar va xonalar/ }));
    await user.click(screen.getByRole("button", { name: "Oshpaz buyurtmalari" }));
    expect(screen.getByRole("button", { name: "Oshpaz buyurtmalari" }))
      .toHaveClass("ad-tab", "on");
    expect(await screen.findByRole("heading", { name: "Buyurtma yo‘q" }))
      .toBeInTheDocument();
  });

  it("has one modular Ordinary cabinet action and keeps logout out of the dashboard", async () => {
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
