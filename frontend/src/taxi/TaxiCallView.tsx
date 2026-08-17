import type { Dispatch, RefObject, SetStateAction } from "react";

import type { TaxiKind, TaxiRide } from "../api/types";

type Phase = "form" | "search" | "found";
type Point = { latitude: number; longitude: number };

function money(value: number) {
  return Math.round(value).toLocaleString("uz-UZ").replace(/,/g, " ");
}

function statusLabel(ride: TaxiRide) {
  if (ride.kind === "dostavka") {
    if (
      [
        "arrived",
        "ongoing",
        "in_delivery",
        "arrived_customer",
        "delivered_waiting_customer",
      ].includes(ride.status)
    ) {
      return "📦 Dostavka olindi — yetkazilmoqda";
    }
    return "🚚 Dostavkachi buyurtmani olish uchun yo'lda";
  }
  if (ride.status === "arrived") return "📍 Haydovchi yetib keldi!";
  if (ride.status === "ongoing") return "🛣️ Safardasiz";
  return "🚗 Haydovchi yo'lda kelmoqda";
}

export function TaxiCallView({
  phase,
  ride,
  cancel,
  onBack,
  ozim,
  estimatedPrice,
  distance,
  kind,
  setKind,
  pickMode,
  fromAddr,
  choosePick,
  requestCurrentLocation,
  to,
  toAddr,
  setOzim,
  setTo,
  setToAddr,
  carType,
  setCarType,
  cargo,
  setCargo,
  error,
  submit,
  mapHost,
  district,
}: {
  phase: Phase;
  ride: TaxiRide | null;
  cancel(): Promise<void>;
  onBack(): void;
  ozim: boolean;
  estimatedPrice: number | null;
  distance: number | null;
  kind: TaxiKind;
  setKind: Dispatch<SetStateAction<TaxiKind>>;
  pickMode: "from" | "to";
  fromAddr: string;
  choosePick(mode: "from" | "to"): void;
  requestCurrentLocation(force: boolean): void;
  to: Point | null;
  toAddr: string;
  setOzim: Dispatch<SetStateAction<boolean>>;
  setTo: Dispatch<SetStateAction<Point | null>>;
  setToAddr: Dispatch<SetStateAction<string>>;
  carType: string;
  setCarType: Dispatch<SetStateAction<string>>;
  cargo: string;
  setCargo: Dispatch<SetStateAction<string>>;
  error: string;
  submit(): Promise<void>;
  mapHost: RefObject<HTMLDivElement | null>;
  district: string;
}) {
  return (
    <main className="screen active taxi-call-v1656" data-screen="taxi-call">
      <div className="taxi-call-v1656__shell">
        <section className="call-panel" id="callPanel">
          {phase === "search" ? (
            <div className="panel-card taxi-call-v1656__centered">
              <div className="spinner" />
              <b>Haydovchi qidirilmoqda...</b>
              <div className="list-sub">
                Yaqin atrofdagi bo'sh haydovchilarga yuborildi
              </div>
              <button
                className="btn btn-outline btn-block"
                type="button"
                onClick={cancel}
              >
                Bekor qilish
              </button>
            </div>
          ) : phase === "found" && ride ? (
            <>
              <div className="panel-card taxi-call-v1656__centered">
                <b>{statusLabel(ride)}</b>
                <button
                  aria-label="Bekor qilish"
                  className="panel-x"
                  type="button"
                  onClick={cancel}
                >
                  ✕
                </button>
              </div>
              <DriverCard ride={ride} onCancel={cancel} />
            </>
          ) : (
            <div className="panel-card">
              <button
                aria-label="Yopish"
                className="panel-x"
                type="button"
                onClick={onBack}
              >
                ✕
              </button>
              <div className="call-price">
                {ozim ? (
                  "Manzil og'zaki aytiladi — narx bosib o'tilgan masofa bo'yicha, safar oxirida 🧭"
                ) : estimatedPrice ? (
                  <>
                    <strong>~{money(estimatedPrice)} so'm</strong>
                    <br />
                    <small>{distance?.toFixed(1)} km · naqd, haydovchiga</small>
                  </>
                ) : to ? (
                  "Narx hisoblanmoqda..."
                ) : (
                  "Boradigan joyni belgilang — narx shu yerda chiqadi"
                )}
              </div>
              <div className="sort-row taxi-call-v1656__tabs">
                <button
                  className={`sort-chip${kind === "taxi" ? " on" : ""}`}
                  type="button"
                  onClick={() => setKind("taxi")}
                >
                  🚖 Taxi
                </button>
                <button
                  className={`sort-chip${kind === "dostavka" ? " on" : ""}`}
                  type="button"
                  onClick={() => setKind("dostavka")}
                >
                  📦 Dostavka
                </button>
              </div>
              <div className="field">
                <span className="taxi-call-v1656__field-label">
                  Qayerdan{pickMode === "from" ? <em> — xaritani suring</em> : null}
                </span>
                <div className="taxi-call-v1656__from-row">
                  <button
                    className={`input taxi-call-v1656__input-button${pickMode === "from" ? " is-active" : ""}`}
                    type="button"
                    onClick={() => choosePick("from")}
                  >
                    {fromAddr}
                  </button>
                  <button
                    aria-label="Joriy joylashuvni olish"
                    className="taxi-call-v1656__gps"
                    type="button"
                    onClick={() => requestCurrentLocation(true)}
                  >
                    📍 GPS
                  </button>
                </div>
              </div>
              <div className="field">
                <span className="taxi-call-v1656__field-label">
                  Qayerga
                  {pickMode === "to" && !ozim ? <em> — xaritani suring</em> : null}
                </span>
                <button
                  disabled={ozim}
                  className={`input taxi-call-v1656__input-button${pickMode === "to" && !ozim ? " is-active" : ""}`}
                  type="button"
                  onClick={() => choosePick("to")}
                >
                  {toAddr || "Bu maydonni tanlab xaritani suring"}
                </button>
              </div>
              <button
                className={`sort-chip taxi-call-v1656__say-it${ozim ? " on" : ""}`}
                type="button"
                onClick={() => {
                  setOzim((current) => !current);
                  setTo(null);
                  setToAddr("");
                }}
              >
                🗣 O'zim aytaman
              </button>
              {kind === "dostavka" ? (
                <>
                  <fieldset className="field taxi-call-v1656__vehicle-field">
                    <legend>Mashina turi</legend>
                    <div className="taxi-call-v1656__vehicle-options">
                      {(["Yengil yuk", "Katta yuk"] as const).map((option) => (
                        <button
                          aria-pressed={carType === option}
                          className={`sort-chip${carType === option ? " on" : ""}`}
                          key={option}
                          type="button"
                          onClick={() => setCarType(option)}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  </fieldset>
                  <label className="field taxi-call-v1656__cargo-field">
                    <span className="taxi-call-v1656__field-label">Yuk turi</span>
                    <input
                      aria-label="Yuk turi"
                      className="input"
                      placeholder="Masalan: mebel, quti, texnika"
                      value={cargo}
                      onChange={(event) => setCargo(event.currentTarget.value)}
                    />
                  </label>
                </>
              ) : null}
              {error ? (
                <p className="elon-hint" role="alert">
                  {error}
                </p>
              ) : null}
              <button
                className="btn btn-primary btn-block"
                type="button"
                onClick={() => void submit()}
              >
                Zakaz qilish
              </button>
            </div>
          )}
        </section>
        <div className="taxi-call-v1656__map-wrap">
          <div className="taxi-call-v1656__map" id="taxiCallMap" ref={mapHost} />
          {phase === "form" ? (
            <div className="taxi-call-v1656__center-pin">📍</div>
          ) : null}
          {district ? (
            <div className="taxi-call-v1656__map-chip">⌾ {district}</div>
          ) : null}
          <button
            aria-label="Taxi oynasidan chiqish"
            className="taxi-call-v1656__map-action"
            type="button"
            onClick={onBack}
          >
            🚖
          </button>
        </div>
      </div>
    </main>
  );
}

function DriverCard({ ride, onCancel }: { ride: TaxiRide; onCancel(): void }) {
  const driver = ride.driver;
  const canCancel =
    ride.kind === "dostavka"
      ? ride.status === "accepted"
      : ["accepted", "arrived"].includes(ride.status);
  const cost = ride.ozim ? ride.final_price : ride.price;
  return (
    <div className="panel-card taxi-call-v1656__driver-card" id="driverCard">
      <div className="taxi-call-v1656__driver-row">
        <div className="cab-logo">{ride.kind === "dostavka" ? "📦" : "🚖"}</div>
        <div>
          <b>{driver?.name || "Haydovchi"}</b>
          <div className="list-sub">
            {[driver?.car_color, driver?.car_model].filter(Boolean).join(" ") ||
              "Mashina"}
            {driver?.car_plate ? ` · ${driver.car_plate}` : ""}
          </div>
          {cost ? (
            <div className="list-sub taxi-call-v1656__price">
              💰 ~{money(cost)} so'm (naqd)
            </div>
          ) : null}
          {ride.ozim ? <div className="list-sub">Manzilni og'zaki aytasiz</div> : null}
        </div>
      </div>
      <div className="taxi-call-v1656__actions">
        {driver?.phone ? (
          <a className="btn btn-primary" href={`tel:${driver.phone}`}>
            📞 Qo'ng'iroq
          </a>
        ) : null}
        {canCancel ? (
          <button className="btn btn-outline" type="button" onClick={onCancel}>
            Bekor qilish
          </button>
        ) : null}
      </div>
    </div>
  );
}
