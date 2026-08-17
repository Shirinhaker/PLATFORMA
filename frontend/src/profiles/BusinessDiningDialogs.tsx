import { useState, type ReactNode } from "react";

import type { BusinessOnlineRecord } from "../api/business-online-types";

export type DiningModalState =
  | { kind: "choose" }
  | {
      kind: "form";
      placeKind: "table" | "room";
      place: BusinessOnlineRecord | null;
    }
  | { kind: "booking"; place: BusinessOnlineRecord }
  | { kind: "delete"; place: BusinessOnlineRecord }
  | { kind: "clear"; place: BusinessOnlineRecord };

export function DiningModal({
  children,
  close,
}: {
  children: ReactNode;
  close: () => void;
}) {
  return (
    <>
      <div className="app-modal-back on" onClick={close} />
      <div className="app-confirm on" onClick={(event) => event.stopPropagation()}>
        {children}
      </div>
    </>
  );
}

export function DiningPlaceForm({
  modal,
  busy,
  close,
  save,
  showMessage,
}: {
  modal: Extract<DiningModalState, { kind: "form" }>;
  busy: boolean;
  close: () => void;
  save: (record: BusinessOnlineRecord) => Promise<void>;
  showMessage: (value: string) => void;
}) {
  const isTable = modal.placeKind === "table";
  const [name, setName] = useState(String(modal.place?.name ?? ""));
  const [seats, setSeats] = useState(
    modal.place?.seats ? String(modal.place.seats) : "",
  );
  return (
    <DiningModal close={close}>
      <div className="acf-title">
        {modal.place ? "Tahrirlash" : isTable ? "Yangi stol" : "Yangi xona"}
      </div>
      <div
        style={{
          margin: "12px 2px 4px",
          fontSize: 13,
          color: "var(--koprik-soft)",
          textAlign: "left",
        }}
      >
        {isTable ? "Stol raqami yoki nomi" : "Xona nomi"}
      </div>
      <input
        className="input"
        maxLength={60}
        value={name}
        autoFocus
        placeholder={isTable ? "Masalan: Stol 1" : "Masalan: VIP xona"}
        onChange={(event) => setName(event.target.value)}
      />
      {isTable && (
        <>
          <div
            style={{
              margin: "10px 2px 4px",
              fontSize: 13,
              color: "var(--koprik-soft)",
              textAlign: "left",
            }}
          >
            O'rindiqlar soni
          </div>
          <input
            className="input"
            inputMode="numeric"
            value={seats}
            placeholder="4"
            onChange={(event) => setSeats(event.target.value)}
          />
        </>
      )}
      <div className="acf-btns">
        <button className="acf-cancel" type="button" onClick={close}>
          Bekor qilish
        </button>
        <button
          className="acf-ok"
          type="button"
          disabled={busy}
          onClick={() => {
            const cleanName = name.trim();
            if (!cleanName) {
              showMessage(isTable ? "Stol nomini kiriting." : "Xona nomini kiriting.");
              return;
            }
            void save({
              kind: modal.placeKind,
              name: cleanName,
              seats: isTable ? Number.parseInt(seats || "0", 10) || 0 : 0,
            });
          }}
        >
          Saqlash
        </button>
      </div>
    </DiningModal>
  );
}

export function DiningBookingForm({
  place,
  busy,
  close,
  save,
  showMessage,
}: {
  place: BusinessOnlineRecord;
  busy: boolean;
  close: () => void;
  save: (record: BusinessOnlineRecord) => Promise<void>;
  showMessage: (value: string) => void;
}) {
  const today = todayYmd();
  const [customerName, setCustomerName] = useState("");
  const [phone, setPhone] = useState("");
  const [bookingDate, setBookingDate] = useState(today);
  const [bookingTime, setBookingTime] = useState("");
  const [guests, setGuests] = useState("");
  const [note, setNote] = useState("");
  return (
    <DiningModal close={close}>
      <div className="acf-title">📅 {String(place.name ?? "")} — bron</div>
      <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <input
          className="input"
          value={customerName}
          placeholder="Mijoz ismi"
          onChange={(event) => setCustomerName(event.target.value)}
        />
        <input
          className="input"
          inputMode="tel"
          value={phone}
          placeholder="Telefon raqami"
          onChange={(event) => setPhone(event.target.value)}
        />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 8,
          }}
        >
          <input
            className="input"
            type="date"
            min={today}
            value={bookingDate}
            onChange={(event) => setBookingDate(event.target.value)}
          />
          <input
            className="input"
            type="time"
            value={bookingTime}
            onChange={(event) => setBookingTime(event.target.value)}
          />
        </div>
        <input
          className="input"
          inputMode="numeric"
          value={guests}
          placeholder="Mehmonlar soni"
          onChange={(event) => setGuests(event.target.value)}
        />
        <input
          className="input"
          value={note}
          placeholder="Izoh — ixtiyoriy"
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
      <div className="acf-btns">
        <button className="acf-cancel" type="button" onClick={close}>
          Bekor qilish
        </button>
        <button
          className="acf-ok"
          type="button"
          disabled={busy}
          onClick={() => {
            const customer = customerName.trim();
            if (!customer || !bookingDate || !bookingTime) {
              showMessage("Mijoz ismi, sana va vaqtni kiriting.");
              return;
            }
            void save({
              customer_name: customer,
              phone: phone.trim(),
              booking_date: bookingDate,
              booking_time: bookingTime,
              guests: Number.parseInt(guests || "1", 10) || 1,
              note: note.trim(),
            });
          }}
        >
          Bron qilish
        </button>
      </div>
    </DiningModal>
  );
}

export function DiningConfirm({
  text,
  okText,
  danger = false,
  busy,
  close,
  confirm,
}: {
  text: string;
  okText: string;
  danger?: boolean;
  busy: boolean;
  close: () => void;
  confirm: () => Promise<void>;
}) {
  return (
    <DiningModal close={close}>
      <div className="acf-text">{text}</div>
      <div className="acf-btns">
        <button className="acf-cancel" type="button" onClick={close}>
          Bekor qilish
        </button>
        <button
          className={`acf-ok${danger ? " danger" : ""}`}
          type="button"
          disabled={busy}
          onClick={() => void confirm()}
        >
          {okText}
        </button>
      </div>
    </DiningModal>
  );
}

function todayYmd(): string {
  const today = new Date();
  return [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0"),
  ].join("-");
}
