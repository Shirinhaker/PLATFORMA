import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type {
  BusinessOnlineActionInput,
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import { BusinessProfile } from "./BusinessProfile";


const identity = {
  account_id: 7,
  account_type: "business" as const,
  name: "Muhr",
  login: "muhr1",
  csrf_token: "csrf",
  expires_at: "2026-08-30T08:00:00Z",
};

const cabinetPayload: Record<string, BusinessOnlineRecord[]> = {
  business_subscriptions: [],
  subscription_payments: [],
  item_groups: [{ id: 3, name: "Nonushta", kind: "product" }],
  items: [{
    id: 21,
    name: "Tuxum barak",
    group_id: 3,
    group_name: "Nonushta",
    price: 20000,
    unit: "dona",
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
  dining_places: [{
    id: 5,
    kind: "table",
    name: "Stol 1",
    seats: 4,
    x: 4,
    y: 4,
    locked: 1,
  }],
  dining_orders: [],
};

const diningProfile = {
  account_id: 7,
  name: "Muhr",
  phone: "",
  description: "",
  public_username: "muhr1",
  direction: "Umumiy ovqatlanish",
  activity_type: "Kafe",
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
  cabinet_payload: cabinetPayload,
};

function api(
  profile = diningProfile,
  payload = cabinetPayload,
) {
  const getBusinessOnlineResource = vi.fn(async (
    resource: BusinessOnlineResource,
  ) => ({
    resource,
    items: payload[resource] ?? [],
  }));
  const applyBusinessOnlineAction = vi.fn(async (
    resource: BusinessOnlineResource,
    action: string,
    body: BusinessOnlineActionInput,
  ) => {
    const item = resource === "dining_places"
      ? {
        ...(payload.dining_places?.[0] ?? {}),
        ...(action === "create_order" ? { active_id: 42 } : {}),
      }
      : resource === "dining_orders"
        ? {
          ...(payload.dining_orders?.[0] ?? {}),
          id: body.record_id,
        }
        : null;
    return {
      resource,
      item,
      items: payload[resource] ?? [],
    };
  });
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
    createBusinessOnlineRecord: vi.fn(async (
      resource: BusinessOnlineResource,
      record: BusinessOnlineRecord,
    ) => ({
      resource,
      item: { id: 6, ...record },
      items: [...(payload[resource] ?? []), { id: 6, ...record }],
    })),
    patchBusinessOnlineRecord: vi.fn(async (
      resource: BusinessOnlineResource,
      id: number | string,
      patch: BusinessOnlineRecord,
    ) => ({
      resource,
      item: { id, ...patch },
      items: (payload[resource] ?? []).map((row) => (
        String(row.id) === String(id) ? { ...row, ...patch } : row
      )),
    })),
    deleteBusinessOnlineRecord: vi.fn(async (
      resource: BusinessOnlineResource,
    ) => ({
      resource,
      item: null,
      items: payload[resource] ?? [],
    })),
    applyBusinessOnlineAction,
  };
}

async function renderCabinet(
  profile = diningProfile,
  payload = cabinetPayload,
) {
  const user = userEvent.setup();
  const client = api(profile, payload);
  const rendered = render(
    <BusinessProfile
      api={client}
      identity={identity}
      onLogout={vi.fn()}
      onSwitched={vi.fn()}
    />,
  );
  await screen.findByRole("heading", { name: "Muhr" });
  return { user, client, ...rendered };
}

async function openDining(
  user: ReturnType<typeof userEvent.setup>,
) {
  await user.click(screen.getByRole("button", { name: /Stollar va xonalar/ }));
  return screen.findByRole("heading", { name: "Stollar va xonalar" });
}


describe("v1656 stollar va xonalar pariteti", () => {
  it("faqat Umumiy ovqatlanishda aynan Onlaynlashtirish ichida ko'rinadi", async () => {
    const { user, container, unmount } = await renderCabinet();

    const menu = screen.getByRole("button", { name: /Stollar va xonalar/ });
    expect(menu).toHaveTextContent("Zal rejasini joylashtirish");
    expect(screen.queryByText("Yo‘nalishga xos bo‘limlar"))
      .not.toBeInTheDocument();

    await user.click(menu);
    expect(await screen.findByText("Zal rejasi")).toBeInTheDocument();
    expect(screen.getByText(
      "Belgini harakatlantirish uchun uch nuqtali menyuni oching.",
    )).toBeInTheDocument();
    expect(screen.getByRole("button", {
      name: "Stol yoki xona qo'shish",
    })).toHaveClass("dining-add");
    expect(container.querySelector(".dining-wrap")).toBeInTheDocument();
    expect(container.querySelector(".dining-plan")).toBeInTheDocument();

    unmount();
    const savdoProfile = {
      ...diningProfile,
      direction: "Savdo",
      activity_type: "Oziq-ovqat do'koni",
    };
    await renderCabinet(savdoProfile);
    expect(screen.queryByRole("button", { name: /Stollar va xonalar/ }))
      .not.toBeInTheDocument();
  });

  it("qo'shish, majburiy nom, bron va o'chirish tasdig'ini aynan bajaradi", async () => {
    const { user, client } = await renderCabinet();
    await openDining(user);

    await user.click(screen.getByRole("button", {
      name: "Stol yoki xona qo'shish",
    }));
    expect(screen.getByText("Nima qo'shamiz?")).toHaveClass("acf-title");
    await user.click(screen.getByRole("button", { name: "🪑 Stol" }));
    expect(screen.getByText("Yangi stol")).toHaveClass("acf-title");
    expect(screen.getByPlaceholderText("Masalan: Stol 1")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("4")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Stol nomini kiriting.");
    await user.type(screen.getByPlaceholderText("Masalan: Stol 1"), "Stol 2");
    await user.type(screen.getByPlaceholderText("4"), "6");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(client.createBusinessOnlineRecord).toHaveBeenCalledWith(
      "dining_places",
      { kind: "table", name: "Stol 2", seats: 6 },
    );

    await user.click(screen.getAllByRole("button", { name: "Menyu" })[0]!);
    expect(screen.getByRole("button", { name: "🛒 Zakaz qilish" }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "✥ Harakatlantirish" }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "🔒 Qotirish" }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "✏️ Tahrirlash" }))
      .toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "✏️ Tahrirlash" }));
    expect(screen.getByText("Tahrirlash")).toHaveClass("acf-title");
    expect(screen.getByPlaceholderText("Masalan: Stol 1"))
      .toHaveValue("Stol 1");
    await user.click(screen.getByRole("button", { name: "Bekor qilish" }));

    await user.click(screen.getAllByRole("button", { name: "Menyu" })[0]!);
    await user.click(screen.getByRole("button", { name: "✥ Harakatlantirish" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Belgini bosib ushlab, kerakli joyga suring.",
    );
    expect(document.querySelectorAll(".dining-place")[0]).toHaveClass("moving");
    await user.click(screen.getAllByRole("button", { name: "Menyu" })[0]!);
    await user.click(screen.getByRole("button", { name: "🔒 Qotirish" }));
    expect(client.patchBusinessOnlineRecord).toHaveBeenCalledWith(
      "dining_places",
      5,
      { x: 4, y: 4, locked: 1 },
    );

    await user.click(screen.getAllByRole("button", { name: "Menyu" })[0]!);
    await user.click(screen.getByRole("button", { name: "📅 Bron qilish" }));
    expect(screen.getByText("📅 Stol 1 — bron")).toHaveClass("acf-title");
    await user.click(screen.getByRole("button", { name: "Bron qilish" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Mijoz ismi, sana va vaqtni kiriting.",
    );
    await user.type(screen.getByPlaceholderText("Mijoz ismi"), "Ali");
    fireEvent.change(screen.getByDisplayValue(/\d{4}-\d{2}-\d{2}/), {
      target: { value: "2026-08-01" },
    });
    fireEvent.change(containerTimeInput(), { target: { value: "19:30" } });
    await user.click(screen.getByRole("button", { name: "Bron qilish" }));
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "dining_places",
      "book",
      expect.objectContaining({
        record_id: 5,
        payload: expect.objectContaining({
          customer_name: "Ali",
          booking_date: "2026-08-01",
          booking_time: "19:30",
        }),
      }),
    );

    await user.click(screen.getByRole("button", { name: "Menyu" }));
    await user.click(screen.getByRole("button", { name: "🗑 O'chirish" }));
    expect(screen.getByText("Stol 1 o'chirilsinmi?")).toHaveClass("acf-text");
    expect(screen.getByRole("button", { name: "O'chirish" }))
      .toHaveClass("danger");
    await user.click(screen.getByRole("button", { name: "O'chirish" }));
    expect(client.deleteBusinessOnlineRecord).toHaveBeenCalledWith(
      "dining_places",
      5,
    );
  });

  it("zal va mahsulotlarning monolitdagi bo'sh holatlarini aynan ko'rsatadi", async () => {
    const emptyPayload = {
      ...cabinetPayload,
      dining_places: [],
      dining_orders: [],
      items: [],
      item_groups: [],
    };
    const emptyProfile = {
      ...diningProfile,
      cabinet_payload: emptyPayload,
    };
    const first = await renderCabinet(emptyProfile, emptyPayload);
    await openDining(first.user);
    const emptyPlan = document.querySelector(".dining-empty");
    expect(emptyPlan).toBeVisible();
    expect(emptyPlan).toHaveTextContent(
      "Hozircha stol yoki xona yo'q.Yuqoridagi + tugmasini bosing.",
    );

    first.unmount();
    const noMenuPayload = {
      ...cabinetPayload,
      items: [],
      item_groups: [],
    };
    const noMenuProfile = {
      ...diningProfile,
      cabinet_payload: noMenuPayload,
    };
    const second = await renderCabinet(noMenuProfile, noMenuPayload);
    await openDining(second.user);
    await second.user.click(screen.getByRole("button", { name: "Menyu" }));
    await second.user.click(screen.getByRole("button", {
      name: "🛒 Zakaz qilish",
    }));
    expect(screen.getByRole("heading", { name: "Mahsulot yo'q" }))
      .toBeInTheDocument();
    expect(screen.getByText(
      "Avval Mahsulot va xizmatlar bo'limida mahsulot qo'shing.",
    )).toBeInTheDocument();
  });

  it("cab-dining-order yangi zakaz oqimini aynan ko'rsatadi", async () => {
    const { user, client } = await renderCabinet();
    await openDining(user);
    await waitFor(() => expect(client.getBusinessOnlineResource)
      .toHaveBeenCalledWith("items"));

    await user.click(screen.getByRole("button", { name: "Menyu" }));
    await user.click(screen.getByRole("button", { name: "🛒 Zakaz qilish" }));

    expect(screen.getByRole("heading", { name: "Zakaz qilish" }))
      .toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "← Orqaga" }));
    expect(screen.getByText("Zal rejasi")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Menyu" }));
    await user.click(screen.getByRole("button", { name: "🛒 Zakaz qilish" }));
    expect(screen.getByText("Stol 1 — yangi zakaz")).toBeInTheDocument();
    expect(screen.getByText("Mahsulotlarni + va − orqali tanlang."))
      .toBeInTheDocument();
    expect(screen.getByPlaceholderText("Mahsulot yoki guruhni qidirish..."))
      .toBeInTheDocument();
    expect(screen.getByPlaceholderText("Mijoz ismi — ixtiyoriy"))
      .toBeInTheDocument();
    expect(screen.getByPlaceholderText("Izoh — ixtiyoriy"))
      .toBeInTheDocument();
    const search = screen.getByPlaceholderText(
      "Mahsulot yoki guruhni qidirish...",
    );
    await user.type(search, "lavash");
    expect(screen.getByRole("heading", { name: "Topilmadi" }))
      .toBeInTheDocument();
    expect(screen.getByText("Boshqa nom bilan qidirib ko'ring."))
      .toBeInTheDocument();
    await user.clear(search);
    await user.click(screen.getByRole("button", { name: "Zakazni saqlash" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Kamida bitta mahsulot tanlang.",
    );

    await user.click(screen.getByRole("button", { name: "+" }));
    expect(screen.getByText("Tuxum barak").closest(".dorder-row"))
      .toHaveTextContent("20 000 so'm so'm · dona");
    expect(screen.getByText("Jami").nextElementSibling)
      .toHaveTextContent("20 000 so'm so'm");
    await user.type(
      screen.getByPlaceholderText("Mijoz ismi — ixtiyoriy"),
      "Vali",
    );
    await user.click(screen.getByRole("button", { name: "Zakazni saqlash" }));
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "dining_places",
      "create_order",
      {
        record_id: 5,
        payload: {
          items: [{ item_id: 21, qty: 1 }],
          customer_name: "Vali",
          note: "",
        },
      },
    );
  });

  it("mavjud zakazga taom qo'shish variantini aynan ko'rsatadi", async () => {
    const occupiedPayload = {
      ...cabinetPayload,
      dining_places: [{
        ...cabinetPayload.dining_places![0],
        active_id: 41,
        active_kind: "order",
        total: 20000,
      }],
      dining_orders: [{
        id: 41,
        place_id: 5,
        kind: "order",
        status: "active",
        total: 20000,
      }],
    };
    const occupiedProfile = {
      ...diningProfile,
      cabinet_payload: occupiedPayload,
    };
    const { user, client } = await renderCabinet(
      occupiedProfile,
      occupiedPayload,
    );
    await openDining(user);
    await user.click(screen.getByRole("button", { name: "Menyu" }));
    await user.click(screen.getByRole("button", { name: "✅ Bo'shatish" }));
    expect(screen.getByText(
      "Stol 1 bo'shatilsinmi? Faol zakaz va bron yakunlanadi.",
    )).toHaveClass("acf-text");
    await user.click(screen.getByRole("button", { name: "Bekor qilish" }));
    await user.click(screen.getByRole("button", { name: "Menyu" }));
    await user.click(screen.getByRole("button", {
      name: "🛒 Zakazga taom qo‘shish",
    }));

    expect(screen.getByText("Stol 1 — zakazga qo‘shish")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Mijoz ismi — ixtiyoriy"))
      .not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Qo‘shimcha izoh — ixtiyoriy"))
      .toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "+" }));
    await user.click(screen.getByRole("button", { name: "Zakazga qo‘shish" }));
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "dining_orders",
      "add_items",
      {
        record_id: 41,
        payload: {
          items: [{ item_id: 21, qty: 1 }],
          note: "",
        },
      },
    );
  });
});

function containerTimeInput(): HTMLInputElement {
  const input = document.querySelector('input[type="time"]');
  if (!(input instanceof HTMLInputElement)) {
    throw new Error("Bron vaqti maydoni topilmadi.");
  }
  return input;
}
