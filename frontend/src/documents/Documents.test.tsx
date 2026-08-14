import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BusinessDocument, BusinessProfile } from "../api/types";
import { Documents, type DocumentsApi } from "./Documents";


const profile: BusinessProfile = {
  account_id: 7,
  name: "Turon Savdo",
  phone: "",
  description: "",
  public_username: "turon",
  direction: "Savdo",
  activity_type: "Do'kon",
  address: "Qumqo'rg'on",
  latitude: null,
  longitude: null,
  work_hours: {},
  pay_card: "",
  pay_holder: "",
  pay_qr_object_key: "",
  pay_qr_url: "",
  director: "Ali Valiyev",
  tax_id: "309111222",
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
  dashboard_snapshot: {
    revenue: 0,
    new_orders: 0,
    debt_total: 0,
    low_stock: 0,
    active_orders: 0,
  },
  recent_activity: [],
  cabinet_payload: {},
};

const outgoing: BusinessDocument = {
  id: 31,
  direction: "chiquvchi",
  doc_type: "Shartnoma",
  title: "Yetkazib berish",
  number: "7",
  doc_date: "2026-08-10",
  contractor_id: 9,
  contractor_name: "Olma Savdo",
  body: "Shartnoma matni",
  sender_name: "",
  receiver_inn: "",
  status: "",
  created_at: "2026-08-10T09:00:00Z",
};

const incoming: BusinessDocument = {
  ...outgoing,
  id: 32,
  direction: "kiruvchi",
  contractor_id: null,
  contractor_name: "",
  sender_name: "Olma Savdo",
  receiver_inn: "309111222",
  status: "kutilmoqda",
};

function documentsApi(): DocumentsApi {
  return {
    getDocumentCounterparties: vi.fn().mockResolvedValue({
      counterparties: [{
        id: 9,
        name: "Olma Savdo",
        ctype: "Mijoz",
        director: "",
        phone: "",
        address: "",
        inn: "309333444",
        account: "",
        bank: "",
        mfo: "",
        note: "",
        created_at: "2026-08-10T09:00:00Z",
      }],
      count: 1,
      types: ["Yetkazib beruvchi", "Mijoz", "Hamkor", "Boshqa"],
    }),
    createDocumentCounterparty: vi.fn().mockResolvedValue({ ok: true, id: 10 }),
    updateDocumentCounterparty: vi.fn().mockResolvedValue({ ok: true }),
    deleteDocumentCounterparty: vi.fn().mockResolvedValue(undefined),
    getDocuments: vi.fn().mockImplementation((direction) => Promise.resolve({
      documents: direction === "kiruvchi" ? [incoming] : [outgoing],
      count: 1,
    })),
    getDocument: vi.fn().mockImplementation((id) => Promise.resolve(
      id === incoming.id ? incoming : outgoing,
    )),
    createDocument: vi.fn().mockResolvedValue({ ok: true, id: 40 }),
    updateDocument: vi.fn().mockResolvedValue({ ok: true }),
    deleteDocument: vi.fn().mockResolvedValue(undefined),
    sendDocument: vi.fn().mockResolvedValue({
      ok: true,
      receiver_name: "Olma Savdo",
    }),
    respondDocument: vi.fn().mockResolvedValue({
      ok: true,
      status: "qabul qilindi",
    }),
    updateBusinessProfile: vi.fn().mockResolvedValue(profile),
  };
}

beforeEach(() => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("Documents", () => {
  it("does not add an AI draft control that modular did not render", async () => {
    const user = userEvent.setup();
    const api = {
      ...documentsApi(),
      generateAIDocumentDraft: vi.fn(),
    };
    render(
      <Documents
        api={api}
        profile={profile}
        initialView="center"
        canManageCounterparties
        onProfile={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /Chiquvchi/ }));
    await user.click(await screen.findByRole("button", { name: /Shartnoma/ }));
    expect(screen.queryByText("AI uchun topshiriq")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "🤖 AI draft yaratish" })).not.toBeInTheDocument();
  });

  it("saves the monolith My Documents director and STIR fields", async () => {
    const user = userEvent.setup();
    const api = documentsApi();
    render(
      <Documents
        api={api}
        profile={profile}
        initialView="profile"
        canManageCounterparties
        onProfile={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await user.clear(screen.getByLabelText("Rahbar F.I.Sh."));
    await user.type(screen.getByLabelText("Rahbar F.I.Sh."), "Vali Karimov");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(api.updateBusinessProfile).toHaveBeenCalledWith({
      director: "Vali Karimov",
      tax_id: "309111222",
    });
    expect(await screen.findByText(/ma'lumotlari saqlandi/)).toBeInTheDocument();
  });

  it("sends an outgoing document by STIR and shows the sent result", async () => {
    const user = userEvent.setup();
    const api = documentsApi();
    render(
      <Documents
        api={api}
        profile={profile}
        initialView="center"
        canManageCounterparties
        onProfile={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Chiquvchi/ }));
    await user.click(await screen.findByRole("button", { name: /Shartnoma/ }));
    await user.type(await screen.findByLabelText("Qabul qiluvchi STIR"), "309333444");
    await user.click(screen.getByRole("button", { name: "Yuborish" }));

    expect(api.sendDocument).toHaveBeenCalledWith(31, "309333444");
    expect(await screen.findByText(/Yuborildi/)).toBeInTheDocument();
    await waitFor(() => expect(api.getDocuments).toHaveBeenLastCalledWith("chiquvchi"));
  });

  it("keeps incoming text read-only and accepts the pending document", async () => {
    const user = userEvent.setup();
    const api = documentsApi();
    render(
      <Documents
        api={api}
        profile={profile}
        initialView="center"
        canManageCounterparties
        onProfile={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Kiruvchi/ }));
    await user.click(await screen.findByRole("button", { name: /Shartnoma/ }));

    expect(await screen.findByLabelText("Hujjat matni")).toHaveAttribute("readonly");
    await user.click(screen.getByRole("button", { name: /Qabul qilish/ }));
    expect(api.respondDocument).toHaveBeenCalledWith(32, "qabul");
    expect(await screen.findByText("Qabul qilindi ✅")).toBeInTheDocument();
    await waitFor(() => expect(api.getDocuments).toHaveBeenLastCalledWith("kiruvchi"));
  });
});
