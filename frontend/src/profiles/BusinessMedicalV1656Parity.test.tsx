import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

const queueDirections = [
  "Transport va logistika",
  "Xizmat ko'rsatish",
  "Maishiy xizmatlar",
  "Qurilish",
  "Tibbiy xizmatlar",
  "Ko'chmas mulk",
  "Axborot texnologiyalari",
  "Konsalting va professional",
  "Madaniyat, sport, ko'ngilochar",
  "Turizm va mehmonxona",
  "Reklama va marketing",
  "Poligrafiya va nashriyot",
  "Moliyaviy faoliyat",
  "Import-eksport",
];

const payload: Record<string, BusinessOnlineRecord[]> = {
  business_subscriptions: [],
  subscription_payments: [],
  item_groups: [],
  items: [{
    id: 31,
    name: "Qabul",
    kind: "service",
    queue_enabled: 1,
    price: 50000,
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
  dining_places: [],
  dining_orders: [],
  medical_staff: [{
    id: 11,
    name: "Ali Valiyev",
    profession: "Terapevt",
    status: "active",
  }],
  medical_doctors: [{
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
    mode: "slot",
    room: "12-xona",
    bio: "Shifokor haqida",
    status: "active",
    item_ids: [31],
  }],
  medical_queue: [{
    id: 41,
    item_id: 31,
    staff_id: 11,
    patient_name: "Vali",
    phone: "901234567",
    queue_date: "2026-08-01",
    queue_no: 1,
    queue_code: "QAB-001",
    source: "online",
    status: "waiting",
    slot_time: "09:00",
    service_name: "Qabul",
    doctor_name: "Ali Valiyev",
  }],
};

function profile(
  direction = "Tibbiy xizmatlar",
  cabinetPayload: Record<string, BusinessOnlineRecord[]> = payload,
) {
  return {
    account_id: 7,
    name: "Muhr klinikasi",
    phone: "",
    description: "",
    public_username: "muhr1",
    direction,
    activity_type: direction === "Tibbiy xizmatlar" ? "Klinika" : "Xizmat",
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
  const createBusinessOnlineRecord = vi.fn(async (
    resource: BusinessOnlineResource,
    record: BusinessOnlineRecord,
  ) => ({
    resource,
    item: { id: 6, ...record },
    items: [...(cabinetPayload[resource] ?? []), { id: 6, ...record }],
  }));
  const patchBusinessOnlineRecord = vi.fn(async (
    resource: BusinessOnlineResource,
    id: number | string,
    patch: BusinessOnlineRecord,
  ) => ({
    resource,
    item: { id, ...patch },
    items: (cabinetPayload[resource] ?? []).map((row) => (
      String(row.id) === String(id) ? { ...row, ...patch } : row
    )),
  }));
  const applyBusinessOnlineAction = vi.fn(async (
    resource: BusinessOnlineResource,
    action: string,
    body: BusinessOnlineActionInput,
  ) => ({
    resource,
    item: action === "offline_add"
      ? { id: 42, queue_code: "QAB-002", ...body.payload }
      : { id: body.record_id, ...body.payload },
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
    createBusinessOnlineRecord,
    patchBusinessOnlineRecord,
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


describe("v1656 xizmat ko'rsatuvchilar va navbat pariteti", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-08-01T05:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("14 navbatli yo'nalishda aynan Onlaynlashtirish ichida mos nomlarni ko'rsatadi", async () => {
    for (const direction of queueDirections) {
      const current = profile(direction);
      const { unmount } = await renderCabinet(current);
      const medical = direction === "Tibbiy xizmatlar";
      const providers = screen.getByRole("button", {
        name: new RegExp(medical ? "Shifokorlar" : "Xizmat ko‘rsatuvchilar"),
      });
      expect(providers).toHaveTextContent(
        medical
          ? "Shifokor kartasi, xizmat va ish jadvali"
          : "Xizmat ko‘rsatuvchi kartasi, xizmat va ish jadvali",
      );
      expect(screen.getByRole("button", { name: /Navbat boshqaruvi/ }))
        .toHaveTextContent("Onlayn va oflayn yagona navbat");
      expect(screen.queryByText("Yo‘nalishga xos bo‘limlar"))
        .not.toBeInTheDocument();
      unmount();
    }

    for (const direction of ["Savdo", "Umumiy ovqatlanish", "Ta'lim faoliyati"]) {
      const { unmount } = await renderCabinet(profile(direction));
      expect(screen.queryByRole("button", { name: /Navbat boshqaruvi/ }))
        .not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /Xizmat ko‘rsatuvchilar/ }))
        .not.toBeInTheDocument();
      unmount();
    }
  });

  it("cab-medical-doctors ro'yxati va cab-medical-doctor-formni aynan ko'rsatadi", async () => {
    const { user, client, container } = await renderCabinet();
    await user.click(screen.getByRole("button", { name: /Shifokorlar/ }));

    expect(screen.getByRole("button", { name: "+ Shifokor biriktirish" }))
      .toHaveClass("btn", "btn-primary", "btn-block");
    expect(screen.queryByText("v1656’dan ko‘chirilgan haqiqiy ma’lumotlar"))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yangilash" }))
      .not.toBeInTheDocument();
    const doctor = screen.getByRole("button", { name: /Ali Valiyev/ });
    expect(doctor).toHaveAttribute("class", "panel-card");
    expect(doctor).toHaveStyle({
      display: "block",
      width: "100%",
      textAlign: "left",
      color: "inherit",
    });
    expect(doctor).toHaveTextContent("Kardiolog · 12-xona");
    expect(doctor).toHaveTextContent("Faol");
    expect(doctor).toHaveTextContent("1 xizmat · 08:00–17:00 · 🕐 Vaqtli qabul");

    await user.click(doctor);
    expect(screen.getByText("Ma'muriyatdagi shifokor")).toBeInTheDocument();
    expect(screen.getByLabelText("Ma'muriyatdagi shifokor")).toBeDisabled();
    expect(screen.getByLabelText("Mutaxassisligi")).toHaveValue("Kardiolog");
    expect(screen.getByLabelText("Tajribasi (yil)")).toHaveValue(8);
    expect(screen.getByLabelText("Malaka/toifasi")).toHaveValue("Oliy toifa");
    expect(screen.getByLabelText("Ish kunlari")).toHaveAttribute(
      "placeholder",
      "1,2,3,4,5,6",
    );
    expect(screen.getByLabelText("O'rtacha qabul (daqiqa)")).toHaveValue(20);
    expect(screen.getByLabelText("Navbat turi")).toHaveValue("slot");
    expect(screen.getByLabelText("Xona/joy")).toHaveValue("12-xona");
    expect(screen.getByLabelText("Shifokor haqida")).toHaveValue(
      "Shifokor haqida",
    );
    expect(screen.getByLabelText("Holati")).toHaveValue("active");
    expect(screen.getByText("Qabul qiladigan xizmatlari"))
      .toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Qabul" })).toBeChecked();
    expect(container.querySelector(".form-wrap")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Xona/joy"));
    await user.type(screen.getByLabelText("Xona/joy"), "15-xona");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(client.patchBusinessOnlineRecord).toHaveBeenCalledWith(
      "medical_doctors",
      5,
      expect.objectContaining({
        staff_id: 11,
        room: "15-xona",
        item_ids: [31],
      }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Shifokor saqlandi.",
    );
  });

  it("bo'sh ro'yxat, yangi forma va majburiy tanlov xabarlarini aynan beradi", async () => {
    const emptyPayload = {
      ...payload,
      medical_doctors: [],
      medical_staff: [],
      items: [],
    };
    const { user } = await renderCabinet(
      profile("Tibbiy xizmatlar", emptyPayload),
      emptyPayload,
    );
    await user.click(screen.getByRole("button", { name: /Shifokorlar/ }));
    expect(screen.getByRole("heading", { name: "Shifokor yo‘q" }))
      .toBeInTheDocument();
    expect(screen.getByText(
      "Ma’muriyatdagi faol xodimni xizmatga biriktiring.",
    )).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "+ Shifokor biriktirish" }));
    expect(screen.getByText(
      "Avval xizmatlar bo‘limida xizmat uchun navbat tizimini yoqing.",
    )).toHaveClass("idesc");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Xodim va kamida bitta xizmatni tanlang.",
    );
  });

  it("cab-medical-queue ro'yxati, holatlar va bekor qilish tasdig'ini aynan bajaradi", async () => {
    const { user, client, container } = await renderCabinet();
    await user.click(screen.getByRole("button", { name: /Navbat boshqaruvi/ }));

    expect(screen.getByText("🏥 Yagona navbat")).toBeInTheDocument();
    expect(screen.getByText(
      "Onlayn va oflayn bemorlar bitta ketma-ketlikda.",
    )).toHaveClass("idesc");
    expect(container.querySelector('input[type="date"]')).toHaveValue("2026-08-01");
    const queue = screen.getByText("QAB-001 · Vali").closest(".panel-card");
    expect(queue).not.toBeNull();
    expect(queue).toHaveTextContent(
      "Qabul · Ali Valiyev · Onlayn · 🕐 09:00",
    );
    expect(queue).toHaveTextContent("Kutilmoqda");

    await user.click(within(queue as HTMLElement).getByRole("button", {
      name: "Chaqirish",
    }));
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "medical_queue",
      "set_status",
      { record_id: 41, payload: { status: "called" } },
    );

    await user.click(within(queue as HTMLElement).getByRole("button", {
      name: "Bekor qilish",
    }));
    expect(screen.getByText(
      "Bu navbat bekor qilinsinmi? Foydalanuvchiga xabar yuboriladi.",
    )).toHaveClass("acf-text");
    const dialog = screen.getByRole("dialog");
    const confirm = within(dialog).getAllByRole("button", {
      name: "Bekor qilish",
    }).find((button) => button.classList.contains("danger"));
    expect(confirm).toHaveClass("danger");
    await user.click(confirm!);
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "medical_queue",
      "set_status",
      { record_id: 41, payload: { status: "cancelled" } },
    );
  });

  it("oflayn navbat va ikkita navbatni almashtirish oynalarini aynan bajaradi", async () => {
    const { user, client } = await renderCabinet();
    await user.click(screen.getByRole("button", { name: /Navbat boshqaruvi/ }));

    await user.click(screen.getByRole("button", { name: "+ Oflayn navbat" }));
    expect(screen.getByText("Oflayn navbat")).toHaveClass("acf-title");
    const patientLabel = screen.getByText("Bemor ism-familiyasi");
    expect(patientLabel.tagName).toBe("DIV");
    expect(patientLabel).not.toHaveAttribute("class");
    expect(document.querySelector(".app-modal-back.on")?.tagName).toBe("DIV");
    expect(screen.getByText("Telefon")).toBeInTheDocument();
    expect(screen.getByText("Xizmat")).toBeInTheDocument();
    expect(screen.getByText("Shifokor")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Bemor ism-familiyasi"), "Hasan");
    await user.selectOptions(screen.getByLabelText("Xizmat"), "31");
    await user.selectOptions(screen.getByLabelText("Shifokor"), "11");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "medical_queue",
      "offline_add",
      {
        record_id: undefined,
        payload: {
          patient_name: "Hasan",
          phone: "",
          item_id: 31,
          staff_id: 11,
          queue_date: "2026-08-01",
        },
      },
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Navbat: QAB-002",
    );

    await user.click(screen.getByRole("button", {
      name: "↔ Navbatlarni almashtirish",
    }));
    expect(screen.getByText("Navbatlarni almashtirish")).toHaveClass("acf-title");
    await user.type(screen.getByLabelText("Birinchi navbat ID"), "41");
    await user.type(screen.getByLabelText("Ikkinchi navbat ID"), "42");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(client.applyBusinessOnlineAction).toHaveBeenCalledWith(
      "medical_queue",
      "swap",
      { record_id: 41, payload: { other_queue_id: 42 } },
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Navbatlar almashtirildi.",
    );
  });

  it("boshqa navbatli yo'nalishda mijoz va xizmat ko'rsatuvchi matnlarini ishlatadi", async () => {
    const { user } = await renderCabinet(profile("Xizmat ko'rsatish"));
    await user.click(screen.getByRole("button", {
      name: /Xizmat ko‘rsatuvchilar/,
    }));
    expect(screen.getByRole("button", {
      name: "+ Xizmat ko‘rsatuvchi biriktirish",
    })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "← Kabinetga qaytish" }));
    await user.click(screen.getByRole("button", { name: /Navbat boshqaruvi/ }));
    expect(screen.getByText(
      "Onlayn va oflayn mijozlar bitta ketma-ketlikda.",
    )).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xizmat ko‘rsatuvchilar" }))
      .toBeInTheDocument();
  });
});
