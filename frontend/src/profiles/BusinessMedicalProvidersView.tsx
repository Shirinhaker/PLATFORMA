import { useEffect, useMemo, useState } from "react";

import type { BusinessOnlineRecord } from "../api/business-online-types";
import { queueUiLabels } from "./business-profile-config";
import {
  AppToast,
  compareName,
  doctorDraft,
  isQueueEnabled,
  itemKey,
  providerItemIds,
  recordId,
  text,
  type DoctorDraft,
  type ProviderProps,
  type Toast,
} from "./BusinessMedicalShared";

export function BusinessMedicalProvidersView({
  direction,
  doctors,
  staff,
  items,
  busy,
  loading = false,
  createDoctor,
  patchDoctor,
  onBackHandlerChange,
  onListBack = null,
}: ProviderProps) {
  const labels = queueUiLabels(direction);
  const [editing, setEditing] = useState<BusinessOnlineRecord | null | undefined>();
  const [draft, setDraft] = useState<DoctorDraft>(() => doctorDraft());
  const [toast, setToast] = useState<Toast>(null);
  const queueItems = useMemo(
    () =>
      items
        .filter(
          (item) => text(item.kind) === "service" && isQueueEnabled(item.queue_enabled),
        )
        .sort(compareName),
    [items],
  );
  const orderedStaff = useMemo(() => [...staff].sort(compareName), [staff]);
  const formOpen = editing !== undefined;

  useEffect(() => {
    if (formOpen) {
      onBackHandlerChange(() => setEditing(undefined), labels.providers);
    } else if (onListBack) {
      onBackHandlerChange(onListBack, labels.providers);
    } else {
      onBackHandlerChange(null);
    }
    return () => onBackHandlerChange(null);
  }, [formOpen, labels.providers, onBackHandlerChange, onListBack]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  function openForm(row: BusinessOnlineRecord | null) {
    setEditing(row);
    setDraft(doctorDraft(row ?? undefined));
    setToast(null);
  }

  function update<K extends keyof DoctorDraft>(key: K, value: DoctorDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function save() {
    const staffId = Number(draft.staff_id || 0);
    if (!staffId || draft.item_ids.length === 0) {
      setToast({
        text: "Xodim va kamida bitta xizmatni tanlang.",
        role: "alert",
      });
      return;
    }
    const record = {
      staff_id: staffId,
      specialty: draft.specialty,
      experience_years: Number(draft.experience_years || 0),
      qualification: draft.qualification,
      work_days: draft.work_days,
      work_start: draft.work_start,
      work_end: draft.work_end,
      avg_minutes: Number(draft.avg_minutes || 20),
      mode: draft.mode,
      room: draft.room,
      bio: draft.bio,
      status: draft.status,
      item_ids: draft.item_ids,
    };
    const saved = editing
      ? await patchDoctor(recordId(editing), record)
      : await createDoctor(record);
    if (!saved) return;
    setEditing(undefined);
    setToast({ text: `${labels.provider} saqlandi.`, role: "status" });
  }

  if (formOpen) {
    const staffId = "medical-doctor-staff";
    return (
      <section className="business-medical-v1656">
        <div className="form-wrap">
          <div className="field">
            <label htmlFor={staffId}>
              Ma'muriyatdagi {labels.provider.toLowerCase()}
            </label>
            <select
              className="input"
              id={staffId}
              value={draft.staff_id}
              disabled={Boolean(editing)}
              onChange={(event) => update("staff_id", event.target.value)}
            >
              {orderedStaff.map((row) => (
                <option key={text(row.id)} value={text(row.id)}>
                  {text(row.name)} · {text(row.profession || "Xodim")}
                </option>
              ))}
            </select>
          </div>
          <TextField
            label="Mutaxassisligi"
            value={draft.specialty}
            setValue={(value) => update("specialty", value)}
          />
          <TextField
            label="Tajribasi (yil)"
            value={draft.experience_years}
            setValue={(value) => update("experience_years", value)}
            type="number"
          />
          <TextField
            label="Malaka/toifasi"
            value={draft.qualification}
            setValue={(value) => update("qualification", value)}
          />
          <TextField
            label="Ish kunlari"
            value={draft.work_days}
            setValue={(value) => update("work_days", value)}
            placeholder="1,2,3,4,5,6"
          />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <input
              aria-label="Ish boshlanishi"
              className="input"
              type="time"
              value={draft.work_start}
              onChange={(event) => update("work_start", event.target.value)}
            />
            <input
              aria-label="Ish tugashi"
              className="input"
              type="time"
              value={draft.work_end}
              onChange={(event) => update("work_end", event.target.value)}
            />
          </div>
          <TextField
            label="O'rtacha qabul (daqiqa)"
            value={draft.avg_minutes}
            setValue={(value) => update("avg_minutes", value)}
            type="number"
          />
          <div className="field">
            <label htmlFor="medical-doctor-mode">Navbat turi</label>
            <select
              className="input"
              id="medical-doctor-mode"
              value={draft.mode}
              onChange={(event) => update("mode", event.target.value)}
            >
              <option value="live">Jonli navbat (tartib raqami)</option>
              <option value="slot">Vaqtli qabul (aniq soatga)</option>
            </select>
          </div>
          <TextField
            label="Xona/joy"
            value={draft.room}
            setValue={(value) => update("room", value)}
          />
          <div className="field">
            <label htmlFor="medical-doctor-bio">{labels.provider} haqida</label>
            <textarea
              className="textarea"
              id="medical-doctor-bio"
              value={draft.bio}
              onChange={(event) => update("bio", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="medical-doctor-status">Holati</label>
            <select
              className="input"
              id="medical-doctor-status"
              value={draft.status}
              onChange={(event) => update("status", event.target.value)}
            >
              <option value="active">Faol</option>
              <option value="inactive">Vaqtincha qabul qilmaydi</option>
            </select>
          </div>
          <div className="field">
            <label>
              {labels.medical
                ? "Qabul qiladigan xizmatlari"
                : "Ko‘rsatadigan xizmatlari"}
            </label>
            <div>
              {queueItems.length > 0 ? (
                queueItems.map((item) => {
                  const id = itemKey(item);
                  const value = (item.public_id ?? item.id ?? "") as number | string;
                  return (
                    <label
                      style={{ display: "flex", gap: 8, margin: "8px 2px" }}
                      key={id}
                    >
                      <input
                        type="checkbox"
                        checked={draft.item_ids.map(text).includes(id)}
                        onChange={(event) =>
                          update(
                            "item_ids",
                            event.target.checked
                              ? [...draft.item_ids, value]
                              : draft.item_ids.filter(
                                  (current) => text(current) !== id,
                                ),
                          )
                        }
                      />
                      {text(item.name)}
                    </label>
                  );
                })
              ) : (
                <div className="idesc">
                  Avval xizmatlar bo‘limida xizmat uchun navbat tizimini yoqing.
                </div>
              )}
            </div>
          </div>
          <button
            type="button"
            className="btn btn-primary btn-block"
            disabled={busy}
            onClick={() => void save()}
          >
            Saqlash
          </button>
        </div>
        <AppToast toast={toast} />
      </section>
    );
  }

  return (
    <section className="business-medical-v1656">
      <div className="form-wrap">
        <button
          type="button"
          className="btn btn-primary btn-block"
          style={{ marginBottom: 10 }}
          onClick={() => openForm(null)}
        >
          + {labels.provider} biriktirish
        </button>
        <div>
          {loading ? (
            <div className="idesc">Yuklanmoqda...</div>
          ) : doctors.length > 0 ? (
            doctors.map((doctor) => (
              <button
                type="button"
                className="panel-card"
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  color: "inherit",
                }}
                key={text(doctor.id)}
                onClick={() => openForm(doctor)}
              >
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <div>
                    <b>{text(doctor.name)}</b>
                    <div className="idesc">
                      {text(
                        doctor.specialty ||
                          doctor.profession ||
                          "Mutaxassislik belgilanmagan",
                      )}{" "}
                      · {text(doctor.room || "Joy belgilanmagan")}
                    </div>
                  </div>
                  <span className="sort-chip">
                    {doctor.status === "active" ? "Faol" : "Qabul qilmaydi"}
                  </span>
                </div>
                <div className="idesc" style={{ marginTop: 7 }}>
                  {providerItemIds(doctor).length} xizmat · {text(doctor.work_start)}–
                  {text(doctor.work_end)} ·{" "}
                  {doctor.mode === "slot" ? "🕐 Vaqtli qabul" : "Jonli navbat"}
                </div>
              </button>
            ))
          ) : (
            <div className="empty">
              <h3>{labels.provider} yo‘q</h3>
              <p>Ma’muriyatdagi faol xodimni xizmatga biriktiring.</p>
            </div>
          )}
        </div>
      </div>
      <AppToast toast={toast} />
    </section>
  );
}

function TextField({
  label,
  value,
  setValue,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string;
  setValue: (value: string) => void;
  type?: "text" | "number";
  placeholder?: string;
}) {
  const id = `medical-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        className="input"
        id={id}
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
    </div>
  );
}
