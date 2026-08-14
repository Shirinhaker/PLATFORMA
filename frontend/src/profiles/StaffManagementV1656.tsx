import { useCallback, useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  StaffAccessWrite,
  StaffAttendance,
  StaffAttendanceRow,
  StaffMember,
  StaffMemberWrite,
  StaffSchedule,
  StaffSetup,
} from "../api/types";
import { money } from "./business-profile-config";
import "./StaffManagementV1656.css";


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

type Screen = "list" | "create" | "detail" | "attendance";
type StaffForm = {
  name: string;
  profession: string;
  phone: string;
  salary: string;
  hire_date: string;
  note: string;
};

const WEEK = [
  "Dushanba", "Seshanba", "Chorshanba", "Payshanba",
  "Juma", "Shanba", "Yakshanba",
];

const EMPTY_FORM: StaffForm = {
  name: "",
  profession: "",
  phone: "",
  salary: "0",
  hire_date: "",
  note: "",
};

function today() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function formFrom(member: StaffMember): StaffForm {
  return {
    name: member.name,
    profession: member.profession,
    phone: member.phone,
    salary: String(member.salary),
    hire_date: member.hire_date ?? "",
    note: member.note,
  };
}

function writeFrom(form: StaffForm): StaffMemberWrite {
  return {
    name: form.name.trim(),
    profession: form.profession.trim(),
    phone: form.phone.trim(),
    salary: Math.max(0, Number(form.salary) || 0),
    hire_date: form.hire_date || null,
    note: form.note.trim(),
  };
}

function normalizedSchedule(value: StaffSchedule): StaffSchedule {
  return Object.fromEntries(WEEK.map((_label, index) => {
    const current = value[`d${index}`];
    return [`d${index}`, {
      on: Boolean(current?.on),
      start: current?.start || "09:00",
      end: current?.end || "18:00",
    }];
  }));
}

function duration(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest} daqiqa`;
  return `${hours} soat${rest ? ` ${rest} daqiqa` : ""}`;
}

function StaffFields({
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
            <option key={profession} value={profession}>{profession}</option>
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

function AttendanceEditor({
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

export function StaffManagementV1656({
  api,
  onBack,
}: {
  api: StaffManagementApi;
  onBack: () => void;
}) {
  const [setup, setSetup] = useState<StaffSetup | null>(null);
  const [screen, setScreen] = useState<Screen>("list");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<StaffForm>(EMPTY_FORM);
  const [access, setAccess] = useState<StaffAccessWrite>({
    can_login: false, login: "", password: "", permissions: [],
  });
  const [schedule, setSchedule] = useState<StaffSchedule>(() => normalizedSchedule({}));
  const [profession, setProfession] = useState("");
  const [attendanceDay, setAttendanceDay] = useState(today);
  const [attendance, setAttendance] = useState<StaffAttendance | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const reload = useCallback(async () => {
    const value = await api.getStaffSetup();
    setSetup(value);
    return value;
  }, [api]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    reload()
      .catch((reason) => active && setError(errorMessage(reason)))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [reload]);

  const selected = useMemo(() => (
    [...(setup?.active ?? []), ...(setup?.fired ?? [])]
      .find((member) => member.id === selectedId) ?? null
  ), [selectedId, setup]);

  function openMember(member: StaffMember) {
    setSelectedId(member.id);
    setForm(formFrom(member));
    setAccess({
      can_login: member.can_login,
      login: member.login,
      password: "",
      permissions: [...member.permissions],
    });
    setSchedule(normalizedSchedule(member.schedule));
    setError("");
    setNotice("");
    setScreen("detail");
  }

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await reload();
      setNotice(success);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function openAttendance() {
    setScreen("attendance");
    setBusy(true);
    setError("");
    try {
      setAttendance(await api.getStaffAttendance(attendanceDay));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <main className="staff-v1656 staff-v1656--message">Xodimlar yuklanmoqda…</main>;
  }
  if (!setup) {
    return (
      <main className="staff-v1656 staff-v1656--message">
        <p role="alert">{error || "Xodimlar ma’lumoti yuklanmadi."}</p>
        <button type="button" onClick={onBack}>Orqaga</button>
      </main>
    );
  }

  if (screen === "create") {
    return (
      <main className="staff-v1656">
        <header className="staff-v1656__header">
          <button type="button" aria-label="Kabinetga qaytish" className="staff-v1656__back" onClick={() => setScreen("list")}>←</button>
          <div><h1>Yangi xodim</h1><p>Asosiy ish ma’lumotlarini kiriting</p></div>
        </header>
        <section className="staff-v1656__panel">
          <StaffFields
            form={form}
            professions={setup.professions}
            onChange={(patch) => setForm((current) => ({ ...current, ...patch }))}
          />
          {error && <p className="staff-v1656__error" role="alert">{error}</p>}
          <button
            type="button"
            disabled={busy || !form.name.trim() || !form.profession}
            onClick={() => void run(async () => {
              await api.createStaffMember(writeFrom(form));
              setForm(EMPTY_FORM);
              setScreen("list");
            }, "Xodim qo‘shildi.")}
          >
            Saqlash
          </button>
        </section>
      </main>
    );
  }

  if (screen === "attendance") {
    return (
      <main className="staff-v1656">
        <header className="staff-v1656__header">
          <button type="button" aria-label="Kabinetga qaytish" className="staff-v1656__back" onClick={() => setScreen("list")}>←</button>
          <div><h1>Ish tabeli</h1><p>Kunlik davomat va oylik ishlangan vaqt</p></div>
        </header>
        <section className="staff-v1656__panel">
          <div className="staff-v1656__attendance-date">
            <label>
              Sana
              <input
                type="date"
                max={today()}
                value={attendanceDay}
                onChange={(event) => setAttendanceDay(event.target.value)}
              />
            </label>
            <button type="button" disabled={busy} onClick={() => void openAttendance()}>
              Ko‘rsatish
            </button>
          </div>
          {error && <p className="staff-v1656__error" role="alert">{error}</p>}
          {attendance?.staff.map((row) => (
            <AttendanceEditor
              key={row.id}
              row={row}
              busy={busy}
              onSave={(draft) => void run(async () => {
                const value = await api.updateStaffAttendance(row.id, {
                  date: attendanceDay,
                  status: draft.status,
                  time_in: draft.status === "keldi" ? draft.time_in : "",
                  time_out: draft.status === "keldi" ? draft.time_out : "",
                });
                setAttendance(value);
              }, "Tabel saqlandi.")}
            />
          ))}
          {attendance && !attendance.staff.length && (
            <p className="staff-v1656__empty">Faol xodim yo‘q.</p>
          )}
        </section>
      </main>
    );
  }

  if (screen === "detail" && selected) {
    return (
      <main className="staff-v1656">
        <header className="staff-v1656__header">
          <button type="button" aria-label="Kabinetga qaytish" className="staff-v1656__back" onClick={() => setScreen("list")}>←</button>
          <div><h1>{selected.name}</h1><p>{selected.profession || "Xodim"}</p></div>
          <span className={`staff-v1656__status staff-v1656__status--${selected.status}`}>
            {selected.status === "active" ? "Faol" : "Ishdan bo‘shagan"}
          </span>
        </header>

        {error && <p className="staff-v1656__error" role="alert">{error}</p>}
        {notice && <p className="staff-v1656__notice" role="status">{notice}</p>}

        <section className="staff-v1656__panel">
          <h2>Asosiy ma’lumotlar</h2>
          <StaffFields
            form={form}
            professions={setup.professions}
            onChange={(patch) => setForm((current) => ({ ...current, ...patch }))}
          />
          <button
            type="button"
            disabled={busy}
            onClick={() => void run(
              () => api.updateStaffMember(selected.id, writeFrom(form)),
              "Xodim ma’lumoti saqlandi.",
            )}
          >
            Asosiy ma’lumotni saqlash
          </button>
        </section>

        <section className="staff-v1656__panel">
          <h2>Ilovaga kirish va vakolatlar</h2>
          <p className="staff-v1656__hint">
            Firma logini: <b>{setup.firm_login}</b>. Xodim faqat belgilangan bo‘limlarni ko‘radi.
          </p>
          <label className="staff-v1656__check-row">
            <input
              type="checkbox"
              checked={access.can_login}
              onChange={(event) => setAccess({ ...access, can_login: event.target.checked })}
            />
            Ilovaga kirish huquqi
          </label>
          <div className="staff-v1656__fields">
            <label>
              Xodim logini
              <input
                value={access.login}
                disabled={!access.can_login}
                onChange={(event) => setAccess({ ...access, login: event.target.value.toLowerCase() })}
              />
            </label>
            <label>
              Yangi parol (ixtiyoriy)
              <input
                aria-label="Yangi parol (ixtiyoriy)"
                type="password"
                autoComplete="new-password"
                value={access.password}
                disabled={!access.can_login}
                onChange={(event) => setAccess({ ...access, password: event.target.value })}
              />
              <small>{selected.has_password ? "Parol o‘rnatilgan" : "Yangi parol talab qilinadi"}</small>
            </label>
          </div>
          <div className="staff-v1656__templates">
            {setup.permission_templates.map((template) => (
              <button
                type="button"
                key={template.key}
                disabled={!access.can_login}
                onClick={() => setAccess({ ...access, permissions: [...template.permissions] })}
              >
                {template.label}
              </button>
            ))}
          </div>
          <div className="staff-v1656__permissions">
            {setup.permission_definitions.map((permission) => (
              <label key={permission.key}>
                <input
                  type="checkbox"
                  checked={access.permissions.includes(permission.key)}
                  disabled={!access.can_login}
                  onChange={(event) => setAccess((current) => ({
                    ...current,
                    permissions: event.target.checked
                      ? [...current.permissions, permission.key]
                      : current.permissions.filter((key) => key !== permission.key),
                  }))}
                />
                <span>{permission.icon} {permission.label}</span>
              </label>
            ))}
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => void run(async () => {
              await api.updateStaffAccess(selected.id, access);
              setAccess((current) => ({ ...current, password: "" }));
            }, "Kirish va vakolat saqlandi.")}
          >
            Kirish va vakolatni saqlash
          </button>
        </section>

        <section className="staff-v1656__panel">
          <h2>Haftalik ish grafigi</h2>
          <div className="staff-v1656__schedule">
            {WEEK.map((day, index) => {
              const key = `d${index}`;
              const value = schedule[key] ?? {
                on: false,
                start: "09:00",
                end: "18:00",
              };
              return (
                <div key={key}>
                  <label className="staff-v1656__check-row">
                    <input
                      type="checkbox"
                      checked={value.on}
                      onChange={(event) => setSchedule({
                        ...schedule,
                        [key]: { ...value, on: event.target.checked },
                      })}
                    />
                    {day}
                  </label>
                  <input
                    aria-label={`${day} boshlanishi`}
                    type="time"
                    disabled={!value.on}
                    value={value.start}
                    onChange={(event) => setSchedule({
                      ...schedule,
                      [key]: { ...value, start: event.target.value },
                    })}
                  />
                  <input
                    aria-label={`${day} tugashi`}
                    type="time"
                    disabled={!value.on}
                    value={value.end}
                    onChange={(event) => setSchedule({
                      ...schedule,
                      [key]: { ...value, end: event.target.value },
                    })}
                  />
                </div>
              );
            })}
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => void run(
              () => api.updateStaffSchedule(selected.id, schedule),
              "Ish grafigi saqlandi.",
            )}
          >
            Grafikni saqlash
          </button>
        </section>

        <section className="staff-v1656__danger">
          {selected.status === "active" ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => void run(
                () => api.fireStaffMember(selected.id),
                "Xodim ishdan bo‘shatildi va sessiyalari yopildi.",
              )}
            >
              Ishdan bo‘shatish
            </button>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={() => void run(
                () => api.rehireStaffMember(selected.id),
                "Xodim qayta ishga olindi.",
              )}
            >
              Qayta ishga olish
            </button>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              if (!window.confirm("Xodimni butunlay o‘chirasizmi?")) return;
              void run(async () => {
                await api.deleteStaffMember(selected.id);
                setSelectedId(null);
                setScreen("list");
              }, "Xodim o‘chirildi.");
            }}
          >
            Butunlay o‘chirish
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="staff-v1656">
      <header className="staff-v1656__header">
        <button type="button" aria-label="Kabinetga qaytish" className="staff-v1656__back" onClick={onBack}>←</button>
        <div><h1>Xodimlar</h1><p>Ro‘yxat, kasblar, oylik va vakolatlar</p></div>
      </header>

      <section className="staff-v1656__stats">
        <div><span>Faol</span><b>{setup.active_count}</b></div>
        <div><span>Ishdan bo‘shagan</span><b>{setup.fired_count}</b></div>
        <div><span>Jami oylik</span><b>Oyiga {money(setup.total_salary)}</b></div>
      </section>

      {error && <p className="staff-v1656__error" role="alert">{error}</p>}
      {notice && <p className="staff-v1656__notice" role="status">{notice}</p>}

      <div className="staff-v1656__actions">
        <button
          type="button"
          onClick={() => {
            setForm({ ...EMPTY_FORM, profession: setup.professions[0] ?? "" });
            setScreen("create");
          }}
        >
          + Xodim qo‘shish
        </button>
        <button type="button" className="staff-v1656__secondary" onClick={() => void openAttendance()}>
          📅 Ish tabeli
        </button>
      </div>

      <section className="staff-v1656__profession">
        <label>
          Yangi lavozim
          <input
            value={profession}
            placeholder="Masalan: Operator"
            onChange={(event) => setProfession(event.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={busy || !profession.trim()}
          onClick={() => void run(async () => {
            await api.createStaffProfession(profession.trim());
            setProfession("");
          }, "Yangi lavozim qo‘shildi.")}
        >
          Lavozim qo‘shish
        </button>
      </section>

      <section className="staff-v1656__list">
        {setup.active.map((member) => (
          <button type="button" key={member.id} onClick={() => openMember(member)}>
            <span className="staff-v1656__avatar">{member.name.trim().slice(0, 1).toUpperCase()}</span>
            <span><b>{member.name}</b><small>{member.profession || "Xodim"} · {member.phone || "Telefon yo‘q"}</small></span>
            <span><b>{money(member.salary)}</b><small>{member.can_login ? "Kirish yoqilgan" : "Kirish o‘chiq"}</small></span>
          </button>
        ))}
        {!setup.active.length && <p className="staff-v1656__empty">Hozircha faol xodim yo‘q.</p>}
      </section>

      {setup.fired.length > 0 && (
        <details className="staff-v1656__fired">
          <summary>Ishdan bo‘shaganlar ({setup.fired.length})</summary>
          {setup.fired.map((member) => (
            <button type="button" key={member.id} onClick={() => openMember(member)}>
              <b>{member.name}</b><span>{member.profession || "Xodim"}</span>
            </button>
          ))}
        </details>
      )}
    </main>
  );
}
