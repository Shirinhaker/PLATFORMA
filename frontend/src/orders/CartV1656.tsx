import { useState } from "react";

import type { ApiClient } from "../api/client";
import { findLocationCenter } from "../legacy/public/location-centers";
import type { HomeLocation } from "../legacy/public/location-storage";
import { OrderCheckoutV1656, type OrderDetails } from "./OrderCheckoutV1656";
import {
  cartReceiptTotal,
  changeCartItem,
  clearCartReceipt,
  formatQuantity,
  moneyText,
  parsePriceAmount,
  setCartItemQuantity,
  setCartItemSum,
  type CartReceipt,
  type CartState,
  unitAllowsFraction,
} from "./order-store";
import "./OrdersV1656.css";

type Props = {
  authenticated: boolean;
  carts: CartState;
  createOrder: ApiClient["createOrder"];
  customer?: { phone?: string; address?: string };
  filterProviderPublicId?: string | null;
  homeLocation?: HomeLocation | null;
  homePoint?: { latitude: number; longitude: number } | null;
  onCartsChange(carts: CartState): void;
  onNeedLogin(): void;
  onOrderSent?(): void;
};

function receiptIds(carts: CartState, filter?: string | null): string[] {
  return Object.keys(carts).filter((publicId) => (
    Object.keys(carts[publicId]?.items ?? {}).length > 0
    && (!filter || publicId === filter)
  ));
}

export function CartV1656({
  authenticated,
  carts,
  createOrder,
  customer,
  filterProviderPublicId,
  homeLocation,
  homePoint,
  onCartsChange,
  onNeedLogin,
  onOrderSent,
}: Props) {
  const [checkoutId, setCheckoutId] = useState<string | null>(null);
  const [clearId, setClearId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [sumDrafts, setSumDrafts] = useState<Record<string, string>>({});
  const [quantityDrafts, setQuantityDrafts] = useState<Record<string, string>>({});
  const ids = receiptIds(carts, filterProviderPublicId);
  const checkout = checkoutId ? carts[checkoutId] : undefined;
  const savedLocationPoint = homeLocation
    && Number.isFinite(homeLocation.latitude)
    && Number.isFinite(homeLocation.longitude)
    ? {
        latitude: Number(homeLocation.latitude),
        longitude: Number(homeLocation.longitude),
      }
    : null;
  const checkoutHomePoint = savedLocationPoint
    ?? homePoint
    ?? (homeLocation
      ? findLocationCenter(homeLocation.region, homeLocation.district)
      : null);

  function updateQuantity(
    providerPublicId: string,
    itemPublicId: string,
    raw: string,
    commit: boolean,
  ) {
    const item = carts[providerPublicId]?.items[itemPublicId];
    if (!item) return;
    const clean = unitAllowsFraction(item.unit)
      ? raw.replace(",", ".")
      : raw.replace(/[^0-9]/g, "");
    const quantity = Number.parseFloat(clean);
    const draftKey = `${providerPublicId}:${itemPublicId}`;
    setQuantityDrafts((current) => {
      if (!commit) return { ...current, [draftKey]: clean };
      const next = { ...current };
      delete next[draftKey];
      return next;
    });
    setSumDrafts((current) => {
      if (!(draftKey in current)) return current;
      const next = { ...current };
      delete next[draftKey];
      return next;
    });
    onCartsChange(setCartItemQuantity(
      carts,
      providerPublicId,
      itemPublicId,
      Number.isFinite(quantity) ? quantity : 0,
      commit,
    ));
  }

  function updateSum(providerPublicId: string, itemPublicId: string, raw: string) {
    const clean = raw.replace(/[^0-9]/g, "");
    const key = `${providerPublicId}:${itemPublicId}`;
    setQuantityDrafts((current) => {
      if (!(key in current)) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
    setSumDrafts((current) => ({
      ...current,
      [key]: clean,
    }));
    const amount = Number.parseInt(clean, 10) || 0;
    onCartsChange(setCartItemSum(carts, providerPublicId, itemPublicId, amount));
  }

  function commitSum(providerPublicId: string, itemPublicId: string) {
    const key = `${providerPublicId}:${itemPublicId}`;
    setSumDrafts((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    const quantity = carts[providerPublicId]?.items[itemPublicId]?.qty ?? 0;
    onCartsChange(setCartItemQuantity(
      carts, providerPublicId, itemPublicId, quantity, true,
    ));
  }

  function clear(providerPublicId: string) {
    onCartsChange(clearCartReceipt(carts, providerPublicId));
    setClearId(null);
  }

  function openCheckout(providerPublicId: string) {
    if (!authenticated) {
      onNeedLogin();
      return;
    }
    setNotice("");
    setCheckoutId(providerPublicId);
  }

  async function submit(receipt: CartReceipt, details: OrderDetails) {
    await createOrder({
      provider_kind: "business",
      provider_public_id: receipt.provider_public_id,
      items: Object.values(receipt.items).map((item) => ({
        public_id: item.public_id,
        qty: item.qty,
      })),
      listing_public_id: "",
      title: `Buyurtma: ${receipt.provider_name || "Biznes"}`,
      phone: details.phone,
      order_type: details.order_type,
      address: details.address,
      desired_time: details.desired_time,
      delivery_lat: details.delivery_lat,
      delivery_lng: details.delivery_lng,
      note: details.note,
    });
    onCartsChange(clearCartReceipt(carts, receipt.provider_public_id));
    setCheckoutId(null);
    setNotice("Buyurtma yuborildi.");
    onOrderSent?.();
  }

  return (
    <main className="screen active cart-v1656" data-screen="cart">
      <div className="form-wrap" id="cartBody">
        {notice ? <div className="app-toast on" role="status">{notice}</div> : null}
        {!ids.length ? (
          <div className="empty" style={{ padding: "48px 20px" }}>
            <div className="ic" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="9" cy="20" r="1.4" />
                <circle cx="18" cy="20" r="1.4" />
                <path d="M2 3h3l2.4 12.5a1.6 1.6 0 0 0 1.6 1.3h8.6a1.6 1.6 0 0 0 1.6-1.3L23 7H6" />
              </svg>
            </div>
            <h3>Savatcha bo'sh</h3>
            <p>Do'kon sahifasidan mahsulot qo'shing.</p>
          </div>
        ) : (
          <>
            {!filterProviderPublicId && ids.length > 1 ? (
              <div className="idesc" style={{ marginBottom: 10 }}>
                Har do'kon uchun alohida chek. Har birini alohida buyurtma qilasiz.
              </div>
            ) : null}
            {ids.map((providerPublicId) => {
              const receipt = carts[providerPublicId]!;
              const items = Object.values(receipt.items);
              const total = cartReceiptTotal(receipt);
              return (
                <section className="panel-card" key={providerPublicId} style={{ marginBottom: 14 }}>
                  <div className="cart-receipt-head">
                    <div className="cart-receipt-name">
                      <b>🏪 {receipt.provider_name || "Do'kon"}</b>
                      <div className="idesc">{items.length} xil mahsulot</div>
                    </div>
                    {total > 0 ? <div className="cart-receipt-total">{moneyText(total)}</div> : null}
                  </div>
                  {items.map((item) => {
                    const price = parsePriceAmount(item.price_text);
                    const sumDraftKey = `${providerPublicId}:${item.public_id}`;
                    const quantityValue = sumDraftKey in quantityDrafts
                      ? quantityDrafts[sumDraftKey]
                      : formatQuantity(item.qty);
                    const sumValue = sumDraftKey in sumDrafts
                      ? sumDrafts[sumDraftKey]
                      : item.qty > 0 ? String(Math.round(price * item.qty)) : "";
                    return (
                      <div className="item cart-line" key={item.public_id}>
                        <div className="cart-line-head">
                          <div className="iname">{item.name}</div>
                          <div className="idesc">{item.price_text || "Narx kelishiladi"}</div>
                        </div>
                        <div className="cart-line-controls">
                          <button aria-label={`${item.name} miqdorini kamaytirish`} className="mini-btn" type="button" onClick={() => onCartsChange(changeCartItem(carts, providerPublicId, item.public_id, -1))}>−</button>
                          <input
                            aria-label={`${item.name} miqdori`}
                            className="input"
                            inputMode={unitAllowsFraction(item.unit) ? "decimal" : "numeric"}
                            value={quantityValue}
                            onChange={(event) => updateQuantity(providerPublicId, item.public_id, event.target.value, false)}
                            onBlur={(event) => updateQuantity(providerPublicId, item.public_id, event.target.value, true)}
                          />
                          <span className="idesc">{item.unit || "dona"}</span>
                          <button aria-label={`${item.name} miqdorini oshirish`} className="mini-btn" type="button" onClick={() => onCartsChange(changeCartItem(carts, providerPublicId, item.public_id, 1))}>+</button>
                          {price > 0 ? (
                            <input
                              aria-label={`${item.name} summasi`}
                              className="input"
                              inputMode="numeric"
                              placeholder="so'm"
                              value={sumValue}
                              onChange={(event) => updateSum(providerPublicId, item.public_id, event.target.value)}
                              onBlur={() => commitSum(providerPublicId, item.public_id)}
                            />
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                  <button className="btn btn-amber btn-block" style={{ marginTop: 12 }} type="button" onClick={() => openCheckout(providerPublicId)}>Buyurtma qilish</button>
                  <button className="btn btn-soft btn-block" style={{ marginTop: 8 }} type="button" onClick={() => setClearId(providerPublicId)}>Chekni tozalash</button>
                </section>
              );
            })}
          </>
        )}
      </div>
      {checkout ? (
        <OrderCheckoutV1656
          businessName={checkout.provider_name}
          customer={customer}
          homePoint={checkoutHomePoint}
          useItems={Object.keys(checkout.items).length > 0}
          onCancel={() => setCheckoutId(null)}
          onSubmit={(details) => submit(checkout, details)}
        />
      ) : null}
      {clearId ? (
        <>
          <button
            aria-label="Bekor qilish"
            className="app-modal-back on"
            type="button"
            onClick={() => setClearId(null)}
          />
          <div className="app-confirm on" role="dialog" aria-modal="true">
            <p className="acf-text">Bu do'kon cheki tozalansinmi?</p>
            <div className="acf-btns">
              <button className="acf-cancel" type="button" onClick={() => setClearId(null)}>
                Bekor qilish
              </button>
              <button className="acf-ok danger" type="button" onClick={() => clear(clearId)}>
                Tozalash
              </button>
            </div>
          </div>
        </>
      ) : null}
    </main>
  );
}
