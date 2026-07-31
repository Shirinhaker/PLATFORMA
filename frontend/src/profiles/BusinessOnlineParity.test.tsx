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
  dashboard_snapshot: {},
  recent_activity: [],
  cabinet_payload: {
    item_groups: [{ id: 10, name: "Tayyor mahsulotlar", kind: "product" }],
    items: [{ id: 11, group_id: 10, name: "Muhr", kind: "product", price: 15000 }],
    business_subscriptions: [],
    subscription_payments: [],
    listings: [],
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


describe("v1656 online cabinet parity", () => {
  it("opens the item catalog from the cabinet", async () => {
    const user = userEvent.setup();
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
    await user.click(screen.getByRole("button", { name: /Mahsulot va xizmatlar/ }));

    expect(await screen.findByPlaceholderText("Tovar qidirish...")).toBeInTheDocument();
  });
});
