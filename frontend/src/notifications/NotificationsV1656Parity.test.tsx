import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type {
  NotificationFilterRead,
  NotificationRead,
} from "../api/types";
import {
  ActionNotificationsV1656,
  NotificationsV1656,
  type NotificationsApi,
} from "./NotificationsV1656";


const notification: NotificationRead = {
  id: 11,
  title: "Yangi buyurtma",
  body: "Buyurtma #11 qabul qilindi",
  order_id: 11,
  listing_id: null,
  listing_public_id: "",
  dining_order_id: null,
  medical_queue_id: null,
  ride_id: null,
  action_type: "view_order",
  requires_action: true,
  is_read: false,
  created_at: 1_754_814_400,
  read_at: null,
  resolved_at: null,
};

const filter: NotificationFilterRead = {
  id: 3,
  cat: "uy",
  region: "Toshkent shahri",
  district: "Chilonzor",
  price_min: 100_000,
  price_max: 2_000_000,
  keyword: "hovli",
  created_at: 1_754_814_400,
};


function api(overrides: Partial<NotificationsApi> = {}): NotificationsApi {
  return {
    getNotifications: vi.fn().mockResolvedValue({ items: [notification], unread: 1 }),
    getActionNotifications: vi.fn().mockResolvedValue({
      items: [notification],
      count: 1,
    }),
    markNotificationRead: vi.fn().mockResolvedValue({ ok: true, read_at: 1 }),
    markAllNotificationsRead: vi.fn().mockResolvedValue({ ok: true, read_at: 1 }),
    getNotificationPreference: vi.fn().mockResolvedValue({
      enabled: true,
      orders_enabled: true,
    }),
    saveNotificationPreference: vi.fn().mockImplementation(async (body) => body),
    getNotificationFilters: vi.fn().mockResolvedValue([filter]),
    createNotificationFilter: vi.fn().mockImplementation(async (body) => ({
      id: 4,
      created_at: 1_754_814_401,
      ...body,
    })),
    deleteNotificationFilter: vi.fn().mockResolvedValue({ ok: true }),
    getPushStatus: vi.fn().mockResolvedValue({
      provider: "firebase",
      configured: true,
      active_devices: 1,
      pending: 0,
    }),
    ...overrides,
  };
}


describe("v1656 bildirishnomalar migratsiyasi", () => {
  it("loads normalized notifications, push preference and filters in parallel", async () => {
    const client = api();
    const unread = vi.fn();
    render(
      <NotificationsV1656
        api={client}
        onBack={vi.fn()}
        onUnreadChange={unread}
      />,
    );

    expect(await screen.findByText("Yangi buyurtma")).toBeInTheDocument();
    expect(screen.getByText("Push xizmati faol · 1 ta qurilma")).toBeInTheDocument();
    expect(screen.getByText("Uy-joy")).toBeInTheDocument();
    expect(screen.getByText(/Chilonzor/)).toBeInTheDocument();
    expect(unread).toHaveBeenCalledWith(1);
    expect(client.getNotifications).toHaveBeenCalledTimes(1);
    expect(client.getNotificationFilters).toHaveBeenCalledTimes(1);
  });

  it("marks and opens a notification then updates the unread badge", async () => {
    const client = api();
    const open = vi.fn();
    const unread = vi.fn();
    const user = userEvent.setup();
    render(
      <NotificationsV1656
        api={client}
        onBack={vi.fn()}
        onOpenNotification={open}
        onUnreadChange={unread}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /Yangi buyurtma/ }));

    await waitFor(() => expect(client.markNotificationRead).toHaveBeenCalledWith(11));
    expect(open).toHaveBeenCalledWith(notification);
    expect(unread).toHaveBeenLastCalledWith(0);
  });

  it("toggles push and saves a linked region/district listing filter", async () => {
    const client = api();
    const user = userEvent.setup();
    render(<NotificationsV1656 api={client} onBack={vi.fn()} />);

    const toggle = await screen.findByRole("checkbox");
    await user.click(toggle);
    expect(client.saveNotificationPreference).toHaveBeenCalledWith({
      enabled: false,
      orders_enabled: false,
    });

    await user.click(screen.getByRole("button", { name: /Yangi filtr qo‘shish/ }));
    await user.selectOptions(screen.getByLabelText(/Viloyat/), "Toshkent shahri");
    await user.selectOptions(screen.getByLabelText(/Tuman/), "Chilonzor");
    await user.type(screen.getByPlaceholderText(/mushuk/), "hovli");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    await waitFor(() => expect(client.createNotificationFilter).toHaveBeenCalledWith({
      cat: "uy",
      region: "Toshkent shahri",
      district: "Chilonzor",
      price_min: 0,
      price_max: 0,
      keyword: "hovli",
    }));
  });

  it("polls actionable notifications and opens the selected workflow", async () => {
    const client = api();
    const open = vi.fn();
    const user = userEvent.setup();
    render(
      <ActionNotificationsV1656
        api={client}
        onOpenNotification={open}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /Yangi buyurtma/ }));
    expect(client.markNotificationRead).toHaveBeenCalledWith(11);
    expect(open).toHaveBeenCalledWith(notification);
  });
});
