import type { Dispatch, SetStateAction } from "react";

import type {
  StaffAccessWrite,
  StaffMember,
  StaffSchedule,
  StaffSetup,
} from "../api/types";
import {
  StaffFields,
  WEEK,
  writeFrom,
  type Screen,
  type StaffForm,
  type StaffManagementApi,
} from "./StaffManagementShared";

export function StaffManagementDetailView({
  selected,
  setup,
  form,
  setForm,
  access,
  setAccess,
  schedule,
  setSchedule,
  busy,
  error,
  notice,
  api,
  run,
  setSelectedId,
  setScreen,
}: {
  selected: StaffMember;
  setup: StaffSetup;
  form: StaffForm;
  setForm: Dispatch<SetStateAction<StaffForm>>;
  access: StaffAccessWrite;
  setAccess: Dispatch<SetStateAction<StaffAccessWrite>>;
  schedule: StaffSchedule;
  setSchedule: Dispatch<SetStateAction<StaffSchedule>>;
  busy: boolean;
  error: string;
  notice: string;
  api: StaffManagementApi;
  run: (action: () => Promise<unknown>, success: string) => Promise<void>;
  setSelectedId: Dispatch<SetStateAction<number | null>>;
  setScreen: Dispatch<SetStateAction<Screen>>;
}) {
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
          <h1>{selected.name}</h1>
          <p>{selected.profession || "Xodim"}</p>
        </div>
        <span className={`staff-v1656__status staff-v1656__status--${selected.status}`}>
          {selected.status === "active" ? "Faol" : "Ishdan bo‘shagan"}
        </span>
      </header>

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
          onClick={() =>
            void run(
              () => api.updateStaffMember(selected.id, writeFrom(form)),
              "Xodim ma’lumoti saqlandi.",
            )
          }
        >
          Asosiy ma’lumotni saqlash
        </button>
      </section>

      <section className="staff-v1656__panel">
        <h2>Ilovaga kirish va vakolatlar</h2>
        <p className="staff-v1656__hint">
          Firma logini: <b>{setup.firm_login}</b>. Xodim faqat belgilangan bo‘limlarni
          ko‘radi.
        </p>
        <label className="staff-v1656__check-row">
          <input
            type="checkbox"
            checked={access.can_login}
            onChange={(event) =>
              setAccess({ ...access, can_login: event.target.checked })
            }
          />
          Ilovaga kirish huquqi
        </label>
        <div className="staff-v1656__fields">
          <label>
            Xodim logini
            <input
              value={access.login}
              disabled={!access.can_login}
              onChange={(event) =>
                setAccess({ ...access, login: event.target.value.toLowerCase() })
              }
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
              onChange={(event) =>
                setAccess({ ...access, password: event.target.value })
              }
            />
            <small>
              {selected.has_password
                ? "Parol o‘rnatilgan"
                : "Yangi parol talab qilinadi"}
            </small>
          </label>
        </div>
        <div className="staff-v1656__templates">
          {setup.permission_templates.map((template) => (
            <button
              type="button"
              key={template.key}
              disabled={!access.can_login}
              onClick={() =>
                setAccess({ ...access, permissions: [...template.permissions] })
              }
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
                onChange={(event) =>
                  setAccess((current) => ({
                    ...current,
                    permissions: event.target.checked
                      ? [...current.permissions, permission.key]
                      : current.permissions.filter((key) => key !== permission.key),
                  }))
                }
              />
              <span>
                {permission.icon} {permission.label}
              </span>
            </label>
          ))}
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              await api.updateStaffAccess(selected.id, access);
              setAccess((current) => ({ ...current, password: "" }));
            }, "Kirish va vakolat saqlandi.")
          }
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
                    onChange={(event) =>
                      setSchedule({
                        ...schedule,
                        [key]: { ...value, on: event.target.checked },
                      })
                    }
                  />
                  {day}
                </label>
                <input
                  aria-label={`${day} boshlanishi`}
                  type="time"
                  disabled={!value.on}
                  value={value.start}
                  onChange={(event) =>
                    setSchedule({
                      ...schedule,
                      [key]: { ...value, start: event.target.value },
                    })
                  }
                />
                <input
                  aria-label={`${day} tugashi`}
                  type="time"
                  disabled={!value.on}
                  value={value.end}
                  onChange={(event) =>
                    setSchedule({
                      ...schedule,
                      [key]: { ...value, end: event.target.value },
                    })
                  }
                />
              </div>
            );
          })}
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            void run(
              () => api.updateStaffSchedule(selected.id, schedule),
              "Ish grafigi saqlandi.",
            )
          }
        >
          Grafikni saqlash
        </button>
      </section>

      <section className="staff-v1656__danger">
        {selected.status === "active" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void run(
                () => api.fireStaffMember(selected.id),
                "Xodim ishdan bo‘shatildi va sessiyalari yopildi.",
              )
            }
          >
            Ishdan bo‘shatish
          </button>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void run(
                () => api.rehireStaffMember(selected.id),
                "Xodim qayta ishga olindi.",
              )
            }
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
