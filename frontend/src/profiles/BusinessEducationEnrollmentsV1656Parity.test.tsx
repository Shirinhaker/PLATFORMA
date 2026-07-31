import { render, screen, waitFor, within } from "@testing-library/react";
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

const payload: Record<string, BusinessOnlineRecord[]> = {
  business_subscriptions: [],
  subscription_payments: [],
  item_groups: [],
  items: [
    { id: 51, name: "Ingliz tili", kind: "service" },
    { id: 52, name: "Matematika", kind: "service" },
  ],
  listings: [],
  orders: [],
  messages: [],
  business_reviews: [],
  advertisements: [],
  stories: [],
  notifications: [],
  followers: [],
  following: [],
  dining_places: [],
  dining_orders: [],
  medical_staff: [],
  medical_doctors: [],
  medical_queue: [],
  education_groups: [
    { id: 61, name: "English A1", course_item_id: 51, status: "active" },
    { id: 62, name: "Umumiy guruh", course_item_id: null, status: "active" },
    { id: 63, name: "Algebra", course_item_id: 52, status: "active" },
  ],
  education_students: [],
  education_enrollments: [
    {
      id: 71,
      course_item_id: 51,
      customer_name: "Ali Valiyev",
      phone: "+998901234567",
      note: "Kechki guruh",
      status: "new",
      course_name: "Ingliz tili",
    },
    {
      id: 72,
      course_item_id: 52,
      customer_name: "Dilnoza",
      phone: "+998909876543",
      status: "accepted",
      course_name: "Matematika",
      group_id: 63,
      group_name: "Algebra",
    },
    {
      id: 73,
      course_item_id: 51,
      customer_name: "Vali",
      phone: "",
      status: "rejected",
      course_name: "Ingliz tili",
    },
  ],
};

function profile(
  direction = "Ta'lim faoliyati",
  cabinetPayload: Record<string, BusinessOnlineRecord[]> = payload,
) {
  return {
    account_id: 7,
    name: "Muhr o‘quv markazi",
    phone: "",
    description: "",
    public_username: "muhr1",
    direction,
    activity_type: "O‘quv markazi",
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
}

function api(
  business = profile(),
  cabinetPayload: Record<string, BusinessOnlineRecord[]> = payload,
) {
  const getBusinessOnlineResource = vi.fn(async (
    resource: BusinessOnlineResource,
  ) => ({ resource, items: cabinetPayload[resource] ?? [] }));
  const applyBusinessOnlineAction = vi.fn(async (
    resource: BusinessOnlineResource,
    action: string,
    body: BusinessOnlineActionInput,
  ) => ({
    resource,
    item: { id: body.record_id, status: action === "accept" ? "accepted" : "rejected" },
    items: cabinetPayload[resource] ?? [],
  }));
  return {
    getSession: vi.fn().mockResolvedValue(identity),
    getBusinessProfile: vi.fn().mockResolvedValue(business),
    updateBusinessProfile: vi.fn().mockResolvedValue(business),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    attachBusinessLogo: vi.fn().mockResolvedValue(business),
    attachBusinessPaymentQr: vi.fn().mockResolvedValue(business),
    switchCabinet: vi.fn(),
    logout: vi.fn(),
    getBusinessOnlineResource,
    createBusinessOnlineRecord: vi.fn(),
    patchBusinessOnlineRecord: vi.fn(),
    deleteBusinessOnlineRecord: vi.fn(),
    applyBusinessOnlineAction,
  };
}

async function renderCabinet(
  business = profile(),
  cabinetPayload: Record<string, BusinessOnlineRecord[]> = payload,
) {
  const user = userEvent.setup();
  const client = api(business, cabinetPayload);
  const rendered = render(
    <BusinessProfile
      api={client}
      identity={identity}
      onLogout={vi.fn()}
      onSwitched={vi.fn()}
    />,
  );
  await screen.findByRole("heading", { name: business.name });
  return { user, client, ...rendered };
}

async function openEnrollments(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /Kursga yozilishlar/ }));
  return screen.findByRole("heading", { name: "Kursga yozilishlar" });
}


describe("v1656 kursga yozilishlar pariteti", () => {
  it("faqat Ta'lim faoliyatida Onlaynlashtirish ichida va yangi arizalar soni bilan ko'rinadi", async () => {
    const { unmount } = await renderCabinet();
    const heading = screen.getByRole("heading", { name: "Onlaynlashtirish" });
    const onlineGroup = heading.closest("section");
    expect(onlineGroup).not.toBeNull();
    const menu = within(onlineGroup as HTMLElement).getByRole("button", {
      name: /Kursga yozilishlar/,
    });
    expect(menu).toHaveTextContent("Yangi arizalarni guruhga qabul qilish");
    expect(menu.querySelector("em")).toHaveClass("order-badge");
    expect(menu.querySelector("em")).toHaveTextContent("1");

    unmount();
    await renderCabinet(profile("Savdo"));
    expect(screen.queryByRole("button", { name: /Kursga yozilishlar/ }))
      .not.toBeInTheDocument();
  });

  it("cab-education-enrollments matnlari, klasslari va mos guruhlarni aynan ko'rsatadi", async () => {
    const { user, client, container } = await renderCabinet();
    await openEnrollments(user);

    expect(screen.queryByText("v1656’dan ko‘chirilgan haqiqiy ma’lumotlar"))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yangilash" }))
      .not.toBeInTheDocument();
    expect(screen.getByText("Kursga yozilish arizalari")).toBeInTheDocument();
    expect(screen.getByText(
      "Arizani qabul qilishda o'quvchi biriktiriladigan guruhni tanlang.",
    )).toHaveClass("idesc");
    expect(container.querySelector(".form-wrap")).toBeInTheDocument();
    expect(container.querySelector(".ad-tabs")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yangi" })).toHaveClass("ad-tab", "on");
    expect(screen.getByRole("button", { name: "Qabul qilingan" })).toHaveClass("ad-tab");
    expect(screen.getByRole("button", { name: "Rad etilgan" })).toHaveClass("ad-tab");

    const card = screen.getByText("Ali Valiyev").closest(".panel-card");
    expect(card).not.toBeNull();
    expect(card).toHaveTextContent("📚 Ingliz tili · 📞 +998901234567");
    expect(card).toHaveTextContent("Yangi");
    expect(card).toHaveTextContent("Izoh: Kechki guruh");
    const select = within(card as HTMLElement).getByRole("combobox");
    expect(select).toHaveClass("input");
    expect(within(select).getByRole("option", { name: "Guruhni tanlang" }))
      .toBeInTheDocument();
    expect(within(select).getByRole("option", { name: "English A1" }))
      .toBeInTheDocument();
    expect(within(select).getByRole("option", { name: "Umumiy guruh" }))
      .toBeInTheDocument();
    expect(within(select).queryByRole("option", { name: "Algebra" }))
      .not.toBeInTheDocument();
    expect(within(card as HTMLElement).getByRole("button", { name: "Qabul qilish" }))
      .toHaveClass("btn", "btn-primary");
    expect(within(card as HTMLElement).getByRole("button", { name: "Rad etish" }))
      .toHaveClass("btn", "btn-outline");
    await waitFor(() => expect(client.getBusinessOnlineResource).toHaveBeenCalledWith(
      "education_groups",
    ));
    expect(client.getBusinessOnlineResource).toHaveBeenCalledWith(
      "education_enrollments",
    );
  });

  it("guruh tanlash tekshiruvi va qabul qilishni aynan bajaradi", async () => {
    const { user, client } = await renderCabinet();
    await openEnrollments(user);
    const card = screen.getByText("Ali Valiyev").closest(".panel-card") as HTMLElement;

    await user.click(within(card).getByRole("button", { name: "Qabul qilish" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Guruhni tanlang.");
    expect(client.applyBusinessOnlineAction).not.toHaveBeenCalled();

    await user.selectOptions(within(card).getByRole("combobox"), "61");
    await user.click(within(card).getByRole("button", { name: "Qabul qilish" }));
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "education_enrollments",
      "accept",
      { record_id: 71, payload: { group_id: 61 } },
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "O'quvchi guruhga qabul qilindi.",
    );
  });

  it("qabul qilingan/rad etilgan tablari va bo'sh holatni aynan ko'rsatadi", async () => {
    const { user, unmount } = await renderCabinet();
    await openEnrollments(user);

    await user.click(screen.getByRole("button", { name: "Qabul qilingan" }));
    expect(screen.getByText("Dilnoza")).toBeInTheDocument();
    expect(screen.getByText("Qabul qilindi")).toHaveClass("sort-chip");
    expect(screen.getByText("Guruh: Algebra")).toHaveClass("idesc");

    await user.click(screen.getByRole("button", { name: "Rad etilgan" }));
    expect(screen.getByText("Vali")).toBeInTheDocument();
    expect(screen.getByText("📚 Ingliz tili · 📞 —")).toBeInTheDocument();
    expect(screen.getByText("Rad etildi")).toHaveClass("sort-chip");

    unmount();
    const emptyPayload = { ...payload, education_enrollments: [] };
    const empty = await renderCabinet(
      profile("Ta'lim faoliyati", emptyPayload),
      emptyPayload,
    );
    await openEnrollments(empty.user);
    expect(screen.getByRole("heading", { name: "Arizalar yo'q" }))
      .toBeInTheDocument();
    expect(screen.getByText("Bu bo'limda hozircha ariza mavjud emas."))
      .toBeInTheDocument();
  });

  it("rad etish tasdig'i va amalini aynan bajaradi", async () => {
    const { user, client } = await renderCabinet();
    await openEnrollments(user);
    const card = screen.getByText("Ali Valiyev").closest(".panel-card") as HTMLElement;
    await user.click(within(card).getByRole("button", { name: "Rad etish" }));

    expect(screen.getByText("Bu ariza rad etilsinmi?")).toHaveClass("acf-text");
    const dialog = screen.getByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: "Rad etish" });
    expect(confirm).toHaveClass("acf-ok", "danger");
    await user.click(confirm);
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "education_enrollments",
      "reject",
      { record_id: 71, payload: {} },
    );
    expect(await screen.findByRole("status")).toHaveTextContent("Ariza rad etildi.");
  });
});
