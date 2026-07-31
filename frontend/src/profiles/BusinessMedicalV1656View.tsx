import { useEffect, useMemo, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import { queueUiLabels } from "./business-profile-config";
import "./BusinessMedicalV1656View.css";


type BackHandlerChange = (
  handler: (() => void) | null,
  title?: string,
) => void;

type ProviderProps = {
  direction: string;
  doctors: BusinessOnlineRecord[];
  staff: BusinessOnlineRecord[];
  items: BusinessOnlineRecord[];
  busy: boolean;
  createDoctor: (record: BusinessOnlineRecord) => Promise<boolean>;
  patchDoctor: (
    id: number | string,
    patch: BusinessOnlineRecord,
  ) => Promise<boolean>;
  onBackHandlerChange: BackHandlerChange;
  onListBack?: (() => void) | null;
};

type QueueProps = {
  direction: string;
  rows: BusinessOnlineRecord[];
  doctors: BusinessOnlineRecord[];
  staff: BusinessOnlineRecord[];
  items: BusinessOnlineRecord[];
  busy: boolean;
  createDoctor: ProviderProps["createDoctor"];
  patchDoctor: ProviderProps["patchDoctor"];
  action: (
    resource: BusinessOnlineResource,
    name: string,
    id?: number | string,
    payload?: BusinessOnlineRecord,
  ) => Promise<BusinessOnlineRecord | null>;
  refresh: (...resources: BusinessOnlineResource[]) => Promise<void>;
  onBackHandlerChange: BackHandlerChange;
};

type DoctorDraft = {
  staff_id: string;
  specialty: string;
  experience_years: string;
  qualification: string;
  work_days: string;
  work_start: string;
  work_end: string;
  avg_minutes: string;
  mode: string;
  room: string;
  bio: string;
  status: string;
  item_ids: number[];
};

type Toast = { text: string; role: "alert" | "status" } | null;
type QueueModal =
  | { kind: "offline"; patient: string; phone: string; itemId: string; staffId: string }
  | { kind: "swap"; first: string; second: string }
  | { kind: "cancel"; queue: BusinessOnlineRecord }
  | null;

const STATUS_LABELS: Record<string, string> = {
  waiting: "Kutilmoqda",
  called: "Chaqirildi",
  in_service: "Qabulda",
  done: "Yakunlandi",
  no_show: "Kelmadi",
  cancelled: "Bekor qilindi",
  skipped: "O'tkazib yuborildi",
};

function text(value: unknown) {
  return String(value ?? "");
}

function number(value: unknown) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function recordId(row: BusinessOnlineRecord) {
  return (row.id ?? "") as number | string;
}

function compareName(left: BusinessOnlineRecord, right: BusinessOnlineRecord) {
  const leftName = text(left.name);
  const rightName = text(right.name);
  return leftName < rightName ? -1 : leftName > rightName ? 1 : 0;
}

function isQueueEnabled(value: unknown) {
  return value === true || ["1", "true", "on"].includes(
    text(value).toLowerCase(),
  );
}

function localIsoDate() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function doctorDraft(row?: BusinessOnlineRecord): DoctorDraft {
  return {
    staff_id: text(row?.staff_id),
    specialty: text(row?.specialty),
    experience_years: text(row?.experience_years ?? 0),
    qualification: text(row?.qualification),
    work_days: text(row?.work_days || "1,2,3,4,5,6"),
    work_start: text(row?.work_start || "08:00"),
    work_end: text(row?.work_end || "17:00"),
    avg_minutes: text(row?.avg_minutes || 20),
    mode: text(row?.mode || "live"),
    room: text(row?.room),
    bio: text(row?.bio),
    status: text(row?.status || "active"),
    item_ids: Array.isArray(row?.item_ids)
      ? row.item_ids.map(number).filter(Boolean)
      : [],
  };
}

function AppToast({ toast }: { toast: Toast }) {
  if (!toast) return null;
  return (
    <div className="app-toast on" role={toast.role}>
      {toast.text}
    </div>
  );
}

function ModalFrame({
  title,
  children,
  close,
  save,
  okText = "Saqlash",
  danger = false,
  busy = false,
}: {
  title?: string;
  children: ReactNode;
  close: () => void;
  save: () => void;
  okText?: string;
  danger?: boolean;
  busy?: boolean;
}) {
  return (
    <>
      <div
        className="app-modal-back on"
        onClick={close}
      />
      <div className="app-confirm on" role="dialog" aria-modal="true">
        {title ? <div className="acf-title">{title}</div> : null}
        {children}
        <div className="acf-btns">
          <button type="button" className="acf-cancel" onClick={close}>
            Bekor qilish
          </button>
          <button
            type="button"
            className={`acf-ok${danger ? " danger" : ""}`}
            onClick={save}
            disabled={busy}
          >
            {okText}
          </button>
        </div>
      </div>
    </>
  );
}

function ModalField({
  id,
  label,
  value,
  onChange,
  numeric = false,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  numeric?: boolean;
}) {
  return (
    <>
      <div style={{
        textAlign: "left",
        margin: "10px 2px 4px",
        fontSize: 13,
        color: "var(--koprik-soft, #6b7280)",
      }}>
        {label}
      </div>
      <input
        className="input"
        id={id}
        aria-label={label}
        type="text"
        inputMode={numeric ? "numeric" : undefined}
        value={value}
        onChange={(event) => onChange(
          numeric ? event.target.value.replace(/\D/g, "") : event.target.value,
        )}
      />
    </>
  );
}

export function BusinessMedicalProvidersV1656View({
  direction,
  doctors,
  staff,
  items,
  busy,
  createDoctor,
  patchDoctor,
  onBackHandlerChange,
  onListBack = null,
}: ProviderProps) {
  const labels = queueUiLabels(direction);
  const [editing, setEditing] = useState<BusinessOnlineRecord | null | undefined>();
  const [draft, setDraft] = useState<DoctorDraft>(() => doctorDraft());
  const [toast, setToast] = useState<Toast>(null);
  const queueItems = useMemo(() => items.filter((item) => (
    text(item.kind) === "service" && isQueueEnabled(item.queue_enabled)
  )).sort(compareName), [items]);
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
          <TextField label="Mutaxassisligi" value={draft.specialty} setValue={(value) => update("specialty", value)} />
          <TextField label="Tajribasi (yil)" value={draft.experience_years} setValue={(value) => update("experience_years", value)} type="number" />
          <TextField label="Malaka/toifasi" value={draft.qualification} setValue={(value) => update("qualification", value)} />
          <TextField label="Ish kunlari" value={draft.work_days} setValue={(value) => update("work_days", value)} placeholder="1,2,3,4,5,6" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <input aria-label="Ish boshlanishi" className="input" type="time" value={draft.work_start} onChange={(event) => update("work_start", event.target.value)} />
            <input aria-label="Ish tugashi" className="input" type="time" value={draft.work_end} onChange={(event) => update("work_end", event.target.value)} />
          </div>
          <TextField label="O'rtacha qabul (daqiqa)" value={draft.avg_minutes} setValue={(value) => update("avg_minutes", value)} type="number" />
          <div className="field">
            <label htmlFor="medical-doctor-mode">Navbat turi</label>
            <select className="input" id="medical-doctor-mode" value={draft.mode} onChange={(event) => update("mode", event.target.value)}>
              <option value="live">Jonli navbat (tartib raqami)</option>
              <option value="slot">Vaqtli qabul (aniq soatga)</option>
            </select>
          </div>
          <TextField label="Xona/joy" value={draft.room} setValue={(value) => update("room", value)} />
          <div className="field">
            <label htmlFor="medical-doctor-bio">{labels.provider} haqida</label>
            <textarea className="textarea" id="medical-doctor-bio" value={draft.bio} onChange={(event) => update("bio", event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="medical-doctor-status">Holati</label>
            <select className="input" id="medical-doctor-status" value={draft.status} onChange={(event) => update("status", event.target.value)}>
              <option value="active">Faol</option>
              <option value="inactive">Vaqtincha qabul qilmaydi</option>
            </select>
          </div>
          <div className="field">
            <label>{labels.medical ? "Qabul qiladigan xizmatlari" : "Ko‘rsatadigan xizmatlari"}</label>
            <div>
              {queueItems.length > 0 ? queueItems.map((item) => {
                const id = number(item.id);
                return (
                  <label style={{ display: "flex", gap: 8, margin: "8px 2px" }} key={id}>
                    <input
                      type="checkbox"
                      checked={draft.item_ids.includes(id)}
                      onChange={(event) => update(
                        "item_ids",
                        event.target.checked
                          ? [...draft.item_ids, id]
                          : draft.item_ids.filter((value) => value !== id),
                      )}
                    />
                    {text(item.name)}
                  </label>
                );
              }) : (
                <div className="idesc">
                  Avval xizmatlar bo‘limida xizmat uchun navbat tizimini yoqing.
                </div>
              )}
            </div>
          </div>
          <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={() => void save()}>
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
          {doctors.length > 0 ? doctors.map((doctor) => (
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
                    {text(doctor.specialty || doctor.profession || "Mutaxassislik belgilanmagan")} · {text(doctor.room || "Joy belgilanmagan")}
                  </div>
                </div>
                <span className="sort-chip">
                  {doctor.status === "active" ? "Faol" : "Qabul qilmaydi"}
                </span>
              </div>
              <div className="idesc" style={{ marginTop: 7 }}>
                {Array.isArray(doctor.item_ids) ? doctor.item_ids.length : 0} xizmat · {text(doctor.work_start)}–{text(doctor.work_end)} · {doctor.mode === "slot" ? "🕐 Vaqtli qabul" : "Jonli navbat"}
              </div>
            </button>
          )) : (
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

export function BusinessMedicalQueueV1656View({
  direction,
  rows,
  doctors,
  staff,
  items,
  busy,
  createDoctor,
  patchDoctor,
  action,
  refresh,
  onBackHandlerChange,
}: QueueProps) {
  const labels = queueUiLabels(direction);
  const [date, setDate] = useState(localIsoDate);
  const [modal, setModal] = useState<QueueModal>(null);
  const [toast, setToast] = useState<Toast>(null);
  const [providersOpen, setProvidersOpen] = useState(false);
  const queueItems = items.filter((item) => (
    text(item.kind) === "service" && isQueueEnabled(item.queue_enabled)
  )).sort(compareName);
  const staffById = new Map(staff.map((row) => [text(row.id), row]));
  const visibleRows = rows.filter((row) => text(row.queue_date) === date);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  useEffect(() => {
    if (!providersOpen) onBackHandlerChange(null);
  }, [onBackHandlerChange, providersOpen]);

  function providersForItem(itemId: string) {
    return doctors.filter((doctor) => (
      doctor.status === "active"
      && Array.isArray(doctor.item_ids)
      && doctor.item_ids.map(text).includes(itemId)
      && staffById.has(text(doctor.staff_id))
    ));
  }

  function openOffline() {
    const providerCount = queueItems.reduce(
      (total, item) => total + providersForItem(text(item.id)).length,
      0,
    );
    if (queueItems.length === 0 || providerCount === 0) {
      setToast({
        text: `Avval navbat yoqilgan xizmatga ${labels.provider.toLowerCase()} biriktiring.`,
        role: "alert",
      });
      return;
    }
    setModal({ kind: "offline", patient: "", phone: "", itemId: "", staffId: "" });
  }

  async function setStatus(row: BusinessOnlineRecord, status: string) {
    const saved = await action(
      "medical_queue",
      "set_status",
      recordId(row),
      { status },
    );
    if (saved) await refresh("medical_queue");
  }

  async function saveOffline(current: Extract<QueueModal, { kind: "offline" }>) {
    if (!current.patient.trim()) {
      setToast({ text: `${labels.customer} ism-familiyasi kiritilishi shart.`, role: "alert" });
      return;
    }
    if (!current.itemId) {
      setToast({ text: "Xizmat tanlanishi shart.", role: "alert" });
      return;
    }
    if (!current.staffId) {
      setToast({ text: `${labels.provider} tanlanishi shart.`, role: "alert" });
      return;
    }
    const saved = await action("medical_queue", "offline_add", undefined, {
      patient_name: current.patient.trim(),
      phone: current.phone.trim(),
      item_id: Number(current.itemId),
      staff_id: Number(current.staffId),
      queue_date: date,
    });
    if (!saved) return;
    setModal(null);
    setToast({ text: `Navbat: ${text(saved.queue_code)}`, role: "status" });
    await refresh("medical_queue");
  }

  async function saveSwap(current: Extract<QueueModal, { kind: "swap" }>) {
    if (!current.first) {
      setToast({ text: "Birinchi navbat ID kiritilishi shart.", role: "alert" });
      return;
    }
    if (!current.second) {
      setToast({ text: "Ikkinchi navbat ID kiritilishi shart.", role: "alert" });
      return;
    }
    const saved = await action(
      "medical_queue",
      "swap",
      Number(current.first),
      { other_queue_id: Number(current.second) },
    );
    if (!saved) return;
    setModal(null);
    setToast({ text: "Navbatlar almashtirildi.", role: "status" });
    await refresh("medical_queue");
  }

  if (providersOpen) {
    return (
      <BusinessMedicalProvidersV1656View
        direction={direction}
        doctors={doctors}
        staff={staff}
        items={items}
        busy={busy}
        createDoctor={createDoctor}
        patchDoctor={patchDoctor}
        onBackHandlerChange={onBackHandlerChange}
        onListBack={() => setProvidersOpen(false)}
      />
    );
  }

  return (
    <section className="business-medical-v1656">
      <div className="form-wrap">
        <div className="panel-card">
          <b>🏥 Yagona navbat</b>
          <div className="idesc">
            Onlayn va oflayn {labels.customer.toLowerCase()}lar bitta ketma-ketlikda.
          </div>
        </div>
        <input
          aria-label="Navbat sanasi"
          className="input"
          type="date"
          style={{ marginBottom: 10 }}
          value={date}
          onChange={(event) => setDate(event.target.value)}
        />
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <button type="button" className="btn btn-primary" style={{ flex: 1 }} onClick={openOffline}>
            + Oflayn navbat
          </button>
          <button type="button" className="btn btn-outline" style={{ flex: 1 }} onClick={() => setProvidersOpen(true)}>
            {labels.providers}
          </button>
        </div>
        <button
          type="button"
          className="btn btn-outline btn-block"
          style={{ marginBottom: 10 }}
          onClick={() => setModal({ kind: "swap", first: "", second: "" })}
        >
          ↔ Navbatlarni almashtirish
        </button>
        <div>
          {visibleRows.length > 0 ? visibleRows.map((row) => (
            <div className="panel-card" key={text(row.id)}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <div>
                  <b>{text(row.queue_code)} · {text(row.patient_name)}</b>
                  <div className="idesc">
                    {text(row.service_name)} · {text(row.doctor_name)} · {row.source === "online" ? "Onlayn" : "Oflayn"}{row.slot_time ? ` · 🕐 ${text(row.slot_time)}` : ""}
                  </div>
                </div>
                <span className="sort-chip">{STATUS_LABELS[text(row.status)]}</span>
              </div>
              <div style={{ display: "flex", gap: 5, marginTop: 9, flexWrap: "wrap" }}>
                <button type="button" className="mini-btn" onClick={() => void setStatus(row, "called")}>Chaqirish</button>
                <button type="button" className="mini-btn" onClick={() => void setStatus(row, "in_service")}>Qabul</button>
                <button type="button" className="mini-btn" onClick={() => void setStatus(row, "done")}>Yakunlash</button>
                <button type="button" className="mini-btn" onClick={() => void setStatus(row, "no_show")}>Kelmadi</button>
                <button type="button" className="mini-btn" style={{ borderColor: "#DC2626", color: "#DC2626" }} onClick={() => setModal({ kind: "cancel", queue: row })}>Bekor qilish</button>
              </div>
            </div>
          )) : (
            <div className="empty">
              <h3>Navbat yo‘q</h3>
              <p>Onlayn yoki oflayn navbat qo‘shing.</p>
            </div>
          )}
        </div>
      </div>
      <AppToast toast={toast} />
      {modal?.kind === "cancel" ? (
        <ModalFrame
          close={() => setModal(null)}
          save={() => {
            const row = modal.queue;
            setModal(null);
            void setStatus(row, "cancelled");
          }}
          okText="Bekor qilish"
          danger
          busy={busy}
        >
          <div className="acf-text">
            Bu navbat bekor qilinsinmi? Foydalanuvchiga xabar yuboriladi.
          </div>
        </ModalFrame>
      ) : null}
      {modal?.kind === "offline" ? (
        <ModalFrame
          title="Oflayn navbat"
          close={() => setModal(null)}
          save={() => void saveOffline(modal)}
          busy={busy}
        >
          <ModalField id="medical-offline-patient" label={`${labels.customer} ism-familiyasi`} value={modal.patient} onChange={(value) => setModal({ ...modal, patient: value })} />
          <ModalField id="medical-offline-phone" label="Telefon" value={modal.phone} onChange={(value) => setModal({ ...modal, phone: value })} />
          <div style={{ textAlign: "left", margin: "10px 2px 4px", fontSize: 13, color: "var(--koprik-soft, #6b7280)" }}>Xizmat</div>
          <select aria-label="Xizmat" className="input" id="medical-offline-item" value={modal.itemId} onChange={(event) => setModal({ ...modal, itemId: event.target.value, staffId: "" })}>
            <option value="">Xizmatni tanlang</option>
            {queueItems.map((item) => <option key={text(item.id)} value={text(item.id)}>{text(item.name)}</option>)}
          </select>
          <div style={{ textAlign: "left", margin: "10px 2px 4px", fontSize: 13, color: "var(--koprik-soft, #6b7280)" }}>{labels.provider}</div>
          <select aria-label={labels.provider} className="input" id="medical-offline-staff" value={modal.staffId} onChange={(event) => setModal({ ...modal, staffId: event.target.value })}>
            <option value="">{labels.provider}ni tanlang</option>
            {providersForItem(modal.itemId).map((doctor) => {
              const employee = staffById.get(text(doctor.staff_id)) ?? doctor;
              return (
                <option key={text(doctor.staff_id)} value={text(doctor.staff_id)}>
                  {text(employee.name)}{employee.profession ? ` — ${text(employee.profession)}` : ""}
                </option>
              );
            })}
          </select>
        </ModalFrame>
      ) : null}
      {modal?.kind === "swap" ? (
        <ModalFrame
          title="Navbatlarni almashtirish"
          close={() => setModal(null)}
          save={() => void saveSwap(modal)}
          busy={busy}
        >
          <ModalField id="medical-swap-first" label="Birinchi navbat ID" value={modal.first} onChange={(value) => setModal({ ...modal, first: value })} numeric />
          <ModalField id="medical-swap-second" label="Ikkinchi navbat ID" value={modal.second} onChange={(value) => setModal({ ...modal, second: value })} numeric />
        </ModalFrame>
      ) : null}
    </section>
  );
}
