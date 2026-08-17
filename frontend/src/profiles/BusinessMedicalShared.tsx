import type { ReactNode } from "react";

import type { BusinessOnlineRecord } from "../api/business-online-types";

export type BackHandlerChange = (handler: (() => void) | null, title?: string) => void;

export type ProviderProps = {
  direction: string;
  doctors: BusinessOnlineRecord[];
  staff: BusinessOnlineRecord[];
  items: BusinessOnlineRecord[];
  busy: boolean;
  loading?: boolean;
  createDoctor: (record: BusinessOnlineRecord) => Promise<boolean>;
  patchDoctor: (id: number | string, patch: BusinessOnlineRecord) => Promise<boolean>;
  onBackHandlerChange: BackHandlerChange;
  onListBack?: (() => void) | null;
};

export type QueueProps = {
  direction: string;
  rows: BusinessOnlineRecord[];
  doctors: BusinessOnlineRecord[];
  staff: BusinessOnlineRecord[];
  items: BusinessOnlineRecord[];
  busy: boolean;
  loading?: boolean;
  createDoctor: ProviderProps["createDoctor"];
  patchDoctor: ProviderProps["patchDoctor"];
  createOffline: (input: {
    patientName: string;
    phone: string;
    itemId: string;
    providerId: string;
    queueDate: string;
  }) => Promise<BusinessOnlineRecord | null>;
  changeStatus: (id: number | string, status: string) => Promise<boolean>;
  swapQueues: (first: number | string, second: number | string) => Promise<boolean>;
  loadDate: (date: string) => Promise<void>;
  onBackHandlerChange: BackHandlerChange;
};

export type DoctorDraft = {
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
  item_ids: Array<number | string>;
};

export type Toast = { text: string; role: "alert" | "status" } | null;
export type QueueModal =
  | { kind: "offline"; patient: string; phone: string; itemId: string; staffId: string }
  | { kind: "swap"; first: string; second: string }
  | { kind: "cancel"; queue: BusinessOnlineRecord }
  | null;

export const STATUS_LABELS: Record<string, string> = {
  waiting: "Kutilmoqda",
  called: "Chaqirildi",
  in_service: "Qabulda",
  done: "Yakunlandi",
  no_show: "Kelmadi",
  cancelled: "Bekor qilindi",
  skipped: "O'tkazib yuborildi",
};

export function text(value: unknown) {
  return String(value ?? "");
}

export function recordId(row: BusinessOnlineRecord) {
  return (row.id ?? "") as number | string;
}

export function compareName(left: BusinessOnlineRecord, right: BusinessOnlineRecord) {
  const leftName = text(left.name);
  const rightName = text(right.name);
  return leftName < rightName ? -1 : leftName > rightName ? 1 : 0;
}

export function isQueueEnabled(value: unknown) {
  return value === true || ["1", "true", "on"].includes(text(value).toLowerCase());
}

export function localIsoDate() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function doctorDraft(row?: BusinessOnlineRecord): DoctorDraft {
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
    item_ids: Array.isArray(row?.item_public_ids)
      ? (row.item_public_ids as Array<number | string>)
      : Array.isArray(row?.item_ids)
        ? (row.item_ids as Array<number | string>)
        : [],
  };
}

export function itemKey(row: BusinessOnlineRecord) {
  return text(row.public_id ?? row.id);
}

export function providerItemIds(row: BusinessOnlineRecord) {
  const value = Array.isArray(row.item_public_ids) ? row.item_public_ids : row.item_ids;
  return Array.isArray(value) ? value.map(text) : [];
}

export function providerChoiceId(row: BusinessOnlineRecord) {
  return text(row.provider_id ?? row.staff_id);
}

export function AppToast({ toast }: { toast: Toast }) {
  if (!toast) return null;
  return (
    <div className="app-toast on" role={toast.role}>
      {toast.text}
    </div>
  );
}

export function ModalFrame({
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
      <div className="app-modal-back on" onClick={close} />
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

export function ModalField({
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
      <div
        style={{
          textAlign: "left",
          margin: "10px 2px 4px",
          fontSize: 13,
          color: "var(--koprik-soft, #6b7280)",
        }}
      >
        {label}
      </div>
      <input
        className="input"
        id={id}
        aria-label={label}
        type="text"
        inputMode={numeric ? "numeric" : undefined}
        value={value}
        onChange={(event) =>
          onChange(numeric ? event.target.value.replace(/\D/g, "") : event.target.value)
        }
      />
    </>
  );
}
