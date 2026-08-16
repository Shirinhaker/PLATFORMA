import type { OrderConfirmation } from "./order-cabinet-types";

export function OrderConfirmDialog({
  kind,
  onCancel,
  onConfirm,
}: {
  kind: Exclude<OrderConfirmation, null>;
  onCancel(): void;
  onConfirm(): void;
}) {
  const received = kind === "received";
  const deleting = kind === "delete-message";
  const payment = kind === "payment-confirm";
  return (
    <div className="order-confirm-backdrop">
      <section
        aria-label={
          payment
            ? "To'lovni tasdiqlash"
            : received
              ? "Buyurtmani qabul qilish"
              : deleting
                ? "Xabarni o‘chirish"
                : "Buyurtmani topshirish"
        }
        aria-modal="true"
        className="order-confirm"
        role="dialog"
      >
        <b>
          {payment
            ? "To'lovni tasdiqlashni tasdiqlaysizmi?"
            : deleting
              ? "Bu xabar o‘chirilsinmi?"
              : received
                ? "Buyurtmani to'liq qabul qildingizmi?"
                : "Buyurtma qarshi tomonga topshirildimi?"}
        </b>
        <div className="order-confirm-actions">
          <button type="button" className="mini-btn" onClick={onCancel}>
            Bekor qilish
          </button>
          <button
            type="button"
            className={deleting ? "mini-btn danger" : "mini-btn ok"}
            onClick={onConfirm}
          >
            {payment
              ? "Tasdiqlash"
              : deleting
                ? "O‘chirish"
                : received
                  ? "Ha, qabul qildim"
                  : "Ha, topshirdim"}
          </button>
        </div>
      </section>
    </div>
  );
}
