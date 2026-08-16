import { useEffect, useState } from "react";

import type {
  EducationGroup,
  EducationGroupWrite,
  EducationTeacher,
} from "../../api/types";

import {
  DAYS,
  EMPTY_GROUP,
  ErrorBox,
  Modal,
  Shell,
  errorMessage,
  numeric,
  type EducationDirectoryApi,
} from "./shared";

export function EducationGroups({
  api,
  onBack,
}: {
  api: EducationDirectoryApi;
  onBack: () => void;
}) {
  const [groups, setGroups] = useState<EducationGroup[]>([]);
  const [teachers, setTeachers] = useState<EducationTeacher[]>([]);
  const [courses, setCourses] = useState<Array<{ id: number; name: string }>>([]);
  const [editing, setEditing] = useState<EducationGroup | null | undefined>();
  const [form, setForm] = useState<EducationGroupWrite>(EMPTY_GROUP);
  const [price, setPrice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function reload() {
    setLoading(true);
    setError("");
    try {
      setGroups(await api.getEducationGroups());
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, [api]);
  useEffect(() => {
    let active = true;
    Promise.allSettled([
      api.getEducationTeachers(),
      api.getBusinessOnlineResource("items"),
    ]).then(([teacherResult, courseResult]) => {
      if (!active) return;
      if (teacherResult.status === "fulfilled") setTeachers(teacherResult.value);
      if (courseResult.status !== "fulfilled") return;
      setCourses(
        courseResult.value.items.flatMap((item) => {
          const id = Number(item.id || 0);
          const name = String(item.name || "");
          return id && name && item.kind === "service" ? [{ id, name }] : [];
        }),
      );
    });
    return () => {
      active = false;
    };
  }, [api]);

  function open(group?: EducationGroup) {
    setEditing(group ?? null);
    setForm(
      group
        ? {
            name: group.name,
            course_item_id: group.course_item_id,
            teacher_id: group.teacher_id,
            teacher_name: group.teacher_name,
            room_name: group.room_name,
            capacity: group.capacity,
            weekdays: group.weekdays.split(",").filter(Boolean),
            lesson_from: group.lesson_from,
            lesson_to: group.lesson_to,
            start_date: group.start_date,
            end_date: group.end_date,
            billing_type: group.billing_type,
            package_lessons: group.package_lessons,
            package_price: group.package_price,
          }
        : { ...EMPTY_GROUP, weekdays: [] },
    );
    setPrice(group?.package_price ? String(group.package_price) : "");
  }

  async function save() {
    if (!form.name.trim()) {
      setError("Guruh nomini kiriting.");
      return;
    }
    setBusy(true);
    setError("");
    const teacher = teachers.find((row) => row.id === form.teacher_id);
    const body = {
      ...form,
      teacher_name: teacher?.full_name || form.teacher_name,
      package_price: numeric(price),
    };
    try {
      if (editing) await api.updateEducationGroup(editing.id, body);
      else await api.createEducationGroup(body);
      setEditing(undefined);
      await reload();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!editing || !window.confirm("Bu guruh o'chirilsinmi?")) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteEducationGroup(editing.id);
      setEditing(undefined);
      await reload();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell
      title="Ta'lim guruhlari"
      caption="Guruh va dars ma'lumotlari"
      onBack={onBack}
    >
      <ErrorBox value={error} />
      <section className="education-management-v1656__toolbar">
        <div>
          <b>Guruhlar</b>
          <small>{groups.length} ta faol guruh</small>
        </div>
        <button type="button" onClick={() => open()}>
          + Guruh
        </button>
      </section>
      {loading ? (
        <div className="education-management-v1656__empty">Yuklanmoqda…</div>
      ) : null}
      <section className="education-management-v1656__cards">
        {groups.map((group) => (
          <article key={group.id}>
            <header>
              <div>
                <b>{group.name}</b>
                <small>📚 {group.course_name || "Kurs biriktirilmagan"}</small>
              </div>
              <em>{group.student_count} o'quvchi</em>
            </header>
            <p>
              {group.teacher_name ? `👤 ${group.teacher_name} · ` : ""}
              {group.room_name ? `🚪 ${group.room_name} · ` : ""}
              {group.weekdays
                .split(",")
                .filter(Boolean)
                .map((day) => DAYS.find(([key]) => key === day)?.[1] || day)
                .join(", ") || "Kunlar belgilanmagan"}
              <br />
              {group.lesson_from || "—"} — {group.lesson_to || "—"} ·{" "}
              {group.start_date || "—"} — {group.end_date || "—"}
            </p>
            <button
              className="education-management-v1656__primary"
              type="button"
              onClick={() => open(group)}
            >
              Tahrirlash
            </button>
          </article>
        ))}
      </section>
      {!loading && !groups.length ? (
        <div className="education-management-v1656__empty">
          <h3>Guruhlar yo'q</h3>
          <p>Birinchi guruhni qo'shing.</p>
        </div>
      ) : null}
      {editing !== undefined ? (
        <Modal
          title={editing ? "Guruhni tahrirlash" : "Yangi guruh"}
          actions={
            <>
              {editing ? (
                <button
                  className="danger"
                  disabled={busy}
                  type="button"
                  onClick={() => void remove()}
                >
                  O'chirish
                </button>
              ) : null}
              <button
                disabled={busy}
                type="button"
                onClick={() => setEditing(undefined)}
              >
                Bekor qilish
              </button>
              <button disabled={busy} type="button" onClick={() => void save()}>
                Saqlash
              </button>
            </>
          }
        >
          <label>
            Guruh nomi
            <input
              value={form.name}
              maxLength={80}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </label>
          <label>
            Kurs
            <select
              value={form.course_item_id || ""}
              onChange={(event) =>
                setForm({ ...form, course_item_id: Number(event.target.value) || null })
              }
            >
              <option value="">Kursni tanlang</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            O'qituvchi
            <select
              value={form.teacher_id || ""}
              onChange={(event) =>
                setForm({ ...form, teacher_id: Number(event.target.value) || null })
              }
            >
              <option value="">O'qituvchini tanlang</option>
              {teachers.map((teacher) => (
                <option key={teacher.id} value={teacher.id}>
                  {teacher.full_name}
                  {teacher.specialty ? ` · ${teacher.specialty}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            Xona
            <input
              value={form.room_name}
              maxLength={80}
              onChange={(event) => setForm({ ...form, room_name: event.target.value })}
            />
          </label>
          <label>
            Sig'im
            <input
              inputMode="numeric"
              value={form.capacity || ""}
              onChange={(event) =>
                setForm({ ...form, capacity: numeric(event.target.value) })
              }
            />
          </label>
          <fieldset className="education-management-v1656__weekdays">
            <legend>Dars kunlari</legend>
            {DAYS.map(([key, label]) => (
              <label key={key}>
                <input
                  type="checkbox"
                  checked={form.weekdays.includes(key)}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      weekdays: event.target.checked
                        ? [...form.weekdays, key]
                        : form.weekdays.filter((day) => day !== key),
                    })
                  }
                />
                {label}
              </label>
            ))}
          </fieldset>
          <div className="education-management-v1656__filters two">
            <label>
              Boshlanish
              <input
                type="time"
                value={form.lesson_from}
                onChange={(event) =>
                  setForm({ ...form, lesson_from: event.target.value })
                }
              />
            </label>
            <label>
              Tugash
              <input
                type="time"
                value={form.lesson_to}
                onChange={(event) =>
                  setForm({ ...form, lesson_to: event.target.value })
                }
              />
            </label>
          </div>
          <div className="education-management-v1656__filters two">
            <label>
              Kurs boshlanishi
              <input
                type="date"
                value={form.start_date}
                onChange={(event) =>
                  setForm({ ...form, start_date: event.target.value })
                }
              />
            </label>
            <label>
              Kurs tugashi
              <input
                type="date"
                value={form.end_date}
                onChange={(event) => setForm({ ...form, end_date: event.target.value })}
              />
            </label>
          </div>
          <label>
            To'lov hisoblash
            <select
              value={form.billing_type}
              onChange={(event) =>
                setForm({
                  ...form,
                  billing_type: event.target.value as "monthly" | "attendance",
                })
              }
            >
              <option value="monthly">Oylik</option>
              <option value="attendance">Qatnashuv bo'yicha</option>
            </select>
          </label>
          {form.billing_type === "attendance" ? (
            <div className="education-management-v1656__filters two">
              <label>
                Paketdagi darslar
                <input
                  inputMode="numeric"
                  value={form.package_lessons || ""}
                  onChange={(event) =>
                    setForm({ ...form, package_lessons: numeric(event.target.value) })
                  }
                />
              </label>
              <label>
                Paket narxi
                <input
                  inputMode="numeric"
                  value={price}
                  onChange={(event) => setPrice(event.target.value)}
                />
              </label>
            </div>
          ) : null}
        </Modal>
      ) : null}
    </Shell>
  );
}
