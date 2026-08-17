import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  StaffAccessWrite,
  StaffAttendance,
  StaffMember,
  StaffSchedule,
  StaffSetup,
} from "../api/types";
import { money } from "./business-profile-config";
import { StaffManagementDetailView } from "./StaffManagementDetailView";
import {
  AttendanceEditor,
  EMPTY_FORM,
  errorMessage,
  formFrom,
  normalizedSchedule,
  StaffFields,
  today,
  writeFrom,
  type Screen,
  type StaffForm,
  type StaffManagementApi,
} from "./StaffManagementShared";
import "./StaffManagement.css";

export type { StaffManagementApi } from "./StaffManagementShared";

export function StaffManagement({
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
    can_login: false,
    login: "",
    password: "",
    permissions: [],
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
    return () => {
      active = false;
    };
  }, [reload]);

  const selected = useMemo(
    () =>
      [...(setup?.active ?? []), ...(setup?.fired ?? [])].find(
        (member) => member.id === selectedId,
      ) ?? null,
    [selectedId, setup],
  );

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
    return (
      <main className="staff-v1656 staff-v1656--message">Xodimlar yuklanmoqda…</main>
    );
  }
  if (!setup) {
    return (
      <main className="staff-v1656 staff-v1656--message">
        <p role="alert">{error || "Xodimlar ma’lumoti yuklanmadi."}</p>
        <button type="button" onClick={onBack}>
          Orqaga
        </button>
      </main>
    );
  }

  if (screen === "create") {
    return (
      <main className="staff-v1656">
        <header className="staff-v1656__header">
          <button
            type="button"
            aria-label="Kabinetga qaytish"
            className="staff-v1656__back"
            onClick={() => setScreen("list")}
          >
            ←
          </button>
          <div>
            <h1>Yangi xodim</h1>
            <p>Asosiy ish ma’lumotlarini kiriting</p>
          </div>
        </header>
        <section className="staff-v1656__panel">
          <StaffFields
            form={form}
            professions={setup.professions}
            onChange={(patch) => setForm((current) => ({ ...current, ...patch }))}
          />
          {error && (
            <p className="staff-v1656__error" role="alert">
              {error}
            </p>
          )}
          <button
            type="button"
            disabled={busy || !form.name.trim() || !form.profession}
            onClick={() =>
              void run(async () => {
                await api.createStaffMember(writeFrom(form));
                setForm(EMPTY_FORM);
                setScreen("list");
              }, "Xodim qo‘shildi.")
            }
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
          <button
            type="button"
            aria-label="Kabinetga qaytish"
            className="staff-v1656__back"
            onClick={() => setScreen("list")}
          >
            ←
          </button>
          <div>
            <h1>Ish tabeli</h1>
            <p>Kunlik davomat va oylik ishlangan vaqt</p>
          </div>
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
          {error && (
            <p className="staff-v1656__error" role="alert">
              {error}
            </p>
          )}
          {attendance?.staff.map((row) => (
            <AttendanceEditor
              key={row.id}
              row={row}
              busy={busy}
              onSave={(draft) =>
                void run(async () => {
                  const value = await api.updateStaffAttendance(row.id, {
                    date: attendanceDay,
                    status: draft.status,
                    time_in: draft.status === "keldi" ? draft.time_in : "",
                    time_out: draft.status === "keldi" ? draft.time_out : "",
                  });
                  setAttendance(value);
                }, "Tabel saqlandi.")
              }
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
      <StaffManagementDetailView
        selected={selected}
        setup={setup}
        form={form}
        setForm={setForm}
        access={access}
        setAccess={setAccess}
        schedule={schedule}
        setSchedule={setSchedule}
        busy={busy}
        error={error}
        notice={notice}
        api={api}
        run={run}
        setSelectedId={setSelectedId}
        setScreen={setScreen}
      />
    );
  }

  return (
    <main className="staff-v1656">
      <header className="staff-v1656__header">
        <button
          type="button"
          aria-label="Kabinetga qaytish"
          className="staff-v1656__back"
          onClick={onBack}
        >
          ←
        </button>
        <div>
          <h1>Xodimlar</h1>
          <p>Ro‘yxat, kasblar, oylik va vakolatlar</p>
        </div>
      </header>

      <section className="staff-v1656__stats">
        <div>
          <span>Faol</span>
          <b>{setup.active_count}</b>
        </div>
        <div>
          <span>Ishdan bo‘shagan</span>
          <b>{setup.fired_count}</b>
        </div>
        <div>
          <span>Jami oylik</span>
          <b>Oyiga {money(setup.total_salary)}</b>
        </div>
      </section>

      {error && (
        <p className="staff-v1656__error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="staff-v1656__notice" role="status">
          {notice}
        </p>
      )}

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
        <button
          type="button"
          className="staff-v1656__secondary"
          onClick={() => void openAttendance()}
        >
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
          onClick={() =>
            void run(async () => {
              await api.createStaffProfession(profession.trim());
              setProfession("");
            }, "Yangi lavozim qo‘shildi.")
          }
        >
          Lavozim qo‘shish
        </button>
      </section>

      <section className="staff-v1656__list">
        {setup.active.map((member) => (
          <button type="button" key={member.id} onClick={() => openMember(member)}>
            <span className="staff-v1656__avatar">
              {member.name.trim().slice(0, 1).toUpperCase()}
            </span>
            <span>
              <b>{member.name}</b>
              <small>
                {member.profession || "Xodim"} · {member.phone || "Telefon yo‘q"}
              </small>
            </span>
            <span>
              <b>{money(member.salary)}</b>
              <small>{member.can_login ? "Kirish yoqilgan" : "Kirish o‘chiq"}</small>
            </span>
          </button>
        ))}
        {!setup.active.length && (
          <p className="staff-v1656__empty">Hozircha faol xodim yo‘q.</p>
        )}
      </section>

      {setup.fired.length > 0 && (
        <details className="staff-v1656__fired">
          <summary>Ishdan bo‘shaganlar ({setup.fired.length})</summary>
          {setup.fired.map((member) => (
            <button type="button" key={member.id} onClick={() => openMember(member)}>
              <b>{member.name}</b>
              <span>{member.profession || "Xodim"}</span>
            </button>
          ))}
        </details>
      )}
    </main>
  );
}
