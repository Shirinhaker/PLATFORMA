import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BusinessProfile } from "./BusinessProfile";


const identity = {
  account_id: 7,
  account_type: "business" as const,
  name: "Muhr",
  login: "b_muhr",
  csrf_token: "csrf",
  expires_at: "2026-08-30T00:00:00Z",
};

const profile = {
  account_id: 7,
  name: "Muhr",
  phone: "912377784",
  description: "",
  public_username: "muhr1",
  direction: "Savdo",
  activity_type: "Oziq-ovqat do'koni",
  address: "Beruniy ko‘chasi, Qumqo‘rg‘on tumani",
  latitude: 37.838933493659454,
  longitude: 67.58345251326438,
  work_hours: { raw: "09:00-20:00" },
  pay_card: "5614681918687751",
  pay_holder: "BUNYOD ASHUROV",
  pay_qr_object_key: "private/business/7/payment_qr/qr.png",
  pay_qr_url: "https://media.example/qr.png",
  director: "",
  tax_id: "",
  logo_object_key: "private/business/7/logo/logo.png",
  logo_url: "https://media.example/logo.png",
  logo_x: 46.97,
  logo_y: 41.47,
  logo_zoom: 1.8,
  followers_count: 0,
  following_count: 1,
  rating_sum: 0,
  rating_count: 0,
  map_visible: true,
  dashboard_snapshot: {},
  recent_activity: [],
  cabinet_payload: {},
};

function api() {
  return {
    getSession: vi.fn().mockResolvedValue(identity),
    getBusinessProfile: vi.fn().mockResolvedValue(profile),
    updateBusinessProfile: vi.fn().mockImplementation(async (patch) => ({
      ...profile,
      ...patch,
    })),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    attachBusinessLogo: vi.fn().mockResolvedValue(profile),
    attachBusinessPaymentQr: vi.fn().mockResolvedValue(profile),
    getBusinessOnlineResource: vi.fn().mockImplementation(async (resource) => ({
      resource,
      items: [],
    })),
    getStaffSetup: vi.fn().mockResolvedValue({
      active: [],
      fired: [],
      active_count: 0,
      fired_count: 0,
      total_salary: 0,
      firm_login: "b_muhr",
      business_direction: "Savdo",
      professions: ["Sotuvchi"],
      permission_definitions: [],
      permission_templates: [],
    }),
    createStaffMember: vi.fn(),
    updateStaffMember: vi.fn(),
    fireStaffMember: vi.fn(),
    rehireStaffMember: vi.fn(),
    deleteStaffMember: vi.fn(),
    updateStaffAccess: vi.fn(),
    updateStaffSchedule: vi.fn(),
    createStaffProfession: vi.fn(),
    getStaffAttendance: vi.fn(),
    updateStaffAttendance: vi.fn(),
    getExpenses: vi.fn().mockResolvedValue({
      day: "2026-08-04",
      expenses: [],
      total: 0,
      by_category: {},
    }),
    getExpenseCategories: vi.fn().mockResolvedValue({
      categories: ["Boshqa"],
      defaults: ["Boshqa"],
    }),
    createExpenseCategory: vi.fn(),
    createExpense: vi.fn(),
    deleteExpense: vi.fn(),
    switchCabinet: vi.fn(),
    logout: vi.fn(),
  };
}

async function openEditor(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole(
    "button",
    { name: /Profil \/ Mening sahifam/ },
  ));
  return screen.findByRole("heading", { name: "Profil / Mening sahifam" });
}


describe("v1656 business profile parity", () => {
  it("renders the customer-facing profile editor instead of technical fields", async () => {
    const user = userEvent.setup();
    render(
      <BusinessProfile
        api={api()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await openEditor(user);

    expect(screen.getByText("Muhr").closest("section"))
      .toHaveClass("user-profile-card", "koprik-profile-surface");
    expect(screen.getByRole("button", { name: "Biznes rasmini yuklash" }))
      .toHaveClass("user-avatar-camera");
    expect(screen.getByText("Do'kon havolasi")).toBeInTheDocument();
    expect(screen.getByText(
      "Shu havola yoki QR orqali mijozlar to'g'ridan-to'g'ri do'koningizga o'tadi.",
    )).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nusxa" })).toHaveClass("mini-btn");
    expect(screen.getByText(/3–20 belgi/)).toBeInTheDocument();
    expect(screen.getByLabelText("Faoliyat yo'nalishi")).toHaveValue("Savdo");
    expect(screen.getByLabelText("Faoliyat turi"))
      .toHaveValue("Oziq-ovqat do'koni");
    expect(screen.getByRole("button", { name: /Xaritada joy belgilash/ }))
      .toHaveClass("btn", "btn-outline", "btn-block");
    expect(screen.getByText("✅ Joy belgilangan")).toBeInTheDocument();
    expect(screen.getByText("To'lov ma'lumotlari")).toBeInTheDocument();
    expect(screen.getByText(
      "Onlayn buyurtmada mijoz shu yerga to'laydi va chekni suhbatga tashlaydi. Ixtiyoriy — to'ldirmasangiz onlayn to'lov ko'rsatilmaydi.",
    )).toBeInTheDocument();
    expect(screen.getByLabelText("Ish boshlanish vaqti")).toHaveValue("09:00");
    expect(screen.getByLabelText("Ish tugash vaqti")).toHaveValue("20:00");
    expect(screen.getByRole("button", { name: "Saqlash" }))
      .toHaveClass("btn", "btn-primary", "btn-block");

    expect(screen.queryByLabelText("Manzil")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Kenglik")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Uzunlik")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Ish vaqti (JSON)")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Rahbar")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("STIR")).not.toBeInTheDocument();
  });

  it("saves simple start and finish times without exposing JSON", async () => {
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

    await openEditor(user);
    const start = screen.getByLabelText("Ish boshlanish vaqti");
    const finish = screen.getByLabelText("Ish tugash vaqti");
    await user.clear(start);
    await user.type(start, "08:30");
    await user.clear(finish);
    await user.type(finish, "19:15");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(client.updateBusinessProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        work_hours: expect.objectContaining({
          from: "08:30",
          to: "19:15",
          raw: "08:30–19:15",
        }),
      }),
    );
  });

  it("updates activity choices when the business direction changes", async () => {
    const user = userEvent.setup();
    render(
      <BusinessProfile
        api={api()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await openEditor(user);
    await user.selectOptions(
      screen.getByLabelText("Faoliyat yo'nalishi"),
      "Tibbiy xizmatlar",
    );

    expect(screen.getByRole("option", { name: "Klinika" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Stomatologiya" }))
      .toBeInTheDocument();
  });

  it("shows the exact v1656 validation message for an empty business name", async () => {
    const user = userEvent.setup();
    render(
      <BusinessProfile
        api={api()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await openEditor(user);
    await user.clear(screen.getByLabelText("Biznes nomi"));
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(await screen.findByRole("alert"))
      .toHaveTextContent("Biznes nomini kiriting.");
  });

  it("opens followers and following screens from the profile counters", async () => {
    const user = userEvent.setup();
    render(
      <BusinessProfile
        api={api()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await openEditor(user);
    await user.click(screen.getByRole("button", { name: "0 obunachi" }));

    expect(await screen.findByRole("heading", { name: "Obunachilar" }))
      .toBeInTheDocument();
  });

  it("opens live staff management instead of the legacy read-only payload", async () => {
    const user = userEvent.setup();
    render(
      <BusinessProfile
        api={api()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /Xodimlar/ }));
    expect(await screen.findByRole("heading", { name: "Xodimlar" }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Xodim qo‘shish" }))
      .toBeInTheDocument();
  });

  it("opens the live v1656 expense ledger instead of payload rows", async () => {
    const user = userEvent.setup();
    render(
      <BusinessProfile
        api={api()}
        identity={identity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /Xarajatlar/ }));
    expect(await screen.findByRole("heading", { name: "Xarajatlar" }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Xarajat yozish" }))
      .toBeInTheDocument();
  });

  it("shows staff only the sections granted by the server session", async () => {
    const staffIdentity = {
      ...identity,
      name: "Ali Valiyev",
      login: "ali01",
      actor_type: "staff" as const,
      staff_id: 11,
      permissions: ["kassa"],
    };
    render(
      <BusinessProfile
        api={api()}
        identity={staffIdentity}
        onLogout={vi.fn()}
        onSwitched={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Ali Valiyev" }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Kassa/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Xarajatlar/ }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Xodimlar/ }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Profil \/ Mening sahifam/ }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Oddiy kabinetga qaytish/ }))
      .not.toBeInTheDocument();
  });
});
