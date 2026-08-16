import type { OrderMessageRead, OrderProblemReason, OrderRead } from "../api/types";

const ACTIVE = new Set([
  "new",
  "accepted",
  "preparing",
  "tayyor",
  "courier_assigned",
  "courier_arrived_store",
  "handoff_waiting_seller",
  "in_delivery",
  "courier_arrived_customer",
  "delivered_waiting_customer",
  "pickup_waiting_customer",
]);

export const PROBLEM_REASONS: ReadonlyArray<readonly [OrderProblemReason, string]> = [
  ["not_received", "Pul hisobga tushmadi"],
  ["amount_short", "To'langan summa kam"],
  ["receipt_mismatch", "Chek ma'lumoti mos kelmadi"],
  ["receipt_unreadable", "Chek rasmi o'qilmaydi"],
  ["wrong_receipt", "Noto'g'ri chek yuborilgan"],
  ["other", "Boshqa muammo"],
];

export function problemReasonText(reason: string) {
  if (reason === "other") return "Boshqa to'lov muammosi";
  return PROBLEM_REASONS.find(([key]) => key === reason)?.[1] ?? reason;
}

export function workHoursText(value: Record<string, unknown>) {
  const raw = String(value.raw ?? value.text ?? "").trim();
  if (raw) return raw;
  const from = String(value.from ?? value.start ?? value.open ?? "").trim();
  const to = String(value.to ?? value.end ?? value.close ?? "").trim();
  return from && to ? `${from}–${to}` : "";
}

export function isMessageEvent(value: string) {
  return value === "msg" || value.includes("message");
}

export function errorText(reason: unknown) {
  return reason instanceof Error ? reason.message : "Amal bajarilmadi.";
}

export function isService(order: OrderRead) {
  return (
    order.order_category === "service" ||
    ["booking", "service", "queue", "medical"].includes(order.order_type)
  );
}

export function isActive(order: OrderRead) {
  return !order.problem_open && ACTIVE.has(order.status);
}

export function statusText(status: string) {
  return (
    (
      {
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
      } as Record<string, string>
    )[status] ??
    status ??
    "—"
  );
}

export function typeText(type: string) {
  return (
    (
      {
        delivery: "Yetkazib berish",
        pickup: "Olib ketish",
        booking: "Navbat/qabul",
      } as Record<string, string>
    )[type] ??
    type ??
    "—"
  );
}

export function createdText(value: string) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "—";
  return `${date.toLocaleDateString("uz-UZ", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })} · ${date.toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" })}`;
}

export function qtyText(qty: number, unit: string) {
  return `${Number.isInteger(qty) ? qty : qty.toLocaleString("uz-UZ")} ${unit || "dona"}`;
}

export function paymentText(status: string) {
  return (
    (
      {
        confirmed: "To'lov tasdiqlandi",
        rejected: "To'lov rad etildi",
        submitted: "To'lov tekshirilmoqda",
        recheck: "To'lov aniqlashtirilmoqda",
        disputed: "To'lov aniqlashtirilmoqda",
        pending: "To'lov kutilmoqda",
      } as Record<string, string>
    )[status] ?? "To'lov kutilmoqda"
  );
}

export function messagePreview(
  message: Pick<OrderMessageRead, "is_deleted" | "media_type" | "text">,
) {
  if (message.is_deleted) return "Xabar o‘chirildi";
  const text = message.text.trim();
  const value =
    message.media_type === "photo"
      ? `📷 Rasm${text ? `: ${text}` : ""}`
      : text || "Xabar";
  return value.length > 70 ? `${value.slice(0, 70)}…` : value;
}
