import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { TaxiRide } from "../api/types";

export function MyRidesV1656({
  api,
  onBack,
}: {
  api: Partial<Pick<ApiClient, "getMyTaxiRides">>;
  onBack(): void;
}) {
  const [rides, setRides] = useState<TaxiRide[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void api
      .getMyTaxiRides?.()
      .then((value) => {
        if (active) setRides(value.rides);
      })
      .catch((reason: unknown) => {
        if (active)
          setError(reason instanceof Error ? reason.message : "Yuklab bo'lmadi.");
      });
    return () => {
      active = false;
    };
  }, [api]);
  return (
    <main className="profile-shell">
      <header className="profile-heading">
        <h1>Taxi va dostavka buyurtmalarim</h1>
        <button className="button-secondary" type="button" onClick={onBack}>
          Kabinetga qaytish
        </button>
      </header>
      {error ? <p role="alert">{error}</p> : null}
      {!error && !rides.length ? (
        <div className="empty">
          <h3>Hozircha zakaz yo'q</h3>
        </div>
      ) : (
        rides.map((ride) => (
          <div className="panel-card" key={ride.id}>
            <b>{ride.kind === "dostavka" ? "📦 Dostavka" : "🚖 Taxi"}</b>
            <div className="list-sub">🟢 {ride.from_addr || "Boshlanish"}</div>
            <div className="list-sub">
              {ride.ozim
                ? "🗣 Manzilni og'zaki aytadi"
                : `🔴 ${ride.to_addr || "Manzil"}`}
            </div>
            <div className="list-sub">Holat: {ride.status}</div>
          </div>
        ))
      )}
    </main>
  );
}
