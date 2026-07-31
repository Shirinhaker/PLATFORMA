import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

const profile = {
  account_id: 7,
  name: "Muhr",
  phone: "912377784",
  description: "",
  public_username: "muhr1",
  direction: "Savdo",
  activity_type: "Oziq-ovqat do'koni",
  address: "Qumqo‘rg‘on",
  latitude: 37.83,
  longitude: 67.58,
  work_hours: { raw: "09:00-20:00" },
  pay_card: "5614681918687751",
  pay_holder: "BUNYOD ASHUROV",
  pay_qr_object_key: "",
  pay_qr_url: "",
  director: "",
  tax_id: "",
  logo_object_key: "",
  logo_url: "",
  logo_x: 50,
  logo_y: 50,
  logo_zoom: 1,
  followers_count: 2,
  following_count: 1,
  rating_sum: 9,
  rating_count: 2,
  map_visible: true,
  dashboard_snapshot: {
    revenue: 0,
    new_orders: 2,
    debt_total: 214500,
    low_stock: 0,
  },
  recent_activity: [],
  cabinet_payload: {
    business_subscriptions: [{ id: 1, plan: "free", status: "active" }],
    subscription_payments: [{ id: 2, status: "approved", amount_snapshot: 149000 }],
    item_groups: [{ id: 10, name: "Tayyor mahsulotlar", kind: "product" }],
    items: [{ id: 11, group_id: 10, name: "Muhr", kind: "product", price: 15000 }],
    listings: [{ id: 12, title: "Biznes e’loni", status: "active" }],
    orders: [],
    messages: [],
    business_reviews: [],
    advertisements: [],
    stories: [],
    notifications: [],
    followers: [],
    following: [],
  },
};

function api() {
  return {
    getSession: vi.fn().mockResolvedValue(identity),
    getBusinessProfile: vi.fn().mockResolvedValue(profile),
    updateBusinessProfile: vi.fn().mockResolvedValue(profile),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    attachBusinessLogo: vi.fn().mockResolvedValue(profile),
    attachBusinessPaymentQr: vi.fn().mockResolvedValue(profile),
    switchCabinet: vi.fn(),
    logout: vi.fn(),
  };
}

async function back(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /Kabinetga qaytish/ }));
  await screen.findByRole("heading", { name: "Muhr" });
}


describe("v1656 online cabinet parity", () => {
  it("uses dedicated subscription, payment, item and listing screens", async () => {
    const user = userEvent.setup();
    render(
      <BusinessProfile
        api={api()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );
    await screen.findByRole("heading", { name: "Muhr" });

    await user.click(screen.getByRole("button", { name: /Obunalarim/ }));
    expect(await screen.findByRole("heading", { name: "Obunalarim" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "1 oy" })).toBeInTheDocument();

    await back(user);
    await user.click(screen.getByRole("button", { name: /To‘lovlarim/ }));
    expect(await screen.findByRole("heading", { name: "To‘lovlarim" })).toBeInTheDocument();

    await back(user);
    await user.click(screen.getByRole("button", { name: /Mahsulot va xizmatlar/ }));
    expect(await screen.findByPlaceholderText("Tovar qidirish...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\+ Guruh qo'shish/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tovar qo'shish" })).toBeInTheDocument();
    expect(screen.getByText("Muhr")).toBeInTheDocument();

    await back(user);
    await user.click(screen.getByRole("button", { name: /E’lonlarim/ }));
    expect(await screen.findByRole("heading", { name: "E’lonlarim" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\+ E’lon/ })).toBeInTheDocument();
  });
});
