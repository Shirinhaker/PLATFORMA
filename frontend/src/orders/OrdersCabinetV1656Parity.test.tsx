import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { OrderChatRead, OrderRead } from "../api/types";
import { OrdersCabinetV1656, type OrdersApi } from "./OrdersCabinetV1656";


const leaflet = vi.hoisted(() => {
  const map = {
    invalidateSize: vi.fn(),
    remove: vi.fn(),
    setView: vi.fn(),
  };
  map.setView.mockReturnValue(map);
  return {
    map,
    mapFactory: vi.fn(() => map),
    tileLayer: { addTo: vi.fn() },
    marker: { addTo: vi.fn() },
  };
});

vi.mock("leaflet", () => ({
  default: {
    map: leaflet.mapFactory,
    tileLayer: vi.fn(() => leaflet.tileLayer),
    marker: vi.fn(() => leaflet.marker),
  },
}));


function order(overrides: Partial<OrderRead> = {}): OrderRead {
  return {
    id: 91,
    view: "customer",
    title: "Buyurtma: Turon savdo",
    customer_name: "Ali",
    customer_public_id: "u_ali",
    provider_name: "Turon savdo",
    provider_kind: "business",
    provider_public_id: "b_turon",
    item_public_id: "p_non",
    listing_public_id: "",
    order_type: "delivery",
    order_category: "product",
    address: "Qumqo‘rg‘on, Bog‘aro",
    desired_time: "bugun 18:00",
    delivery_lat: 37.834,
    delivery_lng: 67.585,
    note: "Qo‘ng‘iroq qiling",
    phone: "+998901234567",
    qty: 2,
    total_amount: 40_000,
    total_text: "40 000 so‘m",
    status: "accepted",
    payment_status: "pending",
    pay_type: "card",
    debtor_id: null,
    receipt_message_id: null,
    problem_open: false,
    problem_reason: "",
    problem_note: "",
    problem_solution: "",
    problem_opened_at: null,
    problem_resolved_at: null,
    seller_completed_at: null,
    customer_received_at: null,
    last_event: "created",
    chat_count: 1,
    last_chat: "Chek yuborildi",
    last_chat_at: "2026-08-02T09:30:00Z",
    pay_card: "8600123412341234",
    pay_holder: "TURON SAVDO",
    pay_qr_url: "",
    provider_address: "Qumqo‘rg‘on markazi",
    provider_phone: "+998907654321",
    provider_work_hours: {},
    provider_lat: 37.83,
    provider_lng: 67.58,
    customer_seen_at: null,
    provider_seen_at: null,
    seen_at: null,
    is_unread: true,
    created_at: "2026-08-02T09:00:00Z",
    updated_at: "2026-08-02T09:00:00Z",
    items: [{
      id: 1,
      public_id: "p_non",
      name: "Non",
      price: "20 000 so‘m",
      qty: 2,
      unit: "dona",
      line_total: 40_000,
      note: "",
      kind: "product",
    }],
    ...overrides,
  };
}

function chat(value = order()): OrderChatRead {
  return {
    ok: true,
    side: value.view,
    seen_at: "2026-08-02T10:00:00Z",
    other: {
      side: value.view === "customer" ? "provider" : "customer",
      kind: value.view === "customer" ? "business" : "user",
      public_id: value.view === "customer" ? value.provider_public_id : value.customer_public_id,
      name: value.view === "customer" ? value.provider_name : value.customer_name,
    },
    order: value,
    messages: [{
      id: 7,
      text: "Chek yuborildi",
      media_type: "text",
      media_url: "",
      file_name: "",
      reply_to_id: null,
      reply: null,
      edited_at: null,
      deleted_at: null,
      is_deleted: false,
      mine: true,
      sender_name: "Ali",
      sender_kind: "user",
      created_at: "2026-08-02T09:30:00Z",
    }],
  };
}

function apiFor(rows: OrderRead[]): OrdersApi {
  const baseMessage = chat(rows[0] ?? order()).messages[0]!;
  return {
    getMyOrders: vi.fn().mockResolvedValue(rows),
    getOrderInbox: vi.fn().mockResolvedValue(rows),
    markOrderSeen: vi.fn(async (id) => ({ ...rows.find((row) => row.id === id)!, is_unread: false })),
    changeOrderStatus: vi.fn(async (id, status) => ({ ...rows.find((row) => row.id === id)!, status })),
    submitOrderPayment: vi.fn(async (id) => ({ ...rows.find((row) => row.id === id)!, payment_status: "submitted" })),
    decideOrderPayment: vi.fn(async (id, status) => ({ ...rows.find((row) => row.id === id)!, payment_status: status })),
    openOrderProblem: vi.fn(async (id, body) => ({ ...rows.find((row) => row.id === id)!, problem_open: true, problem_reason: body.reason })),
    chooseOrderProblemSolution: vi.fn(async (id, solution) => ({ ...rows.find((row) => row.id === id)!, problem_solution: solution })),
    handoffOrder: vi.fn(async (id) => ({ ...rows.find((row) => row.id === id)!, status: "pickup_waiting_customer" })),
    receiveOrder: vi.fn(async (id) => ({ ...rows.find((row) => row.id === id)!, status: "done" })),
    getOrderChat: vi.fn(async (id) => chat(rows.find((row) => row.id === id)!)),
    sendOrderChatMessage: vi.fn(async (_id, body) => ({ ...baseMessage, id: 8, text: body.text })),
    sendOrderChatImage: vi.fn(async () => ({ ...baseMessage, id: 9, media_type: "photo" })),
    editOrderChatMessage: vi.fn(async (_orderId, messageId, text) => ({ ...baseMessage, id: messageId, text })),
    deleteOrderChatMessage: vi.fn(async (_orderId, messageId) => ({ ...baseMessage, id: messageId, is_deleted: true })),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    getDebtors: vi.fn().mockResolvedValue([{
      id: 31,
      name: "Ali Valiyev",
      phone: "",
      note: "",
      due: "",
      balance: 0,
    }]),
    createDebtor: vi.fn().mockResolvedValue({ id: 31 }),
  };
}


beforeEach(() => vi.clearAllMocks());


describe("v1656 jonli buyurtma kabineti", () => {
  it("mijoz mahsulot buyurtmalarini API dan olib, xizmatlarni alohida saqlaydi", async () => {
    const product = order();
    const service = order({ id: 92, order_type: "delivery", order_category: "service", title: "Stomatolog" });
    const api = apiFor([product, service]);

    const { rerender } = render(
      <OrdersCabinetV1656 api={api} side="customer" category="product" onBack={vi.fn()} />,
    );
    expect(await screen.findByText("Buyurtma: Turon savdo")).toBeInTheDocument();
    expect(screen.queryByText("Stomatolog")).not.toBeInTheDocument();
    expect(api.getMyOrders).toHaveBeenCalledOnce();

    rerender(<OrdersCabinetV1656 api={api} side="customer" category="service" onBack={vi.fn()} />);
    expect(await screen.findByText("Stomatolog")).toBeInTheDocument();
  });

  it("detailni ochganda o‘qilgan qiladi va chek, xarita, to‘lov hamda chatni ko‘rsatadi", async () => {
    const user = userEvent.setup();
    const clipboardWrite = vi.spyOn(navigator.clipboard, "writeText");
    const current = order({ last_event: "msg" });
    const api = apiFor([current]);
    render(<OrdersCabinetV1656 api={api} side="customer" category="product" onBack={vi.fn()} />);

    expect(await screen.findByText("BUYURTMA №91")).toBeInTheDocument();
    expect(screen.getByText("💬 Xabar keldi")).toBeInTheDocument();
    expect(screen.getByText("💬 Chek yuborildi")).toBeInTheDocument();
    expect(screen.getByText("Non × 2 dona")).toBeInTheDocument();
    await user.click(await screen.findByText("Buyurtma: Turon savdo"));
    await waitFor(() => expect(api.markOrderSeen).toHaveBeenCalledWith(91));
    expect(screen.getByRole("heading", { name: "Mening buyurtmam №91" })).toBeInTheDocument();
    expect(screen.getByText("🧾 Buyurtma cheki №91")).toBeInTheDocument();
    expect(screen.getByText("Yetkazib berish metkasi")).toBeInTheDocument();
    expect(screen.getByText("💬 Buyurtma chati")).toBeInTheDocument();
    await waitFor(() => expect(leaflet.map.setView).toHaveBeenCalledWith([37.834, 67.585], 16));

    await user.click(screen.getByRole("button", { name: "📋 Summani nusxalash" }));
    expect(clipboardWrite).toHaveBeenCalledWith("40000");
    expect(screen.getByRole("alert")).toHaveTextContent("Nusxa olindi ✅");

    await user.type(screen.getByPlaceholderText("Buyurtma bo‘yicha xabar yozing..."), "Qachon tayyor?");
    await user.click(screen.getByRole("button", { name: "Yuborish" }));
    expect(api.sendOrderChatMessage).toHaveBeenCalledWith(91, {
      text: "Qachon tayyor?",
      reply_to_id: null,
    });

    await user.click(screen.getByRole("button", { name: "✅ To'lov qildim" }));
    expect(api.submitOrderPayment).toHaveBeenCalledWith(91);
  });

  it("javob preview'i va chat rasmini v1656 ichki viewerida ko‘rsatadi", async () => {
    const user = userEvent.setup();
    const current = order();
    const api = apiFor([current]);
    vi.mocked(api.getOrderChat).mockResolvedValue({
      ...chat(current),
      messages: [{
        ...chat(current).messages[0]!,
        id: 8,
        text: "Mana yangi chek",
        media_type: "photo",
        media_url: "https://cdn.example/receipt.webp",
        reply_to_id: 7,
        reply: {
          id: 7,
          text: "Kvitansiyani yuboring",
          media_type: "text",
          is_deleted: false,
          sender_name: "Turon savdo",
        },
      }],
    });

    render(<OrdersCabinetV1656 api={api} side="customer" category="product" onBack={vi.fn()} />);
    await user.click(await screen.findByText("Buyurtma: Turon savdo"));
    expect(await screen.findByText("Kvitansiyani yuboring")).toBeInTheDocument();
    expect(screen.getByText("↩ Turon savdo")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Rasm" }));
    expect(screen.getByRole("dialog", { name: "Buyurtma chati rasmi" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Rasmni yopish" }));
    expect(screen.queryByRole("dialog", { name: "Buyurtma chati rasmi" })).not.toBeInTheDocument();
  });

  it("rasmli chekni grant bilan yuklaydi va chat reply/edit/delete amallarini saqlaydi", async () => {
    const user = userEvent.setup();
    const current = order();
    const api = apiFor([current]);
    vi.mocked(api.createUploadGrant).mockResolvedValue({
      object_key: "private/user/5/order_chat_image/receipt.webp",
      upload_url: "https://upload.example/receipt",
      method: "PUT",
      headers: { "Content-Type": "image/webp" },
      expires_in_seconds: 300,
    });
    render(<OrdersCabinetV1656 api={api} side="customer" category="product" onBack={vi.fn()} />);
    await user.click(await screen.findByText("Buyurtma: Turon savdo"));
    await screen.findByText("Chek yuborildi");

    const image = new File(["receipt"], "receipt.webp", { type: "image/webp" });
    await user.upload(screen.getByLabelText("📎 Rasm qo‘shish"), image);
    expect(screen.getByText("Rasm tanlandi. Yuborish uchun chatdagi “Yuborish” tugmasini bosing.")).toBeInTheDocument();
    expect(api.createUploadGrant).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Yuborish" }));
    await waitFor(() => expect(api.createUploadGrant).toHaveBeenCalledWith({
      purpose: "order_chat_image",
      filename: "receipt.webp",
      content_type: "image/webp",
      size_bytes: image.size,
    }));
    expect(api.uploadGrantedFile).toHaveBeenCalledWith(
      expect.objectContaining({ object_key: "private/user/5/order_chat_image/receipt.webp" }),
      image,
    );
    expect(api.sendOrderChatImage).toHaveBeenCalledWith(91, expect.objectContaining({
      object_key: "private/user/5/order_chat_image/receipt.webp",
      file_name: "receipt.webp",
    }));

    await user.click(screen.getAllByRole("button", { name: "Xabar amallari" })[0]!);
    await user.click(screen.getByRole("button", { name: "↩️ Javob berish" }));
    await user.type(screen.getByPlaceholderText("Buyurtma bo‘yicha xabar yozing..."), "Qabul qilindi");
    await user.click(screen.getByRole("button", { name: "Yuborish" }));
    expect(api.sendOrderChatMessage).toHaveBeenCalledWith(91, {
      text: "Qabul qilindi",
      reply_to_id: 7,
    });

    await user.click(screen.getAllByRole("button", { name: "Xabar amallari" })[0]!);
    await user.click(screen.getByRole("button", { name: "✏️ Tahrirlash" }));
    const composer = screen.getByPlaceholderText("Buyurtma bo‘yicha xabar yozing...");
    await user.clear(composer);
    await user.type(composer, "Chek yangilandi");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(api.editOrderChatMessage).toHaveBeenCalledWith(91, 7, "Chek yangilandi");

    await user.click(screen.getAllByRole("button", { name: "Xabar amallari" })[0]!);
    await user.click(screen.getByRole("button", { name: "🗑 O‘chirish" }));
    const dialog = screen.getByRole("dialog", { name: "Xabarni o‘chirish" });
    await user.click(within(dialog).getByRole("button", { name: "O‘chirish" }));
    expect(api.deleteOrderChatMessage).toHaveBeenCalledWith(91, 7);
  });

  it("pickup tayyor buyurtmani tasdiqdan keyin mijozga topshiradi", async () => {
    const user = userEvent.setup();
    const ready = order({ view: "provider", order_type: "pickup", status: "tayyor" });
    const api = apiFor([ready]);
    render(<OrdersCabinetV1656 api={api} side="provider" category="product" onBack={vi.fn()} />);
    await user.click(await screen.findByText("Buyurtma: Turon savdo"));
    await user.click(screen.getByRole("button", { name: "🏪 Buyurtmachiga topshirdim" }));
    const dialog = screen.getByRole("dialog", { name: "Buyurtmani topshirish" });
    expect(dialog).toHaveTextContent("Buyurtma qarshi tomonga topshirildimi?");
    await user.click(within(dialog).getByRole("button", { name: "Ha, topshirdim" }));
    expect(api.handoffOrder).toHaveBeenCalledWith(91);
  });

  it("delivery kuryeri kelganda buyurtmani tasdiqdan keyin unga topshiradi", async () => {
    const user = userEvent.setup();
    const waiting = order({
      view: "provider",
      order_type: "delivery",
      status: "handoff_waiting_seller",
    });
    const api = apiFor([waiting]);
    render(<OrdersCabinetV1656 api={api} side="provider" category="product" onBack={vi.fn()} />);
    await user.click(await screen.findByText("Buyurtma: Turon savdo"));
    await user.click(screen.getByRole("button", { name: "📦 Dostavkachiga topshirdim" }));
    const dialog = screen.getByRole("dialog", { name: "Buyurtmani topshirish" });
    await user.click(within(dialog).getByRole("button", { name: "Ha, topshirdim" }));
    expect(api.handoffOrder).toHaveBeenCalledWith(91);
  });

  it("biznes to‘lovni v1656 tasdiqlash oynasidan keyin tasdiqlaydi", async () => {
    const user = userEvent.setup();
    const submitted = order({ view: "provider", payment_status: "submitted" });
    const api = apiFor([submitted]);
    render(<OrdersCabinetV1656 api={api} side="provider" category="product" onBack={vi.fn()} />);
    await user.click(await screen.findByText("Buyurtma: Turon savdo"));
    expect(screen.getByText("Mijoz chek (to'lov skrinshoti)ni suhbatga tashlaydi. Tekshirib tasdiqlang.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "✅ To'lovni tasdiqlash" }));
    const dialog = screen.getByRole("dialog", { name: "To'lovni tasdiqlash" });
    expect(dialog).toHaveTextContent("To'lovni tasdiqlashni tasdiqlaysizmi?");
    await user.click(within(dialog).getByRole("button", { name: "Tasdiqlash" }));
    expect(api.decideOrderPayment).toHaveBeenCalledWith(91, "confirmed");
  });

  it("biznes qabul qilingan buyurtmani tanlangan mijoz qarziga yozadi", async () => {
    const user = userEvent.setup();
    const accepted = order({ view: "provider", status: "accepted" });
    const api = apiFor([accepted]);
    render(<OrdersCabinetV1656 api={api} side="provider" category="product" onBack={vi.fn()} />);

    await user.click(await screen.findByText("Buyurtma: Turon savdo"));
    await user.click(screen.getByRole("button", { name: "📒 Qarzga rasmiylashtirish" }));
    const dialog = await screen.findByRole("dialog", { name: "Tashqi buyurtmani qarzga yozish" });
    await user.selectOptions(within(dialog).getByLabelText("Qarzdor"), "31");
    await user.click(within(dialog).getByRole("button", { name: "Qarzga yozish" }));

    await waitFor(() => expect(api.decideOrderPayment).toHaveBeenCalledWith(91, "debt", 31));
  });

  it("biznes qabul qilish, muammo ochish va topshirishni jonli endpointlarga yuboradi", async () => {
    const user = userEvent.setup();
    const fresh = order({ view: "provider", status: "new", pay_card: "", is_unread: true });
    const api = apiFor([fresh]);
    const first = render(<OrdersCabinetV1656 api={api} side="provider" category="product" onBack={vi.fn()} />);
    await user.click(await screen.findByText("Buyurtma: Turon savdo"));

    await user.click(screen.getByRole("button", { name: "Qabul qilish" }));
    expect(api.changeOrderStatus).toHaveBeenCalledWith(91, "accepted");
    first.unmount();

    const submitted = order({ view: "provider", payment_status: "submitted" });
    const submittedApi = apiFor([submitted]);
    render(<OrdersCabinetV1656 api={submittedApi} side="provider" category="product" onBack={vi.fn()} />);
    await user.click(await screen.findByText("Buyurtma: Turon savdo"));
    await user.click(screen.getByRole("button", { name: "⚠️ To'lov bo'yicha muammo" }));
    const dialog = screen.getByRole("dialog", { name: "To'lov bo'yicha muammo" });
    expect(dialog).toHaveTextContent("Sababni tanlang. Muammo hal bo'lmaguncha tayyorlash, dostavka va yakunlash bloklanadi.");
    await user.selectOptions(within(dialog).getByLabelText("Muammo sababi"), "amount_short");
    await user.click(within(dialog).getByRole("button", { name: "Muammoli buyurtmaga o'tkazish" }));
    expect(submittedApi.openOrderProblem).toHaveBeenCalledWith(91, {
      reason: "amount_short",
      note: "",
    });
  });

  it("biznes yangi buyurtmani kartochkaning o‘zidan qabul qiladi", async () => {
    const user = userEvent.setup();
    const fresh = order({ view: "provider", status: "new", pay_card: "", is_unread: true });
    const api = apiFor([fresh]);
    render(<OrdersCabinetV1656 api={api} side="provider" category="product" onBack={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "Qabul qilish" }));

    expect(api.changeOrderStatus).toHaveBeenCalledWith(91, "accepted");
    expect(api.getOrderChat).not.toHaveBeenCalled();
  });

  it("mijoz muammo yechimini va qabul qilinganini tasdiqlaydi", async () => {
    const user = userEvent.setup();
    const problematic = order({
      status: "pickup_waiting_customer",
      problem_open: true,
      problem_reason: "other",
      problem_solution: "pickup",
      provider_work_hours: { raw: "08:00–18:00" },
    });
    const api = apiFor([problematic]);
    const first = render(<OrdersCabinetV1656 api={api} side="customer" category="product" onBack={vi.fn()} />);
    await user.click(await screen.findByText("Buyurtma: Turon savdo"));
    expect(screen.getByText("Boshqa to'lov muammosi")).toBeInTheDocument();
    expect(screen.getByText(/08:00–18:00/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "🧾 Yangi chek" }));
    expect(api.chooseOrderProblemSolution).toHaveBeenCalledWith(91, "new_receipt");
    expect(screen.queryByRole("button", { name: "✅ Buyurtmani qabul qildim" })).not.toBeInTheDocument();
    first.unmount();

    const delivered = order({
      status: "delivered_waiting_customer",
      problem_open: false,
    });
    const deliveredApi = apiFor([delivered]);
    render(<OrdersCabinetV1656 api={deliveredApi} side="customer" category="product" onBack={vi.fn()} />);
    await user.click(await screen.findByText("Buyurtma: Turon savdo"));
    await user.click(screen.getByRole("button", { name: "✅ Buyurtmani qabul qildim" }));
    const confirm = screen.getByRole("dialog", { name: "Buyurtmani qabul qilish" });
    await user.click(within(confirm).getByRole("button", { name: "Ha, qabul qildim" }));
    expect(deliveredApi.receiveOrder).toHaveBeenCalledWith(91);
  });
});
