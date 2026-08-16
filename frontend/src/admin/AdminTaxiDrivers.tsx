import { useCallback, useEffect, useState } from "react";

import type { AdminApiClient, AdminTaxiDriver } from "./admin-client";

export type AdminTaxiApi = Pick<AdminApiClient, "taxiDrivers" | "topupTaxiDriver">;

export function AdminTaxiDrivers({ api }: { api: AdminTaxiApi }) {
  const [drivers, setDrivers] = useState<AdminTaxiDriver[]>([]);
  const [selected, setSelected] = useState(0);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const rows = await api.taxiDrivers();
      setDrivers(rows);
      setSelected((current) => current || rows[0]?.id || 0);
      setFailed(false);
    } catch (error) {
      setFailed(true);
      setMessage(error instanceof Error ? error.message : "Yuklab bo‘lmadi.");
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  async function topup() {
    const value = Number(amount);
    if (!selected) {
      setFailed(true);
      setMessage("Haydovchini tanlang.");
      return;
    }
    if (!Number.isInteger(value) || value <= 0) {
      setFailed(true);
      setMessage("Summani to‘g‘ri kiriting.");
      return;
    }
    if (reason.trim().length < 3) {
      setFailed(true);
      setMessage("Audit uchun sababni kiriting.");
      return;
    }
    setBusy(true);
    try {
      await api.topupTaxiDriver(selected, value, reason.trim());
      setFailed(false);
      setMessage(`Balans qo‘shildi: +${value.toLocaleString("uz-UZ")} so‘m`);
      setAmount("");
      setReason("");
      await load();
    } catch (error) {
      setFailed(true);
      setMessage(error instanceof Error ? error.message : "So‘rov bajarilmadi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page active">
      <div className="page-head">
        <div>
          <div className="eyebrow">TAXI VA DOSTAVKA</div>
          <h1>Haydovchi balanslari</h1>
        </div>
      </div>
      <div className="panel admin-taxi-topup">
        <label htmlFor="taxiDriver">Haydovchi</label>
        <select
          id="taxiDriver"
          value={selected}
          onChange={(event) => setSelected(Number(event.currentTarget.value))}
        >
          {!drivers.length ? (
            <option value={0}>Haydovchi yo‘q</option>
          ) : (
            drivers.map((driver) => (
              <option key={driver.id} value={driver.id}>
                {driver.name || "—"} · {driver.balance.toLocaleString("uz-UZ")} so‘m
              </option>
            ))
          )}
        </select>
        <label htmlFor="taxiAmount">Summa (so‘m)</label>
        <input
          id="taxiAmount"
          type="number"
          inputMode="numeric"
          min={1}
          max={10_000_000}
          value={amount}
          onChange={(event) => setAmount(event.currentTarget.value)}
        />
        <label htmlFor="taxiReason">Sabab (audit jurnaliga yoziladi)</label>
        <input
          id="taxiReason"
          value={reason}
          onChange={(event) => setReason(event.currentTarget.value)}
          placeholder="Masalan: bank o‘tkazmasi tasdiqlandi"
        />
        <button
          disabled={busy || !drivers.length}
          type="button"
          onClick={() => void topup()}
        >
          Balansni qo‘shish
        </button>
        {message ? (
          <div
            className={`message${failed ? " error" : ""}`}
            role={failed ? "alert" : "status"}
          >
            {message}
          </div>
        ) : null}
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Haydovchi</th>
              <th>Telefon</th>
              <th>Xizmat</th>
              <th>Holat</th>
              <th>Balans</th>
            </tr>
          </thead>
          <tbody>
            {drivers.map((driver) => (
              <tr key={driver.id}>
                <td>{driver.name}</td>
                <td>{driver.phone || "—"}</td>
                <td>{driver.service}</td>
                <td>{driver.available ? "Bo‘sh" : "Band"}</td>
                <td>{driver.balance.toLocaleString("uz-UZ")} so‘m</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
