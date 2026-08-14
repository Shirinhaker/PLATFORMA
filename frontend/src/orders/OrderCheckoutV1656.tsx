import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";

export type OrderDetails = {
  phone: string;
  order_type: "delivery" | "pickup" | "booking";
  address: string;
  desired_time: string;
  delivery_lat: number | null;
  delivery_lng: number | null;
  note: string;
};

type Point = { latitude: number; longitude: number };
type Props = {
  businessName: string;
  useItems: boolean;
  customer?: { phone?: string; address?: string };
  homePoint?: Point | null;
  onCancel(): void;
  onSubmit(details: OrderDetails): Promise<void>;
};

const TASHKENT: Point = { latitude: 41.311, longitude: 69.28 };

export function OrderCheckoutV1656({
  businessName,
  useItems,
  customer,
  homePoint,
  onCancel,
  onSubmit,
}: Props) {
  const mapNodeRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const phoneRef = useRef<HTMLInputElement | null>(null);
  const pointRef = useRef<Point | null>(null);
  const [type, setType] = useState<OrderDetails["order_type"]>("delivery");
  const [phone, setPhone] = useState(customer?.phone ?? "");
  const [address, setAddress] = useState(customer?.address ?? "");
  const [desiredTime, setDesiredTime] = useState("");
  const [note, setNote] = useState("");
  const [point, setPoint] = useState<Point | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const start = homePoint ?? TASHKENT;
  const startLatitude = start.latitude;
  const startLongitude = start.longitude;

  useEffect(() => {
    if (type !== "delivery") return undefined;
    const node = mapNodeRef.current;
    if (!node) return undefined;
    let disposed = false;
    let map: LeafletMap | null = null;
    let openTimer: number | undefined;
    let sizeTimer: number | undefined;

    const captureCenter = () => {
      const center = mapRef.current?.getCenter();
      if (center) {
        const next = { latitude: center.lat, longitude: center.lng };
        pointRef.current = next;
        setPoint(next);
      }
    };

    openTimer = window.setTimeout(() => {
      void import("leaflet").then(({ default: leaflet }) => {
        if (disposed) return;
        const initial = pointRef.current ?? {
          latitude: startLatitude,
          longitude: startLongitude,
        };
        map = leaflet.map(node, {
          zoomControl: true,
          attributionControl: false,
        }).setView([initial.latitude, initial.longitude], 15);
        leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
        }).addTo(map);
        map.on("moveend", captureCenter);
        map.on("click", (event) => {
          map?.setView(event.latlng, map.getZoom());
        });
        mapRef.current = map;
        sizeTimer = window.setTimeout(() => {
          mapRef.current?.invalidateSize();
          captureCenter();
        }, 160);
      }).catch(() => {
        if (!disposed) {
          setError("Xarita yuklanmoqda. Birozdan keyin qayta urinib ko‘ring.");
        }
      });
    }, 160);

    return () => {
      disposed = true;
      window.clearTimeout(openTimer);
      window.clearTimeout(sizeTimer);
      mapRef.current = null;
      map?.remove();
    };
  }, [startLatitude, startLongitude, type]);

  async function submit() {
    const cleanPhone = phone.trim();
    if (!cleanPhone) {
      setError("Telefon raqam kiritish kerak.");
      phoneRef.current?.focus();
      return;
    }
    if (type === "delivery" && !point) {
      setError("Yetkazib berish joyini xaritada belgilang.");
      return;
    }
    let cleanAddress = address.trim();
    if (type === "delivery" && point && !cleanAddress) {
      cleanAddress = `Xaritada belgilandi: ${point.latitude.toFixed(6)}, ${point.longitude.toFixed(6)}`;
    }
    setBusy(true);
    setError("");
    try {
      await onSubmit({
        phone: cleanPhone,
        order_type: type,
        address: cleanAddress,
        desired_time: desiredTime.trim(),
        delivery_lat: type === "delivery" ? point?.latitude ?? null : null,
        delivery_lng: type === "delivery" ? point?.longitude ?? null : null,
        note: note.trim(),
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Buyurtma yuborilmadi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button aria-label="Buyurtma oynasini yopish" className="sheet-backdrop on" id="orderSheetBackdrop" type="button" onClick={onCancel} />
      <section aria-modal="true" className="order-sheet on" id="orderSheet" role="dialog">
        <button className="order-close" aria-label="Yopish" type="button" onClick={onCancel}>×</button>
        <div className="order-grip" />
        <div className="lead" style={{ fontSize: 21, marginTop: 0 }}>Buyurtma berish</div>
        <div className="lead-sub" style={{ marginBottom: 14 }}>
          {businessName || "Biznes"}{useItems ? " — tanlangan mahsulot/xizmatlar bo‘yicha" : " — umumiy buyurtma"}
        </div>
        <div className="order-type-row">
          <button className={`order-type-btn${type === "delivery" ? " on" : ""}`} type="button" onClick={() => setType("delivery")}>
            🚚 Yetkazib berish<span>Manzilni xaritada metka qilib belgilang</span>
          </button>
          <button className={`order-type-btn${type === "pickup" ? " on" : ""}`} type="button" onClick={() => setType("pickup")}>
            🏪 Olib ketish<span>O‘zingiz borib olib ketasiz</span>
          </button>
          <button className={`order-type-btn${type === "booking" ? " on" : ""}`} type="button" onClick={() => setType("booking")}>
            🗓 Navbat / qabulga yozilish<span>Xizmat yoki qabul vaqtiga yozilasiz</span>
          </button>
        </div>
        <div className="field">
          <label htmlFor="orderPhone">Aloqa telefon raqami *</label>
          <input ref={phoneRef} className="input" id="orderPhone" inputMode="tel" placeholder="+998 __ ___ __ __" value={phone} onChange={(event) => setPhone(event.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="orderTime">{type === "booking" ? "Qaysi vaqtga yozilmoqchisiz? — ixtiyoriy" : "Qachonga kerak? — ixtiyoriy"}</label>
          <input className="input" id="orderTime" placeholder="Masalan: bugun 18:00" value={desiredTime} onChange={(event) => setDesiredTime(event.target.value)} />
        </div>
        {type === "delivery" ? (
          <div id="orderDeliveryBlock">
            <div className="field">
              <label htmlFor="orderAddress">Yetkazib berish manzili</label>
              <input className="input" id="orderAddress" placeholder="Tuman, mahalla, ko‘cha, uy" value={address} onChange={(event) => setAddress(event.target.value)} />
            </div>
            <div className="field">
              <label>Xaritada metka belgilang</label>
              <div className="order-map-wrap">
                <div id="orderMap" ref={mapNodeRef} />
                <div className="order-center-pin">📍</div>
                <div className="order-map-help"><span>Xaritani suring — metka markazda turadi</span></div>
              </div>
              <div className="idesc" id="orderMapInfo" style={{ marginTop: 7 }}>
                {point ? `✅ Metka belgilandi: ${point.latitude.toFixed(6)}, ${point.longitude.toFixed(6)}` : "Joy hali belgilanmagan"}
              </div>
            </div>
          </div>
        ) : null}
        <div className="field">
          <label htmlFor="orderNote">Izoh — ixtiyoriy</label>
          <textarea className="textarea" id="orderNote" placeholder="Masalan: qo‘ng‘iroq qilib keling, 2-qavat..." value={note} onChange={(event) => setNote(event.target.value)} />
        </div>
        {error ? <div className="app-toast on" role="alert">{error}</div> : null}
        <button className="btn btn-primary btn-block" id="orderSubmit" type="button" disabled={busy} onClick={() => void submit()}>✅ Buyurtma yuborish</button>
        <button className="btn btn-soft btn-block" id="orderCancel" style={{ marginTop: 9 }} type="button" onClick={onCancel}>Bekor qilish</button>
      </section>
    </>
  );
}
