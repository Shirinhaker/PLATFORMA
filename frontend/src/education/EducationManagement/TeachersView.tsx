// `EducationManagement.tsx` dan ajratildi.
import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { ApiClient } from "../../api/client";
import type {
  EducationAttendanceStudent,
  EducationAttendanceStatus,
  EducationGroup,
  EducationPaymentControl,
  EducationPaymentControlStatus,
  EducationPaymentControlStudent,
  EducationPaymentMonth,
  EducationPaymentStudent,
  EducationPayroll,
  EducationPayrollTeacher,
  EducationTeacher,
  EducationTeacherWrite,
} from "../../api/types";
import "../EducationManagement.css";
import { EducationGroups, EducationStudents } from "../EducationDirectory";
import {
  EMPTY_TEACHER,
  EducationManagementApi,
  EducationShell,
  Empty,
  ErrorBox,
  localDate,
  message,
  money,
  numeric,
} from "./shared";

export function TeachersView({
  api,
  onBack,
}: {
  api: EducationManagementApi;
  onBack: () => void;
}) {
  const [teachers, setTeachers] = useState<EducationTeacher[]>([]);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<EducationTeacher | null | undefined>();
  const [form, setForm] = useState<EducationTeacherWrite>(EMPTY_TEACHER);
  const [salary, setSalary] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function reload() {
    setLoading(true);
    setError("");
    try {
      setTeachers(await api.getEducationTeachers());
    } catch (reason) {
      setError(message(reason));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void reload();
  }, [api]);

  function open(teacher?: EducationTeacher) {
    setEditing(teacher ?? null);
    setForm(
      teacher
        ? {
            full_name: teacher.full_name,
            phone: teacher.phone,
            specialty: teacher.specialty,
            hired_date: teacher.hired_date,
            salary_type: teacher.salary_type,
            salary_amount: teacher.salary_amount,
            note: teacher.note,
          }
        : { ...EMPTY_TEACHER, hired_date: localDate() },
    );
    setSalary(teacher?.salary_amount ? String(teacher.salary_amount) : "");
  }

  async function save() {
    if (!form.full_name.trim()) {
      setError("O'qituvchi ism-familiyasini kiriting.");
      return;
    }
    setBusy(true);
    setError("");
    const body = { ...form, salary_amount: numeric(salary) };
    try {
      if (editing) await api.updateEducationTeacher(editing.id, body);
      else await api.createEducationTeacher(body);
      setEditing(undefined);
      await reload();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (
      !editing ||
      !window.confirm(
        "O'qituvchi faol ro'yxatdan chiqarilsinmi? Guruhlardagi eski nomi saqlanadi.",
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await api.deleteEducationTeacher(editing.id);
      setEditing(undefined);
      await reload();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  const rows = teachers.filter(
    (teacher) =>
      !search.trim() ||
      [teacher.full_name, teacher.phone, teacher.specialty]
        .join(" ")
        .toLocaleLowerCase("uz")
        .includes(search.trim().toLocaleLowerCase("uz")),
  );
  return (
    <EducationShell
      title="O'qituvchilar"
      caption="O'qituvchi, fan va ish haqi"
      onBack={onBack}
    >
      <ErrorBox value={error} />
      <section className="education-management-v1656__toolbar">
        <div>
          <b>O'qituvchilar</b>
          <small>{teachers.length} nafar faol o'qituvchi</small>
        </div>
        <button type="button" onClick={() => open()}>
          + O'qituvchi
        </button>
      </section>
      <input
        className="education-management-v1656__search"
        type="search"
        placeholder="Ism yoki fan bo'yicha qidirish..."
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
      {loading ? <Empty>Yuklanmoqda…</Empty> : null}
      <section className="education-management-v1656__cards">
        {rows.map((teacher) => (
          <button
            className="education-management-v1656__teacher"
            type="button"
            key={teacher.id}
            onClick={() => open(teacher)}
          >
            <span>🧑‍🏫</span>
            <div>
              <b>{teacher.full_name}</b>
              <small>{teacher.specialty || "Mutaxassislik belgilanmagan"}</small>
              <em>
                {teacher.phone ? `📞 ${teacher.phone} · ` : ""}👥 {teacher.group_count}{" "}
                guruh
                {teacher.salary_amount
                  ? ` · 💰 ${money(teacher.salary_amount)} ${teacher.salary_type === "per_lesson" ? "/ dars" : "/ oy"}`
                  : ""}
              </em>
            </div>
            <i>›</i>
          </button>
        ))}
      </section>
      {!loading && !rows.length ? (
        <Empty>
          <h3>O'qituvchi topilmadi</h3>
          <p>Yangi o'qituvchi qo'shing yoki qidiruvni o'zgartiring.</p>
        </Empty>
      ) : null}
      {editing !== undefined ? (
        <div className="education-management-v1656__modal-back">
          <section
            className="education-management-v1656__modal"
            role="dialog"
            aria-modal="true"
          >
            <h2>{editing ? "O'qituvchini tahrirlash" : "Yangi o'qituvchi"}</h2>
            <label>
              Ism-familiya
              <input
                value={form.full_name}
                maxLength={120}
                onChange={(event) =>
                  setForm({ ...form, full_name: event.target.value })
                }
              />
            </label>
            <label>
              Telefon raqami
              <input
                value={form.phone}
                maxLength={30}
                onChange={(event) => setForm({ ...form, phone: event.target.value })}
              />
            </label>
            <label>
              Fan yoki mutaxassisligi
              <input
                value={form.specialty}
                maxLength={120}
                onChange={(event) =>
                  setForm({ ...form, specialty: event.target.value })
                }
              />
            </label>
            <label>
              Ishga kirgan sana
              <input
                type="date"
                value={form.hired_date}
                onChange={(event) =>
                  setForm({ ...form, hired_date: event.target.value })
                }
              />
            </label>
            <label>
              Ish haqi turi
              <select
                value={form.salary_type}
                onChange={(event) =>
                  setForm({
                    ...form,
                    salary_type: event.target.value as "monthly" | "per_lesson",
                  })
                }
              >
                <option value="monthly">Oylik maosh</option>
                <option value="per_lesson">Har bir dars uchun</option>
              </select>
            </label>
            <label>
              Ish haqi summasi
              <input
                inputMode="numeric"
                value={salary}
                onChange={(event) => setSalary(event.target.value)}
              />
            </label>
            <label>
              Izoh
              <textarea
                value={form.note}
                maxLength={500}
                onChange={(event) => setForm({ ...form, note: event.target.value })}
              />
            </label>
            <div className="education-management-v1656__modal-actions">
              {editing ? (
                <button
                  type="button"
                  className="danger"
                  disabled={busy}
                  onClick={() => void remove()}
                >
                  Ro'yxatdan chiqarish
                </button>
              ) : null}
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditing(undefined)}
              >
                Bekor qilish
              </button>
              <button type="button" disabled={busy} onClick={() => void save()}>
                Saqlash
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </EducationShell>
  );
}
