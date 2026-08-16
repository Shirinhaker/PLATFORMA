import type { RefObject } from "react";

import type { OrderProblemSolution, OrderRead, OrderStatus } from "../api/types";
import { paymentText, problemReasonText, workHoursText } from "./order-cabinet-helpers";
import type { OrderConfirmation } from "./order-cabinet-types";

type OrderWorkflowPanelProps = {
  selected: OrderRead;
  side: "customer" | "provider";
  busy: boolean;
  chatFileRef: RefObject<HTMLInputElement | null>;
  onNotice(message: string): void;
  onSubmitPayment(): unknown;
  onConfirmationChange(confirmation: OrderConfirmation): void;
  onProblemOpenChange(open: boolean): void;
  onChooseProblemSolution(solution: OrderProblemSolution): unknown;
  onChangeStatus(status: OrderStatus): unknown;
  onDebtPickerOpenChange(open: boolean): void;
};

export function OrderWorkflowPanel({
  selected,
  side,
  busy,
  chatFileRef,
  onNotice,
  onSubmitPayment,
  onConfirmationChange,
  onProblemOpenChange,
  onChooseProblemSolution,
  onChangeStatus,
  onDebtPickerOpenChange,
}: OrderWorkflowPanelProps) {
  async function copyPaymentText(value: string) {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(value);
      onNotice("Nusxa olindi ✅");
    } catch {
      onNotice("Nusxa olinmadi — havolani qo'lda belgilang");
    }
  }

  const hasPaymentData = Boolean(selected.pay_card || selected.pay_qr_url);
  const canSubmitPayment =
    side === "customer" &&
    selected.status !== "new" &&
    hasPaymentData &&
    !["submitted", "recheck", "disputed", "confirmed"].includes(
      selected.payment_status,
    );
  const showStatusActions =
    !selected.problem_open &&
    (side === "provider"
      ? ["new", "accepted", "preparing", "tayyor", "handoff_waiting_seller"].includes(
          selected.status,
        )
      : [
          "new",
          "accepted",
          "preparing",
          "tayyor",
          "delivered_waiting_customer",
          "pickup_waiting_customer",
        ].includes(selected.status));

  return (
    <>
      {selected.status !== "new" && hasPaymentData ? (
        <section className="panel-card order-payment-v1656">
          <b>💳 Onlayn to'lov</b>
          <p>{paymentText(selected.payment_status)}</p>
          {side === "provider" ? (
            <div className="idesc">
              Mijoz chek (to'lov skrinshoti)ni suhbatga tashlaydi. Tekshirib tasdiqlang.
            </div>
          ) : null}
          {side === "customer" &&
          ["submitted", "recheck", "disputed"].includes(selected.payment_status) ? (
            <div className="idesc">
              To'lov ma'lumoti sotuvchiga yuborildi. Tekshiruv natijasini kuting.
            </div>
          ) : null}
          {side === "customer" && canSubmitPayment ? (
            <div className="idesc">
              To'lash uchun: summa va karta raqamini nusxalang, to'lov ilovangizni
              (Click/Payme/bank) oching va o'tkazing. So'ng kvitansiya (chek) rasmini
              yuboring.
            </div>
          ) : null}
          {side === "customer" && canSubmitPayment && selected.total_text ? (
            <div className="detail-line">
              <b>To'lov summasi</b>
              <strong>{selected.total_text}</strong>
            </div>
          ) : null}
          {side === "customer" && canSubmitPayment && selected.pay_card ? (
            <div className="detail-line">
              <b>Karta raqami</b>
              <strong>{selected.pay_card}</strong>
            </div>
          ) : null}
          {side === "customer" && canSubmitPayment && selected.pay_holder ? (
            <div className="detail-line">
              <b>Karta egasi</b>
              <span>{selected.pay_holder}</span>
            </div>
          ) : null}
          {side === "customer" && canSubmitPayment && selected.pay_qr_url ? (
            <>
              <div className="idesc order-payment-qr-hint">
                Yoki QR kodni to'lov ilovangizda skanerlang:
              </div>
              <img src={selected.pay_qr_url} alt="QR" />
            </>
          ) : null}
          {side === "customer" && selected.payment_status === "confirmed" ? (
            <div className="idesc">
              To'lovingiz do'kon tomonidan tasdiqlandi. Rahmat!
            </div>
          ) : null}
          <div className="order-action-row">
            {canSubmitPayment && selected.total_text ? (
              <button
                type="button"
                className="btn btn-soft btn-block"
                onClick={() =>
                  void copyPaymentText(selected.total_text.replace(/[^0-9]/g, ""))
                }
              >
                📋 Summani nusxalash
              </button>
            ) : null}
            {canSubmitPayment && selected.pay_card ? (
              <button
                type="button"
                className="btn btn-soft btn-block"
                onClick={() =>
                  void copyPaymentText(selected.pay_card.replace(/\s/g, ""))
                }
              >
                📋 Karta raqamini nusxalash
              </button>
            ) : null}
            {canSubmitPayment ? (
              <button
                type="button"
                className="btn btn-primary btn-block"
                disabled={busy}
                onClick={() => chatFileRef.current?.click()}
              >
                📎 Kvitansiyani yuborish
              </button>
            ) : null}
            {canSubmitPayment ? (
              <button
                type="button"
                className="btn btn-primary btn-block"
                disabled={busy}
                onClick={() => void onSubmitPayment()}
              >
                ✅ To'lov qildim
              </button>
            ) : null}
            {side === "provider" &&
            ["submitted", "recheck", "disputed"].includes(selected.payment_status) ? (
              <button
                type="button"
                className="btn btn-primary btn-block"
                disabled={busy}
                onClick={() => onConfirmationChange("payment-confirm")}
              >
                ✅ To'lovni tasdiqlash
              </button>
            ) : null}
            {side === "provider" &&
            ["submitted", "recheck", "disputed"].includes(selected.payment_status) ? (
              <button
                type="button"
                className="btn btn-soft btn-block"
                disabled={busy}
                onClick={() => onProblemOpenChange(true)}
              >
                ⚠️ To'lov bo'yicha muammo
              </button>
            ) : null}
          </div>
          {canSubmitPayment ? (
            <div className="idesc order-payment-foot">
              To'lagach chek rasmini yuboring — do'kon tekshirib tasdiqlaydi.
            </div>
          ) : null}
        </section>
      ) : null}

      {selected.problem_open ? (
        <section className="panel-card order-problem-v1656">
          <b>⚠️ To'lov aniqlashtirilmoqda</b>
          <p>{problemReasonText(selected.problem_reason)}</p>
          {selected.problem_note ? <p>Izoh: {selected.problem_note}</p> : null}
          {selected.problem_solution === "pickup" ? (
            <p>
              <b>Do'kon:</b> {selected.provider_address || "Manzil kiritilmagan"}
              {selected.provider_phone ? ` · ${selected.provider_phone}` : ""}
              {workHoursText(selected.provider_work_hours)
                ? ` · ${workHoursText(selected.provider_work_hours)}`
                : ""}
            </p>
          ) : null}
          {side === "customer" ? (
            <div className="order-action-row">
              {(
                [
                  ["pickup", "🏪 Do'konga boraman"],
                  ["wait", "⏳ Kutaman"],
                  ["new_receipt", "🧾 Yangi chek"],
                ] as Array<[OrderProblemSolution, string]>
              ).map(([solution, label]) => (
                <button
                  key={solution}
                  type="button"
                  className="mini-btn"
                  disabled={busy}
                  onClick={() => void onChooseProblemSolution(solution)}
                >
                  {label}
                </button>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {showStatusActions ? (
        <section className="panel-card order-status-actions">
          {side === "provider" && selected.status === "new" ? (
            <>
              <button
                type="button"
                className="mini-btn ok"
                disabled={busy}
                onClick={() => void onChangeStatus("accepted")}
              >
                Qabul qilish
              </button>
              <button
                type="button"
                className="mini-btn danger"
                disabled={busy}
                onClick={() => void onChangeStatus("rejected")}
              >
                Rad etish
              </button>
            </>
          ) : null}
          {side === "provider" && selected.status === "accepted" ? (
            <button
              type="button"
              className="mini-btn danger"
              disabled={busy}
              onClick={() => void onChangeStatus("cancelled")}
            >
              Bekor qilish
            </button>
          ) : null}
          {side === "provider" && selected.status === "accepted" ? (
            <button
              type="button"
              className="mini-btn warning"
              disabled={busy}
              onClick={() => onDebtPickerOpenChange(true)}
            >
              📒 Qarzga rasmiylashtirish
            </button>
          ) : null}
          {side === "provider" && selected.status === "preparing" ? (
            <button
              type="button"
              className="mini-btn ok"
              disabled={busy}
              onClick={() => void onChangeStatus("tayyor")}
            >
              ✅ Buyurtma tayyor
            </button>
          ) : null}
          {side === "provider" &&
          selected.status === "tayyor" &&
          selected.order_type === "delivery" ? (
            <p>Dostavkachi qidirilmoqda</p>
          ) : null}
          {side === "provider" && selected.status === "handoff_waiting_seller" ? (
            <button
              type="button"
              className="mini-btn ok"
              onClick={() => onConfirmationChange("handoff")}
            >
              📦 Dostavkachiga topshirdim
            </button>
          ) : null}
          {side === "provider" &&
          selected.status === "tayyor" &&
          selected.order_type === "pickup" ? (
            <button
              type="button"
              className="mini-btn ok"
              onClick={() => onConfirmationChange("handoff")}
            >
              🏪 Buyurtmachiga topshirdim
            </button>
          ) : null}
          {side === "customer" && ["new", "accepted"].includes(selected.status) ? (
            <button
              type="button"
              className="mini-btn danger"
              disabled={busy}
              onClick={() => void onChangeStatus("cancelled")}
            >
              Bekor qilish
            </button>
          ) : null}
          {side === "customer" && selected.status === "preparing" ? (
            <p>Buyurtma tayyorlanmoqda</p>
          ) : null}
          {side === "customer" && selected.status === "tayyor" ? (
            <p>
              {selected.order_type === "delivery"
                ? "Dostavkachi qidirilmoqda"
                : "Do'kondan olib ketishingiz mumkin"}
            </p>
          ) : null}
          {side === "customer" &&
          ["delivered_waiting_customer", "pickup_waiting_customer"].includes(
            selected.status,
          ) ? (
            <button
              type="button"
              className="mini-btn ok"
              onClick={() => onConfirmationChange("received")}
            >
              ✅ Buyurtmani qabul qildim
            </button>
          ) : null}
        </section>
      ) : null}
    </>
  );
}
