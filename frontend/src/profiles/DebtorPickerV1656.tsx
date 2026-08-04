import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { Debtor } from "../api/types";
import { money } from "./business-profile-config";
import "./DebtLedgerV1656.css";


export type DebtorPickerApi = Pick<ApiClient, "getDebtors" | "createDebtor">;

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

export function DebtorPickerV1656({
  api,
  title = "Qarzga rasmiylashtirish",
  onCancel,
  onSelect,
}: {
  api: DebtorPickerApi;
  title?: string;
  onCancel: () => void;
  onSelect: (debtorId: number) => void;
}) {
  const [rows, setRows] = useState<Debtor[]>([]);
  const [selected, setSelected] = useState(0);
  const [isNew, setIsNew] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setBusy(true);
    api.getDebtors()
      .then((debtors) => {
        if (!active) return;
        setRows(debtors);
        const first = debtors[0];
        if (first) setSelected(first.id);
        else setIsNew(true);
      })
      .catch((reason) => { if (active) setError(message(reason)); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [api]);

  async function submit() {
    if (!isNew && selected > 0) {
      onSelect(selected);
      return;
    }
    if (!name.trim()) {
      setError("Qarzdor ismini kiriting.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const created = await api.createDebtor({
        name: name.trim(),
        phone: phone.trim(),
        note: "",
        due: "",
        initial_debt: 0,
      });
      onSelect(created.id);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="debt-v1656__modal-back" role="presentation">
      <section className="debt-v1656__modal" role="dialog" aria-modal="true" aria-label={title}>
        <h2>{title}</h2>
        {error ? <p className="debt-v1656__error" role="alert">{error}</p> : null}
        {rows.length ? (
          <label>Qarzdor<select
            value={isNew ? 0 : selected}
            onChange={(event) => {
              const value = Number(event.target.value);
              setIsNew(value === 0);
              setSelected(value);
            }}
          >
            <option value={0}>Yangi qarzdor</option>
            {rows.map((debtor) => (
              <option key={debtor.id} value={debtor.id}>
                {debtor.name} · qarzi {money(debtor.balance)}
              </option>
            ))}
          </select></label>
        ) : null}
        {isNew ? (
          <div className="debt-v1656__modal-fields">
            <label>Yangi qarzdor ismi<input
              value={name}
              placeholder="Ism va familiya"
              maxLength={160}
              onChange={(event) => setName(event.target.value)}
            /></label>
            <label>Telefon — ixtiyoriy<input
              value={phone}
              placeholder="+998 ..."
              maxLength={40}
              onChange={(event) => setPhone(event.target.value)}
            /></label>
          </div>
        ) : null}
        <div className="debt-v1656__modal-actions">
          <button type="button" disabled={busy} onClick={onCancel}>Bekor qilish</button>
          <button type="button" disabled={busy} onClick={submit}>Qarzga yozish</button>
        </div>
      </section>
    </div>
  );
}
