import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BusinessProfile } from "./BusinessProfile";
import { UserProfile } from "./UserProfile";


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
  public_username: "ali",
  region: "Surxondaryo",
  district: "Qumqo‘rg‘on",
  mahalla: "",
  latitude: null,
  longitude: null,
  location_exact: false,
  avatar_object_key: "",
  avatar_x: 50,
  avatar_y: 50,
  avatar_zoom: 1,
  followers_count: 3,
  following_count: 2,
  has_business: true,
  dashboard_snapshot: {
    active_orders: 1,
    following: 2,
    saved: 1,
    unread: 4,
  },
  recent_activity: [{
    id: 46,
    kind: "order",
    title: "Muhr",
    status: "new",
    amount: 350000,
    created_at: 1722211200,
  }],
  specialist_profile: {},
  cabinet_payload: {
    orders: [{ id: 46, title: "Muhr", status: "new" }],
    listings: [{ id: 3, title: "Uy sotiladi", status: "active" }],
    stories: [{ id: 7, caption: "Bugungi ish", status: "active" }],
    notifications: [{ id: 8, title: "Yangi xabar", is_read: 0 }],
    saved: [{ id: 4, target_kind: "business", target_id: 7 }],
    follows: [{ id: 2, target_kind: "business", target_id: 7 }],
    followers: [{ id: 9, name: "Vali" }],
    payments: [{ id: 12, status: "approved", amount_snapshot: 10000 }],
    messages: [{ id: 13, text: "Assalomu alaykum" }],
    notify_filters: [{ id: 14, cat: "uy", district: "Qumqo‘rg‘on" }],
    drivers: [{ id: 15, car_model: "Cobalt", car_plate: "75 A 777 AA" }],
    rides: [{ id: 16, from_addr: "Uy", to_addr: "Bozor", status: "completed" }],
  },
};
const businessProfile = {
  account_id: 7,
  name: "Turon",
  phone: "",
  description: "",
  public_username: "turon",
  direction: "Savdo",
  activity_type: "Do‘kon",
  address: "Qumqo‘rg‘on",
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
  followers_count: 8,
  following_count: 1,
  rating_sum: 20,
  rating_count: 5,
  map_visible: true,
  dashboard_snapshot: {
    revenue: 500000,
    new_orders: 2,
    debt_total: 100000,
    low_stock: 1,
    active_orders: 3,
  },
  recent_activity: [{
    id: 44,
    kind: "order",
    title: "Muhr",
    status: "accepted",
    amount: 15000,
    created_at: 1722211200,
  }],
  cabinet_payload: {
    orders: [{ id: 44, title: "Muhr", status: "accepted" }],
    item_groups: [{ id: 1, name: "Tayyor mahsulotlar", kind: "product" }],
    items: [{ id: 2, name: "Muhr", price: "15000" }],
    listings: [{ id: 5, title: "Biznes e’loni", status: "active" }],
    debtors: [{ id: 3, name: "Vali", balance: 100000 }],
    qarz_transactions: [{ id: 4, type: "debt", amount: 100000 }],
    notifications: [],
    followers: [{ id: 8, name: "Sardor" }],
    following: [{ id: 9, name: "Hamkor biznes" }],
    subscription_payments: [{ id: 10, status: "approved", amount_snapshot: 149000 }],
    staff: [{ id: 11, name: "Haqiqiy xodim", role: "kassir" }],
    documents: [{ id: 12, title: "Shartnoma", status: "active" }],
    incoming_documents: [{ id: 13, title: "Kiruvchi xat" }],
    outgoing_documents: [{ id: 14, title: "Chiquvchi xat" }],
    internal_documents: [{ id: 15, title: "Ichki buyruq" }],
    counterparties: [{ id: 16, name: "Ta’minotchi" }],
    warehouse_items: [{ id: 17, name: "Qog‘oz", stock_qty: 20 }],
    warehouse_tx: [{ id: 18, item_name: "Qog‘oz", qty: 10 }],
    sales: [{ id: 19, total: 500000 }],
    cash_transactions: [{ id: 20, amount: 500000, kind: "income" }],
  },
};


function profileApi() {
  return {
    getSession: vi.fn().mockResolvedValue(userIdentity),
    getUserProfile: vi.fn().mockResolvedValue(userProfile),
    updateUserProfile: vi.fn().mockResolvedValue(userProfile),
    getBusinessProfile: vi.fn().mockResolvedValue(businessProfile),
    updateBusinessProfile: vi.fn().mockResolvedValue(businessProfile),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    attachUserAvatar: vi.fn().mockResolvedValue(userProfile),
    attachBusinessLogo: vi.fn().mockResolvedValue(businessProfile),
    switchCabinet: vi.fn().mockResolvedValue({
      account_id: 7,
      account_type: "business",
      login: "b_turon",
      csrf_token: "next-csrf",
      expires_at: "2026-08-27T08:00:00Z",
    }),
    logout: vi.fn().mockResolvedValue(undefined),
  };
}


async function openUserProfileForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Profilim" }));
  return screen.findByLabelText("Ism");
}


async function openBusinessProfileForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole(
    "button",
    { name: /Profil \/ Mening sahifam/ },
  ));
  return screen.findByLabelText("Biznes nomi");
}


describe("profile cabinets", () => {
  it("renders migrated user counts, activity and real section data", async () => {
    const user = userEvent.setup();
    const api = profileApi();
    render(
      <UserProfile
        api={api}
        identity={userIdentity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Ali" }))
      .toBeInTheDocument();
    expect(screen.getByText("3 obunachi")).toBeInTheDocument();
    expect(screen.getByText("Buyurtma #46 — Muhr")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "E’lonlarim" }));
    expect(await screen.findByText("Uy sotiladi")).toBeInTheDocument();
    expect(screen.getByText("1 ta haqiqiy yozuv")).toBeInTheDocument();
  });

  it("opens migrated driver, ride and notification-filter data", async () => {
    const user = userEvent.setup();
    render(
      <UserProfile
        api={profileApi()}
        identity={userIdentity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole(
      "button",
      { name: "Haydovchilik profilim" },
    ));
    expect(await screen.findByText("Cobalt")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Kabinetga qaytish/ }));
    await user.click(screen.getByRole(
      "button",
      { name: "Taxi va dostavka buyurtmalarim" },
    ));
    expect(await screen.findByText("Bozor")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Kabinetga qaytish/ }));
    await user.click(screen.getByRole(
      "button",
      { name: "Bildirishnoma filtrlari" },
    ));
    expect(await screen.findByText("Qumqo‘rg‘on")).toBeInTheDocument();
  });

  it("edits user profile without business fields", async () => {
    const user = userEvent.setup();
    const api = profileApi();
    render(
      <UserProfile
        api={api}
        identity={userIdentity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );
    const name = await openUserProfileForm(user);
    expect(screen.queryByLabelText("STIR")).not.toBeInTheDocument();
    await user.clear(name);
    await user.type(name, "Yangi ism");
    api.updateUserProfile.mockImplementation(async (patch) => ({
      ...userProfile,
      ...patch,
    }));
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(api.updateUserProfile).toHaveBeenCalledWith({ name: "Yangi ism" });
    expect(await screen.findByText("Saqlandi")).toBeInTheDocument();
  });

  it("switches directly to linked business cabinet without logout", async () => {
    const user = userEvent.setup();
    const api = profileApi();
    api.getSession.mockResolvedValue(businessIdentity);
    const onSwitched = vi.fn();
    render(
      <UserProfile
        api={api}
        identity={userIdentity}
        onLogout={vi.fn()}
        onSwitched={onSwitched}
      />,
    );
    await user.click(await screen.findByRole(
      "button",
      { name: /Biznes kabinetga o‘tish/ },
    ));
    expect(api.switchCabinet).toHaveBeenCalledWith("business");
    expect(api.logout).not.toHaveBeenCalled();
    expect(onSwitched).toHaveBeenCalledWith(businessIdentity);
  });

  it("renders migrated business dashboard and merged real items", async () => {
    const user = userEvent.setup();
    render(
      <BusinessProfile
        api={profileApi()}
        identity={businessIdentity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );
    expect(await screen.findByRole("heading", { name: "Turon" }))
      .toBeInTheDocument();
    expect(screen.getByText("500 000 so‘m")).toBeInTheDocument();
    expect(screen.getByText("Onlaynlashtirish")).toBeInTheDocument();
    expect(screen.getByText("Tizimlashtirish")).toBeInTheDocument();
    expect(screen.getByText("Ma’muriyat")).toBeInTheDocument();
    await user.click(screen.getByRole(
      "button",
      { name: /Mahsulot va xizmatlar/ },
    ));
    expect(await screen.findByText("Muhr")).toBeInTheDocument();
    expect(screen.getByText("Tayyor mahsulotlar")).toBeInTheDocument();
  });

  it("opens migrated staff, documents and combined warehouse data", async () => {
    const user = userEvent.setup();
    render(
      <BusinessProfile
        api={profileApi()}
        identity={businessIdentity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /Xodimlar/ }));
    expect(await screen.findByText("Haqiqiy xodim")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Kabinetga qaytish/ }));
    await user.click(screen.getByRole(
      "button",
      { name: /Mening hujjatlarim/ },
    ));
    expect(await screen.findByText("Shartnoma")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Kabinetga qaytish/ }));
    await user.click(screen.getByRole("button", { name: /Ombor/ }));
    expect(await screen.findByText("Qog‘oz")).toBeInTheDocument();
  });

  it("edits business profile and uploads logo", async () => {
    const user = userEvent.setup();
    const api = profileApi();
    const file = new File(["image"], "logo.png", { type: "image/png" });
    api.createUploadGrant.mockResolvedValue({
      object_key: "private/business/7/logo/abc.png",
      upload_url: "https://r2.example/upload",
      method: "PUT",
      headers: { "Content-Type": "image/png" },
      expires_in_seconds: 900,
    });
    render(
      <BusinessProfile
        api={api}
        identity={businessIdentity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );
    expect(await openBusinessProfileForm(user)).toBeInTheDocument();
    expect(screen.getByLabelText("STIR")).toBeInTheDocument();
    expect(screen.queryByLabelText("Mahalla")).not.toBeInTheDocument();
    await user.upload(screen.getByLabelText("Logotip"), file);
    expect(api.attachBusinessLogo).toHaveBeenCalledWith(
      expect.objectContaining({
        object_key: "private/business/7/logo/abc.png",
      }),
    );
  });
});
