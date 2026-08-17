import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  StaffAttendanceRow,
  StaffMember,
  StaffMemberWrite,
  StaffSchedule,
} from "../api/types";

export type StaffManagementApi = Pick<
  ApiClient,
  | "getStaffSetup"
  | "createStaffMember"
  | "updateStaffMember"
  | "fireStaffMember"
  | "rehireStaffMember"
  | "deleteStaffMember"
  | "updateStaffAccess"
  | "updateStaffSchedule"
  | "createStaffProfession"
  | "getStaffAttendance"
  | "updateStaffAttendance"
>;

export type Screen = "list" | "create" | "detail" | "attendance";
export type StaffForm = {
  name: string;
  profession: string;
  phone: string;
  salary: string;
  hire_date: string;
  note: string;
};

export const WEEK = [
  "Dushanba",
  "Seshanba",
  "Chorshanba",
  "Payshanba",
  "Juma",
  "Shanba",
  "Yakshanba",
];

export const EMPTY_FORM: StaffForm = {
  name: "",
  profession: "",
  phone: "",
  salary: "0",
  hire_date: "",
  note: "",
};

export function today() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

export function formFrom(member: StaffMember): StaffForm {
  return {
    name: member.name,
    profession: member.profession,
    phone: member.phone,
    salary: String(member.salary),
    hire_date: member.hire_date ?? "",
    note: member.note,
  };
}

export function writeFrom(form: StaffForm): StaffMemberWrite {
  return {
    name: form.name.trim(),
    profession: form.profession.trim(),
    phone: form.phone.trim(),
    salary: Math.max(0, Number(form.salary) || 0),
    hire_date: form.hire_date || null,
    note: form.note.trim(),
  };
}

export function normalizedSchedule(value: StaffSchedule): StaffSchedule {
  return Object.fromEntries(
    WEEK.map((_label, index) => {
      const current = value[`d${index}`];
      return [
        `d${index}`,
        {
          on: Boolean(current?.on),
          start: current?.start || "09:00",
          end: current?.end || "18:00",
        },
      ];
    }),
  );
}

function duration(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest} daqiqa`;
  return `${hours} soat${rest ? ` ${rest} daqiqa` : ""}`;
}

export function StaffFields({
  form,
  professions,
  onChange,
}: {
  form: StaffForm;
  professions: string[];
  onChange: (patch: Partial<StaffForm>) => void;
}) {
  return (
    <div className="staff-v1656__fields">
      <label>
        F.I.Sh.
        <input
          value={form.name}
          maxLength={120}
          onChange={(event) => onChange({ name: event.target.value })}
          required
        />
      </label>
      <label>
        Lavozimi
        <select
          value={form.profession}
          onChange={(event) => onChange({ profession: event.target.value })}
          required
        >
          <option value="">Tanlang</option>
          {professions.map((profession) => (
            <option key={profession} value={profession}>
              {profession}
            </option>
          ))}
        </select>
      </label>
      <label>
        Telefon
        <input
          type="tel"
          value={form.phone}
          maxLength={32}
          onChange={(event) => onChange({ phone: event.target.value })}
        />
      </label>
      <label>
        Oylik maosh
        <input
          type="number"
          min="0"
          step="1000"
          value={form.salary}
          onChange={(event) => onChange({ salary: event.target.value })}
        />
      </label>
      <label>
        Ishga kirgan sana
        <input
          type="date"
          value={form.hire_date}
          onChange={(event) => onChange({ hire_date: event.target.value })}
        />
      </label>
      <label className="staff-v1656__wide">
        Izoh
        <textarea
          value={form.note}
          maxLength={500}
          onChange={(event) => onChange({ note: event.target.value })}
        />
      </label>
    </div>
  );
}

export function AttendanceEditor({
  row,
  busy,
  onSave,
}: {
  row: StaffAttendanceRow;
  busy: boolean;
  onSave: (row: StaffAttendanceRow) => void;
}) {
  const [draft, setDraft] = useState(row);
  useEffect(() => setDraft(row), [row]);
  return (
    <article className="staff-v1656__attendance-row">
      <div>
        <b>{row.name}</b>
        <span>{row.profession || "Xodim"}</span>
        <small>
          Oy davomida: {row.month_present} kun · {duration(row.month_minutes)}
        </small>
      </div>
      <label>
        Holati
        <select
          value={draft.status}
          onChange={(event) => setDraft({ ...draft, status: event.target.value })}
        >
          <option value="">Belgilanmagan</option>
          <option value="keldi">Keldi</option>
          <option value="kelmadi">Kelmadi</option>
          <option value="dam">Dam olish</option>
        </select>
      </label>
      <label>
        Keldi
        <input
          type="time"
          disabled={draft.status !== "keldi"}
          value={draft.time_in}
          onChange={(event) => setDraft({ ...draft, time_in: event.target.value })}
        />
      </label>
      <label>
        Ketdi
        <input
          type="time"
          disabled={draft.status !== "keldi"}
          value={draft.time_out}
          onChange={(event) => setDraft({ ...draft, time_out: event.target.value })}
        />
      </label>
      <button type="button" disabled={busy} onClick={() => onSave(draft)}>
        Saqlash
      </button>
    </article>
  );
}
