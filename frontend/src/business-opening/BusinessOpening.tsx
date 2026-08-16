import { useState } from "react";

import type { ApiClient } from "../api/client";
import type { BusinessOpeningRead, BusinessOpeningWrite } from "../api/types";
import { BUSINESS_DIRECTIONS } from "../profiles/business-profile-config";
import "./BusinessOpening.css";

export type BusinessOpeningApi = Pick<ApiClient, "openBusiness">;

type Props = {
  api: BusinessOpeningApi;
  onBack: () => void;
  onSwitch: () => void | Promise<void>;
  onOpened?: (result: BusinessOpeningRead) => void;
};

const EMPTY_FORM: BusinessOpeningWrite = {
  name: "",
  direction: "",
  activity_type: "",
  phone: "",
  address: "",
};

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "So‘rov bajarilmadi.";
}

export function BusinessOpeningV1656({ api, onBack, onSwitch, onOpened }: Props) {
  const [form, setForm] = useState<BusinessOpeningWrite>(EMPTY_FORM);
  const [result, setResult] = useState<BusinessOpeningRead | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function field(name: keyof BusinessOpeningWrite, value: string) {
    setError("");
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const body = {
      name: form.name.trim(),
      direction: form.direction.trim(),
      activity_type: form.activity_type.trim(),
      phone: form.phone.trim(),
      address: form.address.trim(),
    };
    if (!body.name) {
      setError("Biznes nomini kiriting.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const opened = await api.openBusiness(body);
      setResult(opened);
      onOpened?.(opened);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <main className="business-opening-v1656">
        <section className="business-opening-v1656__card business-opening-v1656__success">
          <span className="business-opening-v1656__success-icon" aria-hidden="true">
            ✓
          </span>
          <h1>Biznes ochildi! ✅</h1>
          <p>
            Biznes kabinetingiz uchun alohida login va parol. Saqlab qo'ying —
            Telegramingizga ham yuborildi.
          </p>
          <dl className="business-opening-v1656__credentials">
            <div>
              <dt>🏪 Biznes login</dt>
              <dd>{result.biz_login}</dd>
            </div>
            <div>
              <dt>🔐 Biznes parol</dt>
              <dd>{result.biz_password}</dd>
            </div>
          </dl>
          <button
            type="button"
            className="business-opening-v1656__primary"
            onClick={() => void onSwitch()}
          >
            Biznes kabinetga o'tish
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="business-opening-v1656">
      <section className="business-opening-v1656__card">
        <button type="button" className="business-opening-v1656__back" onClick={onBack}>
          ← Kabinetga qaytish
        </button>
        <header>
          <span aria-hidden="true">🏪</span>
          <div>
            <h1>Biznes ochish</h1>
            <p>
              Biznes ma'lumotlaringizni to'ldiring. Biznes profil shu akkauntingizga
              qo'shiladi — oddiy va biznes kabinet o'rtasida almashtirib turasiz.
            </p>
          </div>
        </header>

        <form onSubmit={submit} noValidate>
          <label>
            <span>Biznes nomi *</span>
            <input
              value={form.name}
              onChange={(event) => field("name", event.target.value)}
              placeholder="Masalan: Anvar Market"
              maxLength={120}
              autoComplete="organization"
              disabled={busy}
            />
          </label>
          <div className="business-opening-v1656__row">
            <label>
              <span>Yo'nalish</span>
              <select
                value={form.direction}
                onChange={(event) => field("direction", event.target.value)}
                disabled={busy}
              >
                <option value="">Tanlang</option>
                {BUSINESS_DIRECTIONS.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.icon} {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Faoliyat turi</span>
              <input
                value={form.activity_type}
                onChange={(event) => field("activity_type", event.target.value)}
                placeholder="Masalan: Oziq-ovqat do'koni"
                maxLength={120}
                disabled={busy}
              />
            </label>
          </div>
          <div className="business-opening-v1656__row">
            <label>
              <span>Telefon</span>
              <input
                value={form.phone}
                onChange={(event) => field("phone", event.target.value)}
                placeholder="+998 __ ___ __ __"
                maxLength={32}
                inputMode="tel"
                autoComplete="tel"
                disabled={busy}
              />
            </label>
            <label>
              <span>Manzil</span>
              <input
                value={form.address}
                onChange={(event) => field("address", event.target.value)}
                placeholder="Tuman, mahalla, ko'cha"
                maxLength={300}
                autoComplete="street-address"
                disabled={busy}
              />
            </label>
          </div>
          {error && (
            <p className="business-opening-v1656__error" role="alert">
              {error}
            </p>
          )}
          <button
            type="submit"
            className="business-opening-v1656__primary"
            disabled={busy}
          >
            {busy ? "Ochilmoqda..." : "Biznes ochish"}
          </button>
        </form>
      </section>
    </main>
  );
}
