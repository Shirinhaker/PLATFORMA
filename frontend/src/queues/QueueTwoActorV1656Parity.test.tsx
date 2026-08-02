import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  BusinessQueueEntry,
  BusinessQueueProvider,
  QueueCreate,
  QueueEntryStatus,
  UserProfile as UserProfileData,
} from "../api/types";
import { UserProfile } from "../profiles/UserProfile";
import { BusinessQueueV1656 } from "./BusinessQueueV1656";
import { QueueBookingV1656 } from "./QueueBookingV1656";


const provider: BusinessQueueProvider = {
  id: 5,
  staff_id: 11,
  name: "Ali Valiyev",
  profession: "Terapevt",
  specialty: "Kardiolog",
  experience_years: 8,
  qualification: "Oliy toifa",
  work_days: "1,2,3,4,5,6,7",
  work_start: "08:00",
  work_end: "17:00",
  avg_minutes: 20,
  room: "12-xona",
  bio: "",
  status: "active",
  mode: "live",
  item_public_ids: ["s_qabul"],
  queue_count: 0,
};

const baseProfile: UserProfileData = {
  account_id: 5,
  name: "Ali",
  phone: "+998901234567",
  public_username: "ali",
  region: "Surxondaryo viloyati",
  district: "Qumqo'rg'on tumani",
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
  cabinet_payload: {},
};


describe("Q5 v1656 ikki aktyorli navbat pariteti", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-08-03T07:00:00Z"));
  });

  afterEach(() => vi.useRealTimers());

  it("mijoz -> navbat -> biznes -> bildirishnoma -> mijoz zanjirini saqlaydi", async () => {
    const user = userEvent.setup();
    let storedQueue: BusinessQueueEntry | null = null;
    let notification: Record<string, unknown> | null = null;

    function requireQueue() {
      if (!storedQueue) throw new Error("Navbat hali yaratilmagan.");
      return storedQueue;
    }

    const customerQueueApi = {
      getQueueOptions: vi.fn().mockResolvedValue({
        business_public_id: "b_shifo",
        item_public_id: "s_qabul",
        queue_date: "2026-08-03",
        providers: [provider],
      }),
      getQueueSlots: vi.fn().mockResolvedValue({ mode: "live", slots: [] }),
      createQueue: vi.fn(async (body: QueueCreate) => {
        storedQueue = {
          id: 41,
          business_account_id: 7,
          business_name: "Shifo markazi",
          business_direction: "Tibbiy xizmatlar",
          customer_account_id: 5,
          item_public_id: body.item_public_id,
          provider_id: body.provider_id,
          patient_name: "Ali",
          phone: "+998901234567",
          service_name: "Qabul",
          provider_name: "Ali Valiyev",
          queue_date: body.queue_date,
          queue_no: 1,
          queue_code: "QAB-001",
          source: "online",
          status: "waiting",
          note: body.note,
          slot_time: body.slot_time,
          ahead_count: 0,
          avg_minutes: 20,
          wait_minutes: 0,
          created_at: "2026-08-03T07:00:00Z",
          updated_at: "2026-08-03T07:00:00Z",
        };
        return storedQueue;
      }),
    };
    const onMessage = vi.fn();
    const bookingView = render(
      <QueueBookingV1656
        api={customerQueueApi}
        target={{
          businessPublicId: "b_shifo",
          itemPublicId: "s_qabul",
          serviceName: "Qabul",
          direction: "Tibbiy xizmatlar",
        }}
        onClose={vi.fn()}
        onMessage={onMessage}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    await user.selectOptions(await screen.findByLabelText("Shifokor"), "5");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(onMessage).toHaveBeenCalledWith("Navbatingiz: QAB-001");
    expect(requireQueue().status).toBe("waiting");
    bookingView.unmount();

    const businessApi = {
      getBusinessQueueSetup: vi.fn().mockResolvedValue({
        services: [{
          public_id: "s_qabul",
          name: "Qabul",
          price_text: "50 000 so'm",
        }],
        staff: [{ id: 11, name: "Ali Valiyev", profession: "Terapevt" }],
      }),
      getBusinessQueueProviders: vi.fn().mockResolvedValue([provider]),
      createBusinessQueueProvider: vi.fn().mockResolvedValue(provider),
      updateBusinessQueueProvider: vi.fn().mockResolvedValue(provider),
      getBusinessQueueEntries: vi.fn(async () => [requireQueue()]),
      createBusinessOfflineQueue: vi.fn(),
      changeBusinessQueueStatus: vi.fn(async (_id: number, status: QueueEntryStatus) => {
        storedQueue = {
          ...requireQueue(),
          status,
          updated_at: "2026-08-03T07:01:00Z",
        };
        if (status === "called") {
          notification = {
            id: 8,
            title: "Navbatingiz keldi",
            body: "QAB-001 navbat shifokor tomonidan chaqirildi.",
            action_type: "medical_queue_called",
            medical_queue_id: storedQueue.id,
            is_read: 0,
          };
        }
        return storedQueue;
      }),
      swapBusinessQueues: vi.fn(),
    };
    const businessView = render(
      <BusinessQueueV1656
        api={businessApi}
        direction="Tibbiy xizmatlar"
        view="medical-queue"
        onBackHandlerChange={vi.fn()}
      />,
    );

    const businessCard = (await screen.findByText("QAB-001 · Ali"))
      .closest(".panel-card");
    expect(businessCard).not.toBeNull();
    await user.click(within(businessCard as HTMLElement)
      .getByRole("button", { name: "Chaqirish" }));
    await waitFor(() => expect(requireQueue().status).toBe("called"));
    expect(within(businessCard as HTMLElement).getByText("Chaqirildi"))
      .toBeInTheDocument();
    businessView.unmount();

    const orderMethods = {
      getMyOrders: vi.fn().mockResolvedValue([]),
      getOrderInbox: vi.fn().mockResolvedValue([]),
      markOrderSeen: vi.fn(),
      changeOrderStatus: vi.fn(),
      submitOrderPayment: vi.fn(),
      decideOrderPayment: vi.fn(),
      openOrderProblem: vi.fn(),
      chooseOrderProblemSolution: vi.fn(),
      handoffOrder: vi.fn(),
      receiveOrder: vi.fn(),
      getOrderChat: vi.fn().mockResolvedValue([]),
      sendOrderChatMessage: vi.fn(),
      sendOrderChatImage: vi.fn(),
      editOrderChatMessage: vi.fn(),
      deleteOrderChatMessage: vi.fn(),
      createUploadGrant: vi.fn(),
      uploadGrantedFile: vi.fn(),
    };
    const userProfileApi = {
      ...orderMethods,
      getSession: vi.fn(),
      getUserProfile: vi.fn(async () => ({
        ...baseProfile,
        cabinet_payload: { notifications: [notification] },
      })),
      updateUserProfile: vi.fn(),
      attachUserAvatar: vi.fn(),
      switchCabinet: vi.fn(),
      logout: vi.fn(),
      getMyQueues: vi.fn(async () => [requireQueue()]),
      cancelMyQueue: vi.fn(),
      markQueueNotificationRead: vi.fn(async (notificationId: number) => {
        notification = { ...notification, is_read: 1 };
        return {
          id: notificationId,
          medical_queue_id: requireQueue().id,
          is_read: true,
        };
      }),
    };
    render(
      <UserProfile
        api={userProfileApi}
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

    await user.click(await screen.findByRole("button", {
      name: "Bildirishnomalarim",
    }));
    await user.click(await screen.findByText("Navbatingiz keldi"));

    expect(userProfileApi.markQueueNotificationRead).toHaveBeenCalledWith(8);
    expect(await screen.findByText("NAVBAT QAB-001")).toBeInTheDocument();
    expect(screen.getByText("Chaqirildi")).toBeInTheDocument();
    expect(screen.getByTestId("medical-queue-41"))
      .toHaveClass("medical-queue-focus");
  });
});
