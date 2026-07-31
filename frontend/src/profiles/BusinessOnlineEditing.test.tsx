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
  phone: "",
  description: "",
  public_username: "muhr1",
  direction: "Savdo",
  activity_type: "Oziq-ovqat do'koni",
  address: "Qumqo‘rg‘on",
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
  cabinet_payload: {
    item_groups: [{ id: 1, name: "Asosiy", kind: "product" }],
    items: [{
      id: 11,
      name: "Eski nom",
      kind: "product",
      group_id: 1,
      price: 15000,
      description: "Eski tavsif",
    }],
    listings: [],
    orders: [],
    messages: [],
    business_reviews: [],
    advertisements: [],
    stories: [],
    notifications: [],
    followers: [],
    following: [],
    business_subscriptions: [],
    subscription_payments: [],
  },
};


describe("business online editing", () => {
  it("edits a migrated item through the typed patch endpoint", async () => {
    const user = userEvent.setup();
    const patchBusinessOnlineRecord = vi.fn().mockResolvedValue({
      resource: "items",
      item: { ...profile.cabinet_payload.items[0], name: "Yangi nom" },
      items: [{ ...profile.cabinet_payload.items[0], name: "Yangi nom" }],
    });
    const api = {
      getSession: vi.fn().mockResolvedValue(identity),
      getBusinessProfile: vi.fn().mockResolvedValue(profile),
      updateBusinessProfile: vi.fn().mockResolvedValue(profile),
      createUploadGrant: vi.fn(),
      uploadGrantedFile: vi.fn(),
      attachBusinessLogo: vi.fn().mockResolvedValue(profile),
      attachBusinessPaymentQr: vi.fn().mockResolvedValue(profile),
      switchCabinet: vi.fn(),
      logout: vi.fn(),
      patchBusinessOnlineRecord,
    };

    render(
      <BusinessProfile
        api={api}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );
    await screen.findByRole("heading", { name: "Muhr" });
    expect(screen.getByText("Tovar, narx va rasm qo'shish")).toBeInTheDocument();
    await user.click(screen.getByRole("button", {
      name: /Mahsulotlar/,
    }));
    await screen.findByPlaceholderText("Tovar qidirish...");
    await user.click(screen.getByRole("button", { name: "Eski nom amallari" }));
    await user.click(screen.getByRole("button", { name: "Tahrirlash" }));
    expect(await screen.findByRole("heading", {
      name: "Mahsulot yoki xizmatni tahrirlash",
    })).toBeInTheDocument();

    const name = screen.getByLabelText("Nomi");
    await user.clear(name);
    await user.type(name, "Yangi nom");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(patchBusinessOnlineRecord).toHaveBeenCalledWith(
      "items",
      "11",
      expect.objectContaining({
        name: "Yangi nom",
        kind: "product",
        group_id: 1,
      }),
    );
  });
});
