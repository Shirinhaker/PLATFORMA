import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { BusinessOnlineResource } from "../api/business-online-types";
import { BusinessProfile } from "./BusinessProfile";


const identity = {
  account_id: 7,
  account_type: "business" as const,
  name: "Muhr",
  login: "muhr1",
  csrf_token: "csrf",
  expires_at: "2026-08-30T08:00:00Z",
};

const payload = {
  business_subscriptions: [],
  subscription_payments: [],
  item_groups: [],
  items: [],
  listings: [],
  orders: [],
  messages: [],
  business_reviews: [{
    id: 4,
    rating: 5,
    text: "Yaxshi",
    reviewer_name: "Ali",
  }],
  advertisements: [],
  stories: [],
  notifications: [{ id: 7, title: "Yangi xabar", is_read: 0 }],
  followers: [],
  following: [{ id: 9, name: "Hamkor biznes" }],
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
  following_count: 1,
  rating_sum: 5,
  rating_count: 1,
  map_visible: true,
  dashboard_snapshot: {},
  recent_activity: [],
  cabinet_payload: payload,
};

function api() {
  const getBusinessOnlineResource = vi.fn(async (
    resource: BusinessOnlineResource,
  ) => ({
    resource,
    items: payload[resource] ?? [],
  }));
  const applyBusinessOnlineAction = vi.fn(async (
    resource: BusinessOnlineResource,
    _action: string,
  ) => ({
    resource,
    item: null,
    items: payload[resource] ?? [],
  }));
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
    getBusinessOnlineResource,
    createBusinessOnlineRecord: vi.fn(),
    patchBusinessOnlineRecord: vi.fn(),
    deleteBusinessOnlineRecord: vi.fn(),
    applyBusinessOnlineAction,
  };
}

async function renderCabinet() {
  const user = userEvent.setup();
  const client = api();
  render(
    <BusinessProfile
      api={client}
      identity={identity}
      onLogout={vi.fn()}
      onSwitched={vi.fn()}
    />,
  );
  await screen.findByRole("heading", { name: "Muhr" });
  return { user, client };
}

async function back(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /Kabinetga qaytish/ }));
  await screen.findByRole("heading", { name: "Muhr" });
}


describe("business online server mutations", () => {
  it("sends notification, review and unfollow actions to the API", async () => {
    const { user, client } = await renderCabinet();

    await user.click(screen.getByRole("button", { name: /Bildirishnomalarim/ }));
    await screen.findByRole("heading", { name: "Bildirishnomalarim" });
    await waitFor(() => expect(client.getBusinessOnlineResource)
      .toHaveBeenCalledWith("notifications"));
    await user.click(screen.getByRole("button", {
      name: "Barchasini o‘qilgan qilish",
    }));
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "notifications",
      "mark_all_read",
      { record_id: undefined, payload: {} },
    );

    await back(user);
    await user.click(screen.getByRole("button", { name: /Mijoz fikrlari/ }));
    await screen.findByRole("heading", { name: "Mijoz fikrlari" });
    await user.click(await screen.findByRole("button", { name: "Javob berish" }));
    await user.type(screen.getByRole("textbox"), "Rahmat");
    await user.click(screen.getByRole("button", { name: "Javobni saqlash" }));
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "business_reviews",
      "reply",
      { record_id: 4, payload: { reply: "Rahmat" } },
    );

    await back(user);
    await user.click(screen.getByRole("button", { name: /Biznes obunalari/ }));
    await screen.findByRole("heading", { name: "Biznes obunalari" });
    await user.click(await screen.findByRole("button", {
      name: "Obunani bekor qilish",
    }));
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "following",
      "unfollow",
      { record_id: 9, payload: {} },
    );
  });
});
