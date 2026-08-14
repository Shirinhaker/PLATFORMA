import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";

import type { ApiClient } from "../api/client";
import type {
  OrderMessageRead,
  OrderProblemReason,
  OrderProblemSolution,
  OrderRead,
  OrderStatus,
} from "../api/types";
import { DebtorPickerV1656 } from "../profiles/DebtorPickerV1656";
import "./OrdersV1656.css";


export type OrdersApi = Pick<
  ApiClient,
  | "getMyOrders"
  | "getOrderInbox"
  | "markOrderSeen"
  | "changeOrderStatus"
  | "submitOrderPayment"
  | "decideOrderPayment"
  | "openOrderProblem"
  | "chooseOrderProblemSolution"
  | "handoffOrder"
  | "receiveOrder"
  | "getOrderChat"
  | "sendOrderChatMessage"
  | "sendOrderChatImage"
  | "editOrderChatMessage"
  | "deleteOrderChatMessage"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "getDebtors"
  | "createDebtor"
>;

type Props = {
  api: OrdersApi;
  side: "customer" | "provider";
  category: "product" | "service";
  onBack(): void;
  onUnreadChange?(count: number): void;
  initialOrderId?: number | null;
  beforeList?: ReactNode;
};

type Tab = "active" | "problem" | "done";
type Confirmation = (
  "handoff" | "received" | "delete-message" | "payment-confirm" | null
);

const ACTIVE = new Set([
  "new", "accepted", "preparing", "tayyor", "courier_assigned",
  "courier_arrived_store", "handoff_waiting_seller", "in_delivery",
  "courier_arrived_customer", "delivered_waiting_customer",
  "pickup_waiting_customer",
]);
const PROBLEM_REASONS: ReadonlyArray<readonly [OrderProblemReason, string]> = [
  ["not_received", "Pul hisobga tushmadi"],
  ["amount_short", "To'langan summa kam"],
  ["receipt_mismatch", "Chek ma'lumoti mos kelmadi"],
  ["receipt_unreadable", "Chek rasmi o'qilmaydi"],
  ["wrong_receipt", "Noto'g'ri chek yuborilgan"],
  ["other", "Boshqa muammo"],
];

function problemReasonText(reason: string) {
  if (reason === "other") return "Boshqa to'lov muammosi";
  return PROBLEM_REASONS.find(([key]) => key === reason)?.[1] ?? reason;
}

function workHoursText(value: Record<string, unknown>) {
  const raw = String(value.raw ?? value.text ?? "").trim();
  if (raw) return raw;
  const from = String(value.from ?? value.start ?? value.open ?? "").trim();
  const to = String(value.to ?? value.end ?? value.close ?? "").trim();
  return from && to ? `${from}–${to}` : "";
}

function isMessageEvent(value: string) {
  return value === "msg" || value.includes("message");
}

function errorText(reason: unknown) {
  return reason instanceof Error ? reason.message : "Amal bajarilmadi.";
}

function isService(order: OrderRead) {
  return order.order_category === "service"
    || ["booking", "service", "queue", "medical"].includes(order.order_type);
}

function isActive(order: OrderRead) {
  return !order.problem_open && ACTIVE.has(order.status);
}

function statusText(status: string) {
  return ({
    new: "Yangi",
    accepted: "To'lov kutilmoqda",
    preparing: "Tayyorlanmoqda",
    rejected: "Rad etildi",
    done: "Yakunlandi",
    cancelled: "Bekor qilindi",
    tayyor: "Tayyor",
    courier_assigned: "Dostavkachi biriktirildi",
    courier_arrived_store: "Dostavkachi sotuvchiga yetib keldi",
    handoff_waiting_seller: "Topshirish tasdig'i kutilmoqda",
    in_delivery: "Yo'lda",
    courier_arrived_customer: "Dostavkachi yetib keldi",
    delivered_waiting_customer: "Qabul tasdig'i kutilmoqda",
    pickup_waiting_customer: "Qabul tasdig'i kutilmoqda",
  } as Record<string, string>)[status] ?? status ?? "—";
}

function typeText(type: string) {
  return ({
    delivery: "Yetkazib berish",
    pickup: "Olib ketish",
    booking: "Navbat/qabul",
  } as Record<string, string>)[type] ?? type ?? "—";
}

function createdText(value: string) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "—";
  return `${date.toLocaleDateString("uz-UZ", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })} · ${date.toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" })}`;
}

function qtyText(qty: number, unit: string) {
  return `${Number.isInteger(qty) ? qty : qty.toLocaleString("uz-UZ")} ${unit || "dona"}`;
}

function paymentText(status: string) {
  return ({
    confirmed: "To'lov tasdiqlandi",
    rejected: "To'lov rad etildi",
    submitted: "To'lov tekshirilmoqda",
    recheck: "To'lov aniqlashtirilmoqda",
    disputed: "To'lov aniqlashtirilmoqda",
    pending: "To'lov kutilmoqda",
  } as Record<string, string>)[status] ?? "To'lov kutilmoqda";
}

function messagePreview(message: Pick<OrderMessageRead, "is_deleted" | "media_type" | "text">) {
  if (message.is_deleted) return "Xabar o‘chirildi";
  const text = message.text.trim();
  const value = message.media_type === "photo"
    ? `📷 Rasm${text ? `: ${text}` : ""}`
    : text || "Xabar";
  return value.length > 70 ? `${value.slice(0, 70)}…` : value;
}

function OrderLocationMap({ latitude, longitude }: { latitude: number; longitude: number }) {
  const node = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!node.current) return undefined;
    let disposed = false;
    let map: LeafletMap | null = null;
    void import("leaflet").then(({ default: leaflet }) => {
      if (disposed || !node.current) return;
      map = leaflet.map(node.current, { attributionControl: false })
        .setView([latitude, longitude], 16);
      leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
      }).addTo(map);
      leaflet.marker([latitude, longitude]).addTo(map);
      window.setTimeout(() => map?.invalidateSize(), 240);
    }).catch(() => undefined);
    return () => {
      disposed = true;
      map?.remove();
    };
  }, [latitude, longitude]);

  return (
    <div className="order-detail-map" ref={node} />
  );
}

function ConfirmDialog({
  kind,
  onCancel,
  onConfirm,
}: {
  kind: Exclude<Confirmation, null>;
  onCancel(): void;
  onConfirm(): void;
}) {
  const received = kind === "received";
  const deleting = kind === "delete-message";
  const payment = kind === "payment-confirm";
  return (
    <div className="order-confirm-backdrop">
      <section
        aria-label={payment ? "To'lovni tasdiqlash" : received
          ? "Buyurtmani qabul qilish"
          : deleting ? "Xabarni o‘chirish" : "Buyurtmani topshirish"}
        aria-modal="true"
        className="order-confirm"
        role="dialog"
      >
        <b>{payment
          ? "To'lovni tasdiqlashni tasdiqlaysizmi?"
          : deleting
          ? "Bu xabar o‘chirilsinmi?"
          : received
            ? "Buyurtmani to'liq qabul qildingizmi?"
            : "Buyurtma qarshi tomonga topshirildimi?"}</b>
        <div className="order-confirm-actions">
          <button type="button" className="mini-btn" onClick={onCancel}>Bekor qilish</button>
          <button type="button" className={deleting ? "mini-btn danger" : "mini-btn ok"} onClick={onConfirm}>
            {payment ? "Tasdiqlash" : deleting ? "O‘chirish" : received ? "Ha, qabul qildim" : "Ha, topshirdim"}
          </button>
        </div>
      </section>
    </div>
  );
}

export function OrdersCabinetV1656({
  api,
  side,
  category,
  onBack,
  onUnreadChange,
  initialOrderId = null,
  beforeList,
}: Props) {
  const [orders, setOrders] = useState<OrderRead[]>([]);
  const [tab, setTab] = useState<Tab>("active");
  const [selected, setSelected] = useState<OrderRead | null>(null);
  const [messages, setMessages] = useState<OrderMessageRead[]>([]);
  const [text, setText] = useState("");
  const [replyTo, setReplyTo] = useState<OrderMessageRead | null>(null);
  const [editing, setEditing] = useState<OrderMessageRead | null>(null);
  const [messageMenu, setMessageMenu] = useState<OrderMessageRead | null>(null);
  const [photoUrl, setPhotoUrl] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<OrderMessageRead | null>(null);
  const [confirmation, setConfirmation] = useState<Confirmation>(null);
  const [problemOpen, setProblemOpen] = useState(false);
  const [problemReason, setProblemReason] = useState<OrderProblemReason>("not_received");
  const [problemNote, setProblemNote] = useState("");
  const [debtPickerOpen, setDebtPickerOpen] = useState(false);
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  const [pendingImageUrl, setPendingImageUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const chatFileRef = useRef<HTMLInputElement | null>(null);
  const initialHandledRef = useRef(false);
  const unreadChangeRef = useRef(onUnreadChange);

  useEffect(() => {
    unreadChangeRef.current = onUnreadChange;
  }, [onUnreadChange]);

  useEffect(() => {
    if (!messageMenu && !photoUrl) return undefined;
    function closeOverlay(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setMessageMenu(null);
      setPhotoUrl("");
    }
    function closeMenu(event: MouseEvent) {
      if (!messageMenu || !(event.target instanceof Element)) return;
      if (event.target.closest(".order-chat-action-menu, .order-msg-menu-btn")) return;
      setMessageMenu(null);
    }
    document.addEventListener("keydown", closeOverlay);
    document.addEventListener("click", closeMenu);
    return () => {
      document.removeEventListener("keydown", closeOverlay);
      document.removeEventListener("click", closeMenu);
    };
  }, [messageMenu, photoUrl]);

  useEffect(() => {
    if (!pendingImage) {
      setPendingImageUrl("");
      return undefined;
    }
    if (typeof URL.createObjectURL !== "function") return undefined;
    const url = URL.createObjectURL(pendingImage);
    setPendingImageUrl(url);
    return () => {
      if (typeof URL.revokeObjectURL === "function") URL.revokeObjectURL(url);
    };
  }, [pendingImage]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const rows = await (side === "customer" ? api.getMyOrders() : api.getOrderInbox());
      setOrders(rows);
      if (!initialHandledRef.current && initialOrderId) {
        initialHandledRef.current = true;
        const target = rows.find((row) => row.id === initialOrderId);
        if (target && isService(target) === (category === "service")) {
          void openDetail(target);
        }
      }
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // API App davomida barqaror, tomon o‘zgarsa qayta yuklanadi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, side]);

  const categoryOrders = useMemo(() => orders.filter(
    (order) => isService(order) === (category === "service"),
  ), [category, orders]);
  const active = categoryOrders.filter(isActive);
  const problem = categoryOrders.filter((order) => order.problem_open);
  const done = categoryOrders.filter((order) => !isActive(order) && !order.problem_open);
  const shown = tab === "active" ? active : tab === "problem" ? problem : done;

  useEffect(() => {
    unreadChangeRef.current?.(
      categoryOrders.filter((order) => order.is_unread).length,
    );
  }, [categoryOrders]);

  useEffect(() => {
    if (loading || shown.length || tab !== "active") return;
    if (problem.length) setTab("problem");
    else if (done.length) setTab("done");
  }, [done.length, loading, problem.length, shown.length, tab]);

  function replaceOrder(next: OrderRead) {
    setOrders((current) => current.map((order) => order.id === next.id ? next : order));
    setSelected((current) => current?.id === next.id ? next : current);
  }

  async function openDetail(order: OrderRead) {
    setSelected({ ...order, is_unread: false });
    setMessages([]);
    setError("");
    try {
      const [seen, chat] = await Promise.all([
        api.markOrderSeen(order.id),
        api.getOrderChat(order.id),
      ]);
      replaceOrder({ ...seen, is_unread: false });
      setMessages(chat.messages);
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  async function mutate(action: () => Promise<OrderRead>): Promise<boolean> {
    setBusy(true);
    setError("");
    try {
      replaceOrder(await action());
      return true;
    } catch (reason) {
      setError(errorText(reason));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(status: OrderStatus) {
    if (!selected) return;
    await mutate(() => api.changeOrderStatus(selected.id, status));
  }

  async function sendMessage() {
    if (!selected) return;
    const clean = text.trim();
    if (editing) {
      if (pendingImage) {
        setError("Tahrirlash paytida rasm yuborilmaydi. Avval tahrirlashni yakunlang yoki X bilan bekor qiling.");
        return;
      }
      if (!clean) return;
      setBusy(true);
      try {
        const next = await api.editOrderChatMessage(selected.id, editing.id, clean);
        setMessages((current) => current.map((message) => message.id === next.id ? next : message));
        setEditing(null);
        setText("");
        await load();
      } catch (reason) {
        setError(errorText(reason));
      } finally {
        setBusy(false);
      }
      return;
    }
    if (pendingImage) {
      await uploadImage(pendingImage, clean);
      return;
    }
    if (!clean) return;
    setBusy(true);
    try {
      const next = await api.sendOrderChatMessage(selected.id, {
        text: clean,
        reply_to_id: replyTo?.id ?? null,
      });
      setMessages((current) => [...current, next]);
      setText("");
      setReplyTo(null);
      await load();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  function chooseImage(file: File) {
    if (!file.type.startsWith("image/")) {
      setError("Faqat rasm tanlang.");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      setError("Rasm hajmi 8 MB dan oshmasin.");
      return;
    }
    setError("");
    setPendingImage(file);
  }

  async function uploadImage(file: File, cleanText: string) {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const grant = await api.createUploadGrant({
        purpose: "order_chat_image",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await api.uploadGrantedFile(grant, file);
      const next = await api.sendOrderChatImage(selected.id, {
        object_key: grant.object_key,
        file_name: file.name,
        text: cleanText,
        reply_to_id: replyTo?.id ?? null,
      });
      setMessages((current) => [...current, next]);
      setText("");
      setReplyTo(null);
      setPendingImage(null);
      if (chatFileRef.current) chatFileRef.current.value = "";
      await load();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function removeMessage() {
    if (!selected || !deleteTarget) return;
    setBusy(true);
    try {
      const next = await api.deleteOrderChatMessage(selected.id, deleteTarget.id);
      setMessages((current) => current.map((message) => message.id === next.id ? next : message));
      setDeleteTarget(null);
      setConfirmation(null);
      await load();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function copyMessage(message: OrderMessageRead) {
    const clean = message.text.trim();
    if (!clean) {
      setError("Nusxalanadigan matn yo‘q.");
      return;
    }
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(clean);
      } else {
        const area = document.createElement("textarea");
        area.value = clean;
        area.style.position = "fixed";
        area.style.left = "-9999px";
        document.body.appendChild(area);
        area.focus();
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      setError("Matn nusxalandi.");
    } catch {
      setError("Nusxalab bo‘lmadi. Matnni qo‘lda belgilang.");
    }
  }

  async function copyPaymentText(value: string) {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(value);
      setError("Nusxa olindi ✅");
    } catch {
      setError("Nusxa olinmadi — havolani qo'lda belgilang");
    }
  }

  if (selected) {
    const otherLabel = side === "provider" ? "Mijoz" : "Qabul qiluvchi";
    const otherName = side === "provider" ? selected.customer_name : selected.provider_name;
    const hasPaymentData = Boolean(selected.pay_card || selected.pay_qr_url);
    const canSubmitPayment = side === "customer"
      && selected.status !== "new"
      && hasPaymentData
      && !["submitted", "recheck", "disputed", "confirmed"].includes(
        selected.payment_status,
      );
    const showStatusActions = !selected.problem_open && (
      side === "provider"
        ? ["new", "accepted", "preparing", "tayyor", "handoff_waiting_seller"].includes(selected.status)
        : [
          "new", "accepted", "preparing", "tayyor",
          "delivered_waiting_customer", "pickup_waiting_customer",
        ].includes(selected.status)
    );
    return (
      <>
      <button type="button" aria-label="Buyurtma tafsilotini yopish" className="order-detail-backdrop on" onClick={() => setSelected(null)} />
      <main className="order-detail-sheet on">
        <button type="button" className="order-close" aria-label="Yopish" onClick={() => setSelected(null)}>×</button>
        <div className="order-grip" />
        <h1 className="lead order-detail-title">{side === "customer" ? "Mening buyurtmam" : "Kelgan buyurtma"} №{selected.id}</h1>
        <div className="lead-sub order-detail-subtitle">{selected.title || "Buyurtma"}</div>
        {error ? <p className="app-toast on" role="alert">{error}</p> : null}

        <section className="panel-card">
          <div className="detail-line"><b>Buyurtma raqami</b><span className="order-no-pill">№{selected.id}</span></div>
          <div className="detail-line"><b>Buyurtma vaqti</b><span>{createdText(selected.created_at)}</span></div>
          <div className="detail-line"><b>Status</b><span>{statusText(selected.status)}</span></div>
          <div className="detail-line"><b>{otherLabel}</b><span>{otherName || "—"}</span></div>
          <div className="detail-line"><b>Turi</b><span>{typeText(selected.order_type)}</span></div>
          {selected.phone ? <div className="detail-line"><b>Telefon</b><span>{selected.phone}</span></div> : null}
          {selected.address ? <div className="detail-line"><b>Manzil</b><span>{selected.address}</span></div> : null}
          {selected.desired_time ? <div className="detail-line"><b>Vaqt</b><span>{selected.desired_time}</span></div> : null}
          {selected.note ? <div className="order-detail-note"><b>Izoh</b><div className="idesc">{selected.note}</div></div> : null}
        </section>

        <section className="panel-card order-receipt-v1656">
          <div className="order-receipt-title">
            <b>🧾 Buyurtma cheki №{selected.id}</b>
            <span>{createdText(selected.created_at)}</span>
          </div>
          {!selected.items.length ? <div className="idesc">Mahsulotlar kiritilmagan.</div> : selected.items.map((item) => (
            <div className="order-receipt-item" key={item.id}>
              <div className="order-receipt-name">{item.name || "Mahsulot"}</div>
              <div className="order-receipt-meta">
                <span>Miqdori</span><b>{qtyText(item.qty, item.unit)}</b>
                <span>Dona narxi</span><b>{item.price || "Narx kelishiladi"}</b>
                <span>Jami</span><b>{item.line_total ? `${item.line_total.toLocaleString("uz-UZ")} so‘m` : "—"}</b>
              </div>
            </div>
          ))}
          {selected.total_text ? <div className="iprice order-receipt-total">Umumiy jami: {selected.total_text}</div> : null}
        </section>

        {selected.delivery_lat != null && selected.delivery_lng != null ? (
          <section className="panel-card">
            <b>Yetkazib berish metkasi</b>
            <OrderLocationMap latitude={selected.delivery_lat} longitude={selected.delivery_lng} />
            <div className="idesc">🗺 {selected.delivery_lat.toFixed(6)}, {selected.delivery_lng.toFixed(6)}</div>
          </section>
        ) : null}

        {selected.status !== "new" && hasPaymentData ? (
          <section className="panel-card order-payment-v1656">
            <b>💳 Onlayn to'lov</b>
            <p>{paymentText(selected.payment_status)}</p>
            {side === "provider" ? <div className="idesc">Mijoz chek (to'lov skrinshoti)ni suhbatga tashlaydi. Tekshirib tasdiqlang.</div> : null}
            {side === "customer" && ["submitted", "recheck", "disputed"].includes(selected.payment_status) ? <div className="idesc">To'lov ma'lumoti sotuvchiga yuborildi. Tekshiruv natijasini kuting.</div> : null}
            {side === "customer" && canSubmitPayment ? <div className="idesc">To'lash uchun: summa va karta raqamini nusxalang, to'lov ilovangizni (Click/Payme/bank) oching va o'tkazing. So'ng kvitansiya (chek) rasmini yuboring.</div> : null}
            {side === "customer" && canSubmitPayment && selected.total_text ? <div className="detail-line"><b>To'lov summasi</b><strong>{selected.total_text}</strong></div> : null}
            {side === "customer" && canSubmitPayment && selected.pay_card ? <div className="detail-line"><b>Karta raqami</b><strong>{selected.pay_card}</strong></div> : null}
            {side === "customer" && canSubmitPayment && selected.pay_holder ? <div className="detail-line"><b>Karta egasi</b><span>{selected.pay_holder}</span></div> : null}
            {side === "customer" && canSubmitPayment && selected.pay_qr_url ? <><div className="idesc order-payment-qr-hint">Yoki QR kodni to'lov ilovangizda skanerlang:</div><img src={selected.pay_qr_url} alt="QR" /></> : null}
            {side === "customer" && selected.payment_status === "confirmed" ? <div className="idesc">To'lovingiz do'kon tomonidan tasdiqlandi. Rahmat!</div> : null}
            <div className="order-action-row">
              {canSubmitPayment && selected.total_text ? <button type="button" className="btn btn-soft btn-block" onClick={() => void copyPaymentText(selected.total_text.replace(/[^0-9]/g, ""))}>📋 Summani nusxalash</button> : null}
              {canSubmitPayment && selected.pay_card ? <button type="button" className="btn btn-soft btn-block" onClick={() => void copyPaymentText(selected.pay_card.replace(/\s/g, ""))}>📋 Karta raqamini nusxalash</button> : null}
              {canSubmitPayment ? <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={() => chatFileRef.current?.click()}>📎 Kvitansiyani yuborish</button> : null}
              {canSubmitPayment ? <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={() => void mutate(() => api.submitOrderPayment(selected.id))}>✅ To'lov qildim</button> : null}
              {side === "provider" && ["submitted", "recheck", "disputed"].includes(selected.payment_status) ? <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={() => setConfirmation("payment-confirm")}>✅ To'lovni tasdiqlash</button> : null}
              {side === "provider" && ["submitted", "recheck", "disputed"].includes(selected.payment_status) ? <button type="button" className="btn btn-soft btn-block" disabled={busy} onClick={() => setProblemOpen(true)}>⚠️ To'lov bo'yicha muammo</button> : null}
            </div>
            {canSubmitPayment ? <div className="idesc order-payment-foot">To'lagach chek rasmini yuboring — do'kon tekshirib tasdiqlaydi.</div> : null}
          </section>
        ) : null}

        {selected.problem_open ? (
          <section className="panel-card order-problem-v1656">
            <b>⚠️ To'lov aniqlashtirilmoqda</b>
            <p>{problemReasonText(selected.problem_reason)}</p>
            {selected.problem_note ? <p>Izoh: {selected.problem_note}</p> : null}
            {selected.problem_solution === "pickup" ? <p><b>Do'kon:</b> {selected.provider_address || "Manzil kiritilmagan"}{selected.provider_phone ? ` · ${selected.provider_phone}` : ""}{workHoursText(selected.provider_work_hours) ? ` · ${workHoursText(selected.provider_work_hours)}` : ""}</p> : null}
            {side === "customer" ? <div className="order-action-row">
              {([[
                "pickup", "🏪 Do'konga boraman",
              ], ["wait", "⏳ Kutaman"], ["new_receipt", "🧾 Yangi chek"]] as Array<[OrderProblemSolution, string]>).map(([solution, label]) => (
                <button key={solution} type="button" className="mini-btn" disabled={busy} onClick={() => void mutate(() => api.chooseOrderProblemSolution(selected.id, solution))}>{label}</button>
              ))}
            </div> : null}
          </section>
        ) : null}

        {showStatusActions ? <section className="panel-card order-status-actions">
          {side === "provider" && selected.status === "new" ? <>
            <button type="button" className="mini-btn ok" disabled={busy} onClick={() => void changeStatus("accepted")}>Qabul qilish</button>
            <button type="button" className="mini-btn danger" disabled={busy} onClick={() => void changeStatus("rejected")}>Rad etish</button>
          </> : null}
          {side === "provider" && selected.status === "accepted" ? <button type="button" className="mini-btn danger" disabled={busy} onClick={() => void changeStatus("cancelled")}>Bekor qilish</button> : null}
          {side === "provider" && selected.status === "accepted" ? <button type="button" className="mini-btn warning" disabled={busy} onClick={() => setDebtPickerOpen(true)}>📒 Qarzga rasmiylashtirish</button> : null}
          {side === "provider" && selected.status === "preparing" ? <button type="button" className="mini-btn ok" disabled={busy} onClick={() => void changeStatus("tayyor")}>✅ Buyurtma tayyor</button> : null}
          {side === "provider" && selected.status === "tayyor" && selected.order_type === "delivery" ? <p>Dostavkachi qidirilmoqda</p> : null}
          {side === "provider" && selected.status === "handoff_waiting_seller" ? <button type="button" className="mini-btn ok" onClick={() => setConfirmation("handoff")}>📦 Dostavkachiga topshirdim</button> : null}
          {side === "provider" && selected.status === "tayyor" && selected.order_type === "pickup" ? <button type="button" className="mini-btn ok" onClick={() => setConfirmation("handoff")}>🏪 Buyurtmachiga topshirdim</button> : null}
          {side === "customer" && ["new", "accepted"].includes(selected.status) ? <button type="button" className="mini-btn danger" disabled={busy} onClick={() => void changeStatus("cancelled")}>Bekor qilish</button> : null}
          {side === "customer" && selected.status === "preparing" ? <p>Buyurtma tayyorlanmoqda</p> : null}
          {side === "customer" && selected.status === "tayyor" ? <p>{selected.order_type === "delivery" ? "Dostavkachi qidirilmoqda" : "Do'kondan olib ketishingiz mumkin"}</p> : null}
          {side === "customer" && ["delivered_waiting_customer", "pickup_waiting_customer"].includes(selected.status) ? <button type="button" className="mini-btn ok" onClick={() => setConfirmation("received")}>✅ Buyurtmani qabul qildim</button> : null}
        </section> : null}

        <section className="panel-card order-chat-box">
          <b>💬 Buyurtma chati</b>
          <div className="idesc">Bu suhbat faqat shu buyurtmaga bog‘langan. Umumiy chatga aralashmaydi.</div>
          <div className="order-chat-list">
            {!messages.length ? <div className="order-chat-empty">Hozircha buyurtma bo‘yicha xabar yo‘q.</div> : messages.map((message) => (
              <div className={`msg ${message.mine ? "me" : "them"}`} key={message.id}>
                {message.is_deleted ? <div className="order-chat-deleted">Xabar o‘chirildi</div> : <>
                  <button type="button" className="order-msg-menu-btn" aria-label="Xabar amallari" onClick={() => setMessageMenu(message)}>⋯</button>
                  {message.reply ? <div className="order-chat-reply-preview"><b>↩ {message.reply.sender_name || "Xabar"}</b>{messagePreview(message.reply)}</div> : null}
                  {message.media_type === "photo" && message.media_url ? <img className="order-chat-photo" src={message.media_url} alt="Rasm" title="Rasmni ochish" role="button" tabIndex={0} onClick={() => setPhotoUrl(message.media_url)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setPhotoUrl(message.media_url); }} /> : null}
                  {message.text ? <div className="order-chat-text">{message.text}</div> : null}
                </>}
                <span className="msg-time">{message.mine ? "Siz" : message.sender_name} · {createdText(message.created_at)}{message.edited_at ? " · Tahrirlangan" : ""}</span>
              </div>
            ))}
          </div>
          {replyTo ? <div className="order-chat-state on">Javob berilyapti<small>{messagePreview(replyTo)}</small><button type="button" aria-label="Javobni bekor qilish" onClick={() => setReplyTo(null)}>×</button></div> : null}
          {editing ? <div className="order-chat-state edit on">Xabar tahrirlanyapti<small>{messagePreview(editing)}</small><button type="button" aria-label="Tahrirlashni bekor qilish" onClick={() => { setEditing(null); setText(""); }}>×</button></div> : null}
          {pendingImage ? <div className="order-chat-preview on">
            <button type="button" className="order-chat-preview-x" aria-label="Rasmni bekor qilish" onClick={() => { setPendingImage(null); if (chatFileRef.current) chatFileRef.current.value = ""; }}>×</button>
            {pendingImageUrl ? <img src={pendingImageUrl} alt="Tanlangan rasm" /> : null}
            <div className="idesc">Rasm tanlandi. Yuborish uchun chatdagi “Yuborish” tugmasini bosing.</div>
          </div> : null}
          <div className="order-chat-attach-row">
            <label className="order-chat-attach-btn">📎 Rasm qo‘shish<input ref={chatFileRef} className="order-chat-file" type="file" accept="image/*" disabled={busy || Boolean(editing)} onChange={(event) => { const file = event.currentTarget.files?.[0]; if (file) chooseImage(file); }} /></label>
          </div>
          <div className="order-chat-send">
            <input placeholder="Buyurtma bo‘yicha xabar yozing..." value={text} onChange={(event) => setText(event.currentTarget.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); void sendMessage(); } }} />
            <button type="button" disabled={busy} onClick={() => void sendMessage()}>{editing ? "Saqlash" : "Yuborish"}</button>
          </div>
        </section>
        {messageMenu ? <div className="order-chat-action-menu on">
          <button type="button" onClick={() => { setReplyTo(messageMenu); setEditing(null); setMessageMenu(null); }}>↩️ Javob berish</button>
          <button type="button" onClick={() => { void copyMessage(messageMenu); setMessageMenu(null); }}>📋 Nusxalash</button>
          {messageMenu.mine && messageMenu.text.trim() ? <button type="button" onClick={() => { setEditing(messageMenu); setReplyTo(null); setText(messageMenu.text); setPendingImage(null); setMessageMenu(null); }}>✏️ Tahrirlash</button> : null}
          {messageMenu.mine ? <button type="button" className="danger" onClick={() => { setDeleteTarget(messageMenu); setConfirmation("delete-message"); setMessageMenu(null); }}>🗑 O‘chirish</button> : null}
        </div> : null}
        {photoUrl ? <div className="order-photo-viewer on" role="dialog" aria-label="Buyurtma chati rasmi" onClick={(event) => { if (event.currentTarget === event.target) setPhotoUrl(""); }}>
          <button type="button" className="order-photo-viewer-x" aria-label="Rasmni yopish" onClick={() => setPhotoUrl("")}>×</button>
          <img src={photoUrl} alt="Buyurtma chati rasmi" />
        </div> : null}
        <button type="button" className="btn btn-soft btn-block" onClick={() => setSelected(null)}>Yopish</button>

        {problemOpen ? (
          <div className="order-confirm-backdrop">
            <section aria-label="To'lov bo'yicha muammo" aria-modal="true" className="order-confirm order-problem-dialog" role="dialog">
              <b>To'lov bo'yicha muammo</b>
              <div className="lead-sub">Sababni tanlang. Muammo hal bo'lmaguncha tayyorlash, dostavka va yakunlash bloklanadi.</div>
              <label>Muammo sababi<select value={problemReason} onChange={(event) => setProblemReason(event.currentTarget.value as OrderProblemReason)}>{PROBLEM_REASONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
              <label>Izoh<textarea placeholder="Muammoni qisqacha tushuntiring" value={problemNote} onChange={(event) => setProblemNote(event.currentTarget.value)} /></label>
              <div className="order-confirm-actions">
                <button type="button" className="mini-btn" onClick={() => setProblemOpen(false)}>Bekor qilish</button>
                <button type="button" className="mini-btn warning" disabled={busy} onClick={() => void (async () => {
                  if (await mutate(() => api.openOrderProblem(selected.id, { reason: problemReason, note: problemNote.trim() }))) setProblemOpen(false);
                })()}>Muammoli buyurtmaga o'tkazish</button>
              </div>
            </section>
          </div>
        ) : null}
        {confirmation ? <ConfirmDialog kind={confirmation} onCancel={() => { setConfirmation(null); setDeleteTarget(null); }} onConfirm={() => {
          if (confirmation === "delete-message") void removeMessage();
          else if (confirmation === "received") void (async () => {
            if (await mutate(() => api.receiveOrder(selected.id))) setConfirmation(null);
          })();
          else if (confirmation === "payment-confirm") void (async () => {
            if (await mutate(() => api.decideOrderPayment(selected.id, "confirmed"))) setConfirmation(null);
          })();
          else void (async () => {
            if (await mutate(() => api.handoffOrder(selected.id))) setConfirmation(null);
          })();
        }} /> : null}
        {debtPickerOpen ? (
          <DebtorPickerV1656
            api={api}
            title="Tashqi buyurtmani qarzga yozish"
            onCancel={() => setDebtPickerOpen(false)}
            onSelect={(debtorId) => { void (async () => {
              if (await mutate(() => api.decideOrderPayment(selected.id, "debt", debtorId))) {
                setDebtPickerOpen(false);
              }
            })(); }}
          />
        ) : null}
      </main>
      </>
    );
  }

  return (
    <main className="orders-cabinet-v1656">
      <header className="orders-v1656-heading">
        <button type="button" className="mini-btn" onClick={onBack}>‹</button>
        <h1>{side === "customer"
          ? category === "service" ? "Xizmat buyurtmalarim" : "Buyurtmalarim"
          : category === "service" ? "Xizmat buyurtmalari" : "Buyurtmalar"}</h1>
      </header>
      {error ? <p className="app-toast on" role="alert">{error}</p> : null}
      {beforeList}
      <div className="order-tabs" role="tablist">
        <button type="button" className={`seg-b${tab === "active" ? " on" : ""}`} onClick={() => setTab("active")}>Buyurtmalar ({active.length}){active.some((order) => order.is_unread) ? " 🔔" : ""}</button>
        <button type="button" className={`seg-b${tab === "problem" ? " on" : ""}`} onClick={() => setTab("problem")}>Muammoli ({problem.length})</button>
        <button type="button" className={`seg-b${tab === "done" ? " on" : ""}`} onClick={() => setTab("done")}>Yakunlangan ({done.length}){done.some((order) => order.is_unread) ? " 🔔" : ""}</button>
      </div>
      {loading ? <p>Buyurtmalar yuklanmoqda...</p> : shown.length ? (
        <div className="orders-v1656-list">
          {shown.map((order) => (
            <div role="button" tabIndex={0} className={`item order-card${order.status === "new" ? " order-new" : ""}${order.is_unread ? " order-unread" : ""}`} key={order.id} onClick={() => void openDetail(order)} onKeyDown={(event) => { if (event.currentTarget !== event.target) return; if (event.key === "Enter" || event.key === " ") void openDetail(order); }}>
              <div className="order-card-number"><span className="order-no-pill">BUYURTMA №{order.id}</span><span className="idesc">🕒 {createdText(order.created_at)}</span></div>
              <div className="order-card-head"><div><div className="iname">{order.title || "Buyurtma"}</div><div className="idesc">{side === "provider" ? "Mijoz" : "Qabul qiluvchi"}: {side === "provider" ? order.customer_name : order.provider_name}</div></div><span className={`tx-amt ${["rejected", "cancelled"].includes(order.status) ? "debit" : "credit"}`}>{statusText(order.status)}</span></div>
              {order.is_unread ? <div className="order-unread-pill">{isMessageEvent(order.last_event) ? "💬 Xabar keldi" : side === "provider" ? "🔔 Yangi buyurtma" : "🔔 Status yangilandi"}</div> : null}
              <div className="idesc">Turi: {typeText(order.order_type)}</div>
              {order.address ? <div className="idesc">📍 {order.address}</div> : null}
              {order.delivery_lat != null && order.delivery_lng != null ? <div className="idesc">🗺 {order.delivery_lat.toFixed(6)}, {order.delivery_lng.toFixed(6)}</div> : null}
              {order.desired_time ? <div className="idesc">🕒 {order.desired_time}</div> : null}
              {order.phone ? <div className="idesc">☎ {order.phone}</div> : null}
              {order.note ? <div className="idesc order-card-note">{order.note}</div> : null}
              {order.problem_open ? <div className="order-card-problem"><b>⚠️ To'lov aniqlashtirilmoqda</b><div>{problemReasonText(order.problem_reason)}</div>{order.problem_note ? <div>Izoh: {order.problem_note}</div> : null}{order.problem_solution === "pickup" ? <div><b>Do'kon:</b> {order.provider_address || "Manzil kiritilmagan"}{order.provider_phone ? ` · ${order.provider_phone}` : ""}{workHoursText(order.provider_work_hours) ? ` · ${workHoursText(order.provider_work_hours)}` : ""}</div> : null}</div> : null}
              {order.items.length ? <div className="order-card-items">{order.items.map((item) => <div className="idesc" key={item.id}><span>{item.name} × {qtyText(item.qty, item.unit)}</span><b>{item.line_total ? item.line_total.toLocaleString("uz-UZ") : item.price || "—"}</b></div>)}{order.total_text ? <div className="iprice">Jami: {order.total_text}</div> : null}</div> : null}
              {order.last_chat ? <div className="idesc order-card-chat">💬 {order.last_chat}</div> : order.chat_count ? <div className="idesc order-card-chat">💬 {order.chat_count} ta xabar</div> : null}
              {!order.problem_open && side === "provider" && order.status === "new" ? <div className="order-card-actions">
                <button type="button" className="mini-btn" disabled={busy} onClick={(event) => { event.stopPropagation(); void mutate(() => api.changeOrderStatus(order.id, "accepted")); }}>Qabul qilish</button>
                <button type="button" className="mini-btn danger" disabled={busy} onClick={(event) => { event.stopPropagation(); void mutate(() => api.changeOrderStatus(order.id, "rejected")); }}>Rad etish</button>
              </div> : null}
              {!order.problem_open && side === "provider" && order.status === "accepted" ? <div className="order-card-actions">
                {["submitted", "recheck", "disputed"].includes(order.payment_status) ? <button type="button" className="mini-btn warning" disabled={busy} onClick={(event) => { event.stopPropagation(); void openDetail(order).then(() => setProblemOpen(true)); }}>⚠️ To'lov muammosi</button> : null}
                <button type="button" className="mini-btn danger" disabled={busy} onClick={(event) => { event.stopPropagation(); void mutate(() => api.changeOrderStatus(order.id, "cancelled")); }}>Bekor qilish</button>
              </div> : null}
              {!order.problem_open && side === "provider" && order.status === "preparing" ? <div className="order-card-actions"><button type="button" className="mini-btn ok" disabled={busy} onClick={(event) => { event.stopPropagation(); void mutate(() => api.changeOrderStatus(order.id, "tayyor")); }}>✅ Buyurtma tayyor</button></div> : null}
              {!order.problem_open && side === "provider" && order.status === "tayyor" && order.order_type === "delivery" ? <div className="idesc order-card-status">Dostavkachi qidirilmoqda</div> : null}
              {!order.problem_open && side === "provider" && order.status === "handoff_waiting_seller" ? <div className="order-card-actions"><button type="button" className="mini-btn ok" onClick={(event) => { event.stopPropagation(); setSelected(order); setConfirmation("handoff"); }}>📦 Dostavkachiga topshirdim</button></div> : null}
              {!order.problem_open && side === "provider" && order.status === "tayyor" && order.order_type === "pickup" ? <div className="order-card-actions"><button type="button" className="mini-btn ok" onClick={(event) => { event.stopPropagation(); setSelected(order); setConfirmation("handoff"); }}>🏪 Buyurtmachiga topshirdim</button></div> : null}
              {!order.problem_open && side === "customer" && ["new", "accepted"].includes(order.status) ? <div className="order-card-actions"><button type="button" className="mini-btn danger" disabled={busy} onClick={(event) => { event.stopPropagation(); void mutate(() => api.changeOrderStatus(order.id, "cancelled")); }}>Bekor qilish</button></div> : null}
              {!order.problem_open && side === "customer" && order.status === "preparing" ? <div className="idesc order-card-status">Buyurtma tayyorlanmoqda</div> : null}
              {!order.problem_open && side === "customer" && order.status === "tayyor" ? <div className="idesc order-card-status">{order.order_type === "delivery" ? "Dostavkachi qidirilmoqda" : "Do'kondan olib ketishingiz mumkin"}</div> : null}
              {!order.problem_open && side === "customer" && ["delivered_waiting_customer", "pickup_waiting_customer"].includes(order.status) ? <div className="order-card-actions"><button type="button" className="mini-btn ok" onClick={(event) => { event.stopPropagation(); setSelected(order); setConfirmation("received"); }}>✅ Buyurtmani qabul qildim</button></div> : null}
              {order.problem_open && side === "customer" ? <div className="order-card-actions">{([[
                "pickup", "🏪 Do'konga boraman",
              ], ["wait", "⏳ Kutaman"], ["new_receipt", "🧾 Yangi chek"]] as Array<[OrderProblemSolution, string]>).map(([solution, label]) => <button type="button" className="mini-btn" key={solution} disabled={busy} onClick={(event) => { event.stopPropagation(); void mutate(() => api.chooseOrderProblemSolution(order.id, solution)); }}>{label}</button>)}</div> : null}
              <div className="idesc order-detail-hint">Batafsil ko‘rish va chat uchun bosing</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty"><h3>{tab === "active" ? "Faol buyurtma yo'q" : tab === "problem" ? "Muammoli buyurtma yo'q" : "Yakunlangan buyurtma yo'q"}</h3></div>
      )}
    </main>
  );
}
