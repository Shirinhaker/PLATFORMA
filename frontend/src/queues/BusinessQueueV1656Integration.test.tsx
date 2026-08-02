import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BusinessOnlineScreen } from "../profiles/BusinessOnlineScreen";


const profile = {
  account_id: 7,
  name: "Muhr klinikasi",
  phone: "",
  description: "",
  public_username: "muhr1",
  direction: "Tibbiy xizmatlar",
  activity_type: "Klinika",
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
  cabinet_payload: {},
};

const setup = {
  services: [{ public_id: "s_qabul", name: "Qabul", price_text: "50 000 so‘m" }],
  staff: [{ id: 11, name: "Ali Valiyev", profession: "Terapevt" }],
};

const provider = {
  id: 5,
  staff_id: 11,
  name: "Ali Valiyev",
  profession: "Terapevt",
  specialty: "Kardiolog",
  experience_years: 8,
  qualification: "Oliy toifa",
  work_days: "1,2,3,4,5,6",
  work_start: "08:00",
  work_end: "17:00",
  avg_minutes: 20,
  room: "12-xona",
  bio: "Shifokor haqida",
  status: "active" as const,
  mode: "slot" as const,
  item_public_ids: ["s_qabul"],
  queue_count: 1,
};

const queue = {
  id: 41,
  business_account_id: 7,
  customer_account_id: 21,
  item_public_id: "s_qabul",
  provider_id: 5,
  patient_name: "Vali",
  phone: "901234567",
  service_name: "Qabul",
  provider_name: "Ali Valiyev",
  queue_date: "2026-08-02",
  queue_no: 1,
  queue_code: "QAB-001",
  source: "online",
  status: "waiting",
  note: "",
  slot_time: "09:00",
  ahead_count: 0,
  avg_minutes: 20,
  wait_minutes: 0,
  created_at: "2026-08-02T04:00:00Z",
  updated_at: "2026-08-02T04:00:00Z",
};

function api() {
  return {
    getBusinessQueueSetup: vi.fn().mockResolvedValue(setup),
    getBusinessQueueProviders: vi.fn().mockResolvedValue([provider]),
    createBusinessQueueProvider: vi.fn().mockResolvedValue(provider),
    updateBusinessQueueProvider: vi.fn().mockResolvedValue({
      ...provider,
      room: "15-xona",
    }),
    getBusinessQueueEntries: vi.fn().mockResolvedValue([queue]),
    createBusinessOfflineQueue: vi.fn().mockResolvedValue({
      ...queue,
      id: 42,
      queue_code: "QAB-002",
      source: "offline",
    }),
    changeBusinessQueueStatus: vi.fn().mockImplementation(
      async (_id: number, status: string) => ({ ...queue, status }),
    ),
    swapBusinessQueues: vi.fn().mockResolvedValue(queue),
    getBusinessOnlineResource: vi.fn().mockResolvedValue({ resource: "items", items: [] }),
    createBusinessOnlineRecord: vi.fn(),
    patchBusinessOnlineRecord: vi.fn(),
    deleteBusinessOnlineRecord: vi.fn(),
    applyBusinessOnlineAction: vi.fn(),
  };
}

describe("Q2 typed biznes navbat oqimi", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-08-02T05:00:00Z"));
  });

  afterEach(() => vi.useRealTimers());

  it("provider setup/list/save ni generic snapshotga tegmasdan typed API orqali bajaradi", async () => {
    const user = userEvent.setup();
    const client = api();
    render(
      <BusinessOnlineScreen
        api={client}
        profile={profile}
        view="medical-providers"
        title="Shifokorlar"
        onBack={vi.fn()}
      />,
    );

    const card = await screen.findByRole("button", { name: /Ali Valiyev/ });
    expect(client.getBusinessQueueSetup).toHaveBeenCalledOnce();
    expect(client.getBusinessQueueProviders).toHaveBeenCalledOnce();
    expect(client.getBusinessOnlineResource).not.toHaveBeenCalled();

    await user.click(card);
    await user.clear(screen.getByLabelText("Xona/joy"));
    await user.type(screen.getByLabelText("Xona/joy"), "15-xona");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(client.updateBusinessQueueProvider).toHaveBeenCalledWith(
      5,
      expect.objectContaining({
        staff_id: 11,
        room: "15-xona",
        item_public_ids: ["s_qabul"],
      }),
    );
    expect(client.patchBusinessOnlineRecord).not.toHaveBeenCalled();
  });

  it("kunlik ro'yxat, status, oflayn navbat va swapni typed API orqali bajaradi", async () => {
    const user = userEvent.setup();
    const client = api();
    render(
      <BusinessOnlineScreen
        api={client}
        profile={profile}
        view="medical-queue"
        title="Navbat boshqaruvi"
        onBack={vi.fn()}
      />,
    );

    const card = (await screen.findByText("QAB-001 · Vali")).closest(".panel-card");
    expect(client.getBusinessQueueEntries).toHaveBeenCalledWith("2026-08-02");
    expect(card).toHaveTextContent("Qabul · Ali Valiyev · Onlayn · 🕐 09:00");

    await user.click(within(card as HTMLElement).getByRole("button", { name: "Chaqirish" }));
    expect(client.changeBusinessQueueStatus).toHaveBeenCalledWith(41, "called");

    await user.click(screen.getByRole("button", { name: "+ Oflayn navbat" }));
    await user.type(screen.getByLabelText("Bemor ism-familiyasi"), "Hasan");
    await user.selectOptions(screen.getByLabelText("Xizmat"), "s_qabul");
    await user.selectOptions(screen.getByLabelText("Shifokor"), "5");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(client.createBusinessOfflineQueue).toHaveBeenCalledWith({
      item_public_id: "s_qabul",
      provider_id: 5,
      queue_date: "2026-08-02",
      patient_name: "Hasan",
      phone: "",
      note: "",
      slot_time: "",
    });

    await user.click(screen.getByRole("button", { name: "↔ Navbatlarni almashtirish" }));
    await user.type(screen.getByLabelText("Birinchi navbat ID"), "41");
    await user.type(screen.getByLabelText("Ikkinchi navbat ID"), "42");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(client.swapBusinessQueues).toHaveBeenCalledWith(41, 42);
    expect(client.applyBusinessOnlineAction).not.toHaveBeenCalled();
  });
});
