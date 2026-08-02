import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { BusinessProfile, OrderRead, UserProfile as UserProfileData } from "../api/types";
import { BusinessOnlineScreen } from "../profiles/BusinessOnlineScreen";
import { NotificationsView } from "../profiles/BusinessOnlineViews";
import { UserProfile } from "../profiles/UserProfile";


const liveOrder = {
  id: 91,
  view: "customer",
  title: "Jonli order №91",
  customer_name: "Ali",
  provider_name: "Turon",
  order_type: "delivery",
  order_category: "product",
  address: "Qumqo‘rg‘on",
  total_text: "20 000 so‘m",
  status: "accepted",
  payment_status: "pending",
  is_unread: true,
  last_event: "status_changed",
  items: [],
} as unknown as OrderRead;

const business = {
  account_id: 7,
  name: "Turon",
  direction: "Savdo",
  cabinet_payload: { orders: [{ id: 1, title: "Eski snapshot" }] },
} as unknown as BusinessProfile;

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
  followers_count: 0,
  following_count: 0,
  has_business: false,
  dashboard_snapshot: {},
  recent_activity: [],
  specialist_profile: {},
  cabinet_payload: { orders: [{ id: 1, title: "Eski snapshot" }] },
} satisfies UserProfileData;

function orderMethods(rows = [liveOrder]) {
  return {
    getMyOrders: vi.fn().mockResolvedValue(rows),
    getOrderInbox: vi.fn().mockResolvedValue(rows.map((row) => ({ ...row, view: "provider" }))),
    markOrderSeen: vi.fn(),
    changeOrderStatus: vi.fn(),
    submitOrderPayment: vi.fn(),
    decideOrderPayment: vi.fn(),
    openOrderProblem: vi.fn(),
    chooseOrderProblemSolution: vi.fn(),
    handoffOrder: vi.fn(),
    receiveOrder: vi.fn(),
    getOrderChat: vi.fn(),
    sendOrderChatMessage: vi.fn(),
    sendOrderChatImage: vi.fn(),
    editOrderChatMessage: vi.fn(),
    deleteOrderChatMessage: vi.fn(),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
  };
}


describe("v1656 order kabinet wiring", () => {
  it("biznes order ekranini snapshot emas, jonli inbox bilan ochadi", async () => {
    const legacy = vi.fn();
    const api = { ...orderMethods(), getBusinessOnlineResource: legacy };
    render(
      <BusinessOnlineScreen
        api={api}
        profile={business}
        view="orders"
        title="Buyurtmalar"
        onBack={vi.fn()}
      />,
    );

    expect(await screen.findByText("Jonli order №91")).toBeInTheDocument();
    expect(api.getOrderInbox).toHaveBeenCalledOnce();
    expect(legacy).not.toHaveBeenCalled();
    expect(screen.queryByText("Eski snapshot")).not.toBeInTheDocument();
  });

  it("mijoz kabinetida jonli unread badge va /my ro‘yxatini ochadi", async () => {
    const user = userEvent.setup();
    const api = {
      ...orderMethods(),
      getSession: vi.fn(),
      getUserProfile: vi.fn().mockResolvedValue(userProfile),
      updateUserProfile: vi.fn(),
      attachUserAvatar: vi.fn(),
      switchCabinet: vi.fn(),
      logout: vi.fn(),
    };
    render(
      <UserProfile
        api={api}
        identity={{
          account_id: 5,
          account_type: "user",
          name: "Ali",
          login: "u_ali",
          csrf_token: "csrf",
          expires_at: "2026-08-30T00:00:00Z",
        }}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    const button = await screen.findByRole("button", { name: /Buyurtmalarim/ });
    expect(button).toHaveTextContent("1");
    await user.click(button);
    expect(await screen.findByText("Jonli order №91")).toBeInTheDocument();
    expect(screen.queryByText("Eski snapshot")).not.toBeInTheDocument();
  });

  it("order bildirishnomasini o‘qib, aynan detail deep-linkini uzatadi", async () => {
    const user = userEvent.setup();
    const markOne = vi.fn().mockResolvedValue(undefined);
    const onOpenOrder = vi.fn();
    render(
      <NotificationsView
        rows={[{
          id: 8,
          order_id: 91,
          title: "Status yangilandi",
          body: "Buyurtma qabul qilindi",
          is_read: 0,
        }]}
        busy={false}
        markAll={vi.fn()}
        markOne={markOne}
        onOpenOrder={onOpenOrder}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Status yangilandi/ }));
    expect(markOne).toHaveBeenCalledWith(8);
    expect(onOpenOrder).toHaveBeenCalledWith(91);
  });
});
