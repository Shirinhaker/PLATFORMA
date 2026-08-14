import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { QueueBookingV1656 } from "./QueueBookingV1656";


const target = {
  businessPublicId: "b_shifo",
  itemPublicId: "s_qabul",
  serviceName: "Qabul",
  direction: "Tibbiy xizmatlar",
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
  bio: "",
  status: "active" as const,
  mode: "live" as const,
  item_public_ids: ["s_qabul"],
  queue_count: 2,
};

const saved = {
  id: 41,
  business_account_id: 7,
  customer_account_id: 5,
  item_public_id: "s_qabul",
  provider_id: 5,
  patient_name: "Ali",
  phone: "",
  service_name: "Qabul",
  provider_name: "Ali Valiyev",
  queue_date: "2026-08-02",
  queue_no: 3,
  queue_code: "QAB-003",
  source: "online",
  status: "waiting" as const,
  note: "",
  slot_time: "",
  ahead_count: 2,
  avg_minutes: 20,
  wait_minutes: 40,
  created_at: "2026-08-02T07:00:00Z",
  updated_at: "2026-08-02T07:00:00Z",
};

function queueApi(overrides: Record<string, unknown> = {}) {
  return {
    getQueueOptions: vi.fn().mockResolvedValue({
      business_public_id: "b_shifo",
      item_public_id: "s_qabul",
      queue_date: "2026-08-02",
      providers: [provider],
    }),
    getQueueSlots: vi.fn().mockResolvedValue({ mode: "live", slots: [] }),
    createQueue: vi.fn().mockResolvedValue(saved),
    ...overrides,
  };
}

describe("v1656 ommaviy navbat olish pariteti", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-08-02T07:00:00Z"));
  });

  it("live rejimda sana, shifokor va navbat yaratishni aynan bajaradi", async () => {
    const user = userEvent.setup();
    const api = queueApi();
    const onBooked = vi.fn();
    const onClose = vi.fn();
    const onMessage = vi.fn();
    render(
      <QueueBookingV1656
        api={api}
        target={target}
        onBooked={onBooked}
        onClose={onClose}
        onMessage={onMessage}
      />,
    );

    expect(screen.getByText("Qabul — navbat")).toHaveClass("acf-title");
    expect(screen.getByLabelText("Sana (YYYY-MM-DD)")).toHaveValue("2026-08-02");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(api.getQueueOptions).toHaveBeenCalledWith(
      "b_shifo", "s_qabul", "2026-08-02",
    );

    const providerDialog = await screen.findByRole("dialog");
    expect(providerDialog.querySelector(".acf-title"))
      .toHaveTextContent("Shifokorni tanlang");
    expect(screen.getByRole("option", {
      name: "Ali Valiyev — Kardiolog (navbat 2 ta)",
    })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Shifokor"), "5");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(api.createQueue).toHaveBeenCalledWith({
      business_public_id: "b_shifo",
      item_public_id: "s_qabul",
      provider_id: 5,
      queue_date: "2026-08-02",
      slot_time: "",
      note: "",
    });
    expect(onMessage).toHaveBeenCalledWith("Navbatingiz: QAB-003");
    expect(onBooked).toHaveBeenCalledWith(saved);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("slot rejimda faqat bo'sh vaqtni tanlagandan keyin saqlaydi", async () => {
    const user = userEvent.setup();
    const slotProvider = { ...provider, mode: "slot" as const, queue_count: 0 };
    const api = queueApi({
      getQueueOptions: vi.fn().mockResolvedValue({
        business_public_id: "b_shifo",
        item_public_id: "s_qabul",
        queue_date: "2026-08-02",
        providers: [slotProvider],
      }),
      getQueueSlots: vi.fn().mockResolvedValue({
        mode: "slot",
        slots: ["12:20", "12:40"],
      }),
      createQueue: vi.fn().mockResolvedValue({
        ...saved,
        queue_code: "QAB-1220",
        slot_time: "12:20",
      }),
    });
    render(
      <QueueBookingV1656
        api={api}
        target={target}
        onBooked={vi.fn()}
        onClose={vi.fn()}
        onMessage={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    await user.selectOptions(await screen.findByLabelText("Shifokor"), "5");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(api.getQueueSlots).toHaveBeenCalledWith(
      "b_shifo", "s_qabul", 5, "2026-08-02",
    );
    expect(await screen.findByText("Qabul vaqtini tanlang")).toHaveClass("acf-title");
    await user.selectOptions(screen.getByLabelText("Bo'sh vaqtlar"), "12:20");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(api.createQueue).toHaveBeenCalledWith(expect.objectContaining({
      provider_id: 5,
      slot_time: "12:20",
    }));
  });

  it("provider yoki slot topilmasa monolitdagi xabarni aynan beradi", async () => {
    const user = userEvent.setup();
    const onMessage = vi.fn();
    const onClose = vi.fn();
    const api = queueApi({
      getQueueOptions: vi.fn().mockResolvedValue({
        business_public_id: "b_shifo",
        item_public_id: "s_qabul",
        queue_date: "2026-08-02",
        providers: [],
      }),
    });
    render(
      <QueueBookingV1656
        api={api}
        target={target}
        onBooked={vi.fn()}
        onClose={onClose}
        onMessage={onMessage}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(onMessage).toHaveBeenCalledWith("Shifokor hali biriktirilmagan.");
    expect(onClose).toHaveBeenCalledOnce();
  });
});
