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
    orders: [{
      id: 44,
      title: "Muhr",
      status: "new",
      order_type: "product",
      total_amount: 15000,
      items: [{ id: 1, name: "Muhr", qty: 1 }],
      messages: [{ id: 1, text: "Assalomu alaykum" }],
    }, {
      id: 45,
      title: "Xizmat",
      status: "new",
      order_type: "service",
      total_amount: 40000,
      items: [],
      messages: [],
    }],
    messages: [{ id: 3, text: "Salom", sender_kind: "user" }],
    business_reviews: [{ id: 4, rating: 5, text: "Yaxshi", reviewer_name: "Ali" }],
    advertisements: [{ id: 5, title: "Banner", status: "active" }],
    stories: [{ id: 6, caption: "Bugungi ish", status: "active", views: [] }],
    notifications: [{ id: 7, title: "Yangi xabar", is_read: 0 }],
    followers: [{ id: 8, name: "Vali" }],
    following: [{ id: 9, name: "Hamkor biznes" }],
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

async function renderCabinet() {
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
  return user;
}

async function back(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /Kabinetga qaytish/ }));
  await screen.findByRole("heading", { name: "Muhr" });
}


describe("v1656 online cabinet parity", () => {
  it("opens the exact v1656 item screen from the cabinet", async () => {
    const user = await renderCabinet();

    await user.click(screen.getByRole("button", { name: /Mahsulot va xizmatlar/ }));
    expect(await screen.findByPlaceholderText("Tovar qidirish...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\+ Guruh qo'shish/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tovar qo'shish" })).toBeInTheDocument();
    expect(screen.getByText("Muhr")).toBeInTheDocument();
  });

  it("uses dedicated order, service, conversation and review workflows", async () => {
    const user = await renderCabinet();

    await user.click(screen.getByRole("button", { name: /^📦 Buyurtmalar/ }));
    expect(await screen.findByRole("heading", { name: "Buyurtmalar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yangi" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Jarayondagi" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yakunlangan" })).toBeInTheDocument();

    await back(user);
    await user.click(screen.getByRole("button", { name: /Xizmat buyurtmalari/ }));
    expect(await screen.findByRole("heading", { name: "Xizmat buyurtmalari" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Buyurtma #45 — Xizmat/ })).toBeInTheDocument();

    await back(user);
    await user.click(screen.getByRole("button", { name: /Suhbatlar/ }));
    expect(await screen.findByRole("heading", { name: "Suhbatlar" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Xabar yozing...")).toBeInTheDocument();

    await back(user);
    await user.click(screen.getByRole("button", { name: /Mijoz fikrlari/ }));
    expect(await screen.findByRole("heading", { name: "Mijoz fikrlari" })).toBeInTheDocument();
    expect(screen.getByText("O‘rtacha baho")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Javob berish" })).toBeInTheDocument();
  });

  it("uses dedicated promotion, story, notification and follow screens", async () => {
    const user = await renderCabinet();

    await user.click(screen.getByRole("button", { name: /Reklamalarim/ }));
    expect(await screen.findByRole("heading", { name: "Reklamalarim" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\+ Reklama/ })).toBeInTheDocument();

    await back(user);
    await user.click(screen.getByRole("button", { name: /Istoriya arxivi/ }));
    expect(await screen.findByRole("heading", { name: "Istoriya arxivi" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\+ Istoriya/ })).toBeInTheDocument();

    await back(user);
    await user.click(screen.getByRole("button", { name: /Bildirishnomalarim/ }));
    expect(await screen.findByRole("heading", { name: "Bildirishnomalarim" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Barchasini o‘qilgan qilish" })).toBeInTheDocument();

    await back(user);
    await user.click(screen.getByRole("button", { name: /Obunachilar/ }));
    expect(await screen.findByRole("heading", { name: "Obunachilar" })).toBeInTheDocument();
    expect(screen.getByText("Vali")).toBeInTheDocument();

    await back(user);
    await user.click(screen.getByRole("button", { name: /Biznes obunalari/ }));
    expect(await screen.findByRole("heading", { name: "Biznes obunalari" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Obunani bekor qilish" })).toBeInTheDocument();
  });
});
