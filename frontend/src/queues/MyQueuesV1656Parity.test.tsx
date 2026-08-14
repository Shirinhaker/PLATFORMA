import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MyQueuesV1656 } from "./MyQueuesV1656";


const liveQueue = {
  id: 41,
  business_account_id: 7,
  business_name: "Shifo markazi",
  business_direction: "Tibbiy xizmatlar",
  customer_account_id: 5,
  item_public_id: "s_qabul",
  provider_id: 11,
  patient_name: "Ali",
  phone: "",
  service_name: "Qabul",
  provider_name: "Ali Valiyev",
  queue_date: "2026-08-03",
  queue_no: 3,
  queue_code: "QAB-003",
  source: "online",
  status: "waiting" as const,
  note: "Qo'ng'iroq qiling",
  slot_time: "",
  ahead_count: 2,
  avg_minutes: 20,
  wait_minutes: 40,
  created_at: "2026-08-03T07:00:00Z",
  updated_at: "2026-08-03T07:00:00Z",
};


describe("v1656 mijoz navbatlari pariteti", () => {
  it("navbat, oldindagi odam va kutish vaqtini monolit matni bilan ko'rsatadi", async () => {
    const onFocusHandled = vi.fn();
    const api = {
      getMyQueues: vi.fn().mockResolvedValue([liveQueue]),
      cancelMyQueue: vi.fn(),
    };

    render(
      <MyQueuesV1656
        api={api}
        focusQueueId={41}
        onFocusHandled={onFocusHandled}
      />,
    );

    expect(await screen.findByRole("heading", { name: "📋 Navbatlar" }))
      .toBeInTheDocument();
    expect(screen.getByText("1 ta")).toBeInTheDocument();
    expect(screen.getByText("NAVBAT QAB-003")).toBeInTheDocument();
    expect(screen.getByText("🏢 Shifo markazi")).toBeInTheDocument();
    expect(screen.getByText("🩺 Ali Valiyev")).toBeInTheDocument();
    expect(screen.getByText("Kutilmoqda")).toBeInTheDocument();
    expect(screen.getByText(/Oldingizda:/)).toHaveTextContent("2 ta navbat");
    expect(screen.getByText(/Taxminiy kutish:/)).toHaveTextContent("~40 daqiqa");
    expect(screen.getByTestId("medical-queue-41"))
      .toHaveClass("medical-queue-focus");
    await waitFor(() => expect(onFocusHandled).toHaveBeenCalledWith(41));
  });

  it("faqat waiting/called navbatni aynan tasdiq matni bilan bekor qiladi", async () => {
    const user = userEvent.setup();
    const cancelled = { ...liveQueue, status: "cancelled" as const };
    const api = {
      getMyQueues: vi.fn().mockResolvedValue([
        liveQueue,
        { ...liveQueue, id: 42, queue_code: "QAB-004", status: "in_service" as const },
      ]),
      cancelMyQueue: vi.fn().mockResolvedValue(cancelled),
    };

    render(<MyQueuesV1656 api={api} />);

    const buttons = await screen.findAllByRole("button", { name: "Navbatni bekor qilish" });
    expect(buttons).toHaveLength(1);
    await user.click(buttons[0]!);
    expect(screen.getByRole("dialog", { name: "Navbatni bekor qilish" }))
      .toHaveTextContent("Navbatingizni bekor qilasizmi?");
    await user.click(screen.getByRole("button", { name: "Ha, bekor qilaman" }));

    expect(api.cancelMyQueue).toHaveBeenCalledWith(41);
    expect(await screen.findByRole("status")).toHaveTextContent("Navbat bekor qilindi.");
    expect(screen.getByTestId("medical-queue-41"))
      .toHaveTextContent("Bekor qilindi");
  });

  it("slot navbatida oldindagi odam o'rniga qabul vaqtini ko'rsatadi", async () => {
    render(
      <MyQueuesV1656 api={{
        getMyQueues: vi.fn().mockResolvedValue([{
          ...liveQueue,
          id: 43,
          queue_code: "QAB-1220",
          slot_time: "12:20",
          ahead_count: 0,
          wait_minutes: 0,
        }]),
        cancelMyQueue: vi.fn(),
      }} />,
    );

    expect(await screen.findByText(/Qabul vaqti:/)).toHaveTextContent("12:20");
    expect(screen.queryByText(/Oldingizda:/)).not.toBeInTheDocument();
  });
});
