import type { OrderRead } from "../api/types";
import { createdText, qtyText, statusText, typeText } from "./order-cabinet-helpers";
import { OrderLocationMap } from "./OrderLocationMap";

type OrderDetailOverviewProps = {
  selected: OrderRead;
  side: "customer" | "provider";
};

export function OrderDetailOverview({ selected, side }: OrderDetailOverviewProps) {
  const otherLabel = side === "provider" ? "Mijoz" : "Qabul qiluvchi";
  const otherName =
    side === "provider" ? selected.customer_name : selected.provider_name;

  return (
    <>
      <section className="panel-card">
        <div className="detail-line">
          <b>Buyurtma raqami</b>
          <span className="order-no-pill">№{selected.id}</span>
        </div>
        <div className="detail-line">
          <b>Buyurtma vaqti</b>
          <span>{createdText(selected.created_at)}</span>
        </div>
        <div className="detail-line">
          <b>Status</b>
          <span>{statusText(selected.status)}</span>
        </div>
        <div className="detail-line">
          <b>{otherLabel}</b>
          <span>{otherName || "—"}</span>
        </div>
        <div className="detail-line">
          <b>Turi</b>
          <span>{typeText(selected.order_type)}</span>
        </div>
        {selected.phone ? (
          <div className="detail-line">
            <b>Telefon</b>
            <span>{selected.phone}</span>
          </div>
        ) : null}
        {selected.address ? (
          <div className="detail-line">
            <b>Manzil</b>
            <span>{selected.address}</span>
          </div>
        ) : null}
        {selected.desired_time ? (
          <div className="detail-line">
            <b>Vaqt</b>
            <span>{selected.desired_time}</span>
          </div>
        ) : null}
        {selected.note ? (
          <div className="order-detail-note">
            <b>Izoh</b>
            <div className="idesc">{selected.note}</div>
          </div>
        ) : null}
      </section>

      <section className="panel-card order-receipt-v1656">
        <div className="order-receipt-title">
          <b>🧾 Buyurtma cheki №{selected.id}</b>
          <span>{createdText(selected.created_at)}</span>
        </div>
        {!selected.items.length ? (
          <div className="idesc">Mahsulotlar kiritilmagan.</div>
        ) : (
          selected.items.map((item) => (
            <div className="order-receipt-item" key={item.id}>
              <div className="order-receipt-name">{item.name || "Mahsulot"}</div>
              <div className="order-receipt-meta">
                <span>Miqdori</span>
                <b>{qtyText(item.qty, item.unit)}</b>
                <span>Dona narxi</span>
                <b>{item.price || "Narx kelishiladi"}</b>
                <span>Jami</span>
                <b>
                  {item.line_total
                    ? `${item.line_total.toLocaleString("uz-UZ")} so‘m`
                    : "—"}
                </b>
              </div>
            </div>
          ))
        )}
        {selected.total_text ? (
          <div className="iprice order-receipt-total">
            Umumiy jami: {selected.total_text}
          </div>
        ) : null}
      </section>

      {selected.delivery_lat != null && selected.delivery_lng != null ? (
        <section className="panel-card">
          <b>Yetkazib berish metkasi</b>
          <OrderLocationMap
            latitude={selected.delivery_lat}
            longitude={selected.delivery_lng}
          />
          <div className="idesc">
            🗺 {selected.delivery_lat.toFixed(6)}, {selected.delivery_lng.toFixed(6)}
          </div>
        </section>
      ) : null}
    </>
  );
}
