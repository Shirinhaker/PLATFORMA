import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { ApiClient } from "../api/client";
import type {
  EducationGroup,
  EducationGroupWrite,
  EducationStudent,
  EducationStudentCard,
  EducationStudentWrite,
  EducationTeacher,
} from "../api/types";

export type EducationDirectoryApi = Pick<
  ApiClient,
  | "getBusinessOnlineResource"
  | "getEducationGroups"
  | "createEducationGroup"
  | "updateEducationGroup"
  | "deleteEducationGroup"
  | "getEducationTeachers"
  | "getEducationStudents"
  | "createEducationStudent"
  | "updateEducationStudent"
  | "deleteEducationStudent"
  | "getEducationStudentCard"
  | "transferEducationStudent"
>;

const DAYS = [
  ["mon", "Du"],
  ["tue", "Se"],
  ["wed", "Chor"],
  ["thu", "Pay"],
  ["fri", "Ju"],
  ["sat", "Sha"],
  ["sun", "Yak"],
] as const;

const EMPTY_GROUP: EducationGroupWrite = {
  name: "",
  course_item_id: null,
  teacher_id: null,
  teacher_name: "",
  room_name: "",
  capacity: 0,
  weekdays: [],
  lesson_from: "",
  lesson_to: "",
  start_date: "",
  end_date: "",
  billing_type: "monthly",
  package_lessons: 0,
  package_price: 0,
};

const EMPTY_STUDENT: EducationStudentWrite = {
  full_name: "",
  group_id: null,
  phone: "",
  parent_name: "",
  parent_phone: "",
  birth_date: "",
  joined_date: "",
  monthly_fee: 0,
  payment_start_date: "",
  lesson_package_override: 0,
  note: "",
};

function localDate() {
  const value = new Date();
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
  return value.toISOString().slice(0, 10);
}

function money(value: number) {
  return `${Math.trunc(Number(value || 0)).toLocaleString("uz-UZ")} so'm`;
}

function numeric(value: string) {
  return Number(value.replace(/[^0-9]/g, "")) || 0;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So'rov bajarilmadi.";
}

function Shell({
  title,
  caption,
  onBack,
  children,
}: {
  title: string;
  caption: string;
  onBack: () => void;
  children: ReactNode;
}) {
  return (
    <main className="education-management-v1656">
      <header className="education-management-v1656__heading">
        <button type="button" onClick={onBack}>
          ← Kabinetga qaytish
        </button>
        <div>
          <h1>{title}</h1>
          <p>{caption}</p>
        </div>
      </header>
      {children}
    </main>
  );
}

function ErrorBox({ value }: { value: string }) {
  return value ? (
    <p className="education-management-v1656__error" role="alert">
      {value}
    </p>
  ) : null;
}

function Modal({
  title,
  children,
  actions,
}: {
  title: string;
  children: ReactNode;
  actions: ReactNode;
}) {
  return (
    <div className="education-management-v1656__modal-back">
      <section
        className="education-management-v1656__modal"
        role="dialog"
        aria-modal="true"
      >
        <h2>{title}</h2>
        {children}
        <div className="education-management-v1656__modal-actions">{actions}</div>
      </section>
    </div>
  );
}

export function EducationGroupsV1656({
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

export function EducationStudentsV1656({
  api,
  onBack,
}: {
  api: EducationDirectoryApi;
  onBack: () => void;
}) {
  const [groups, setGroups] = useState<EducationGroup[]>([]);
  const [students, setStudents] = useState<EducationStudent[]>([]);
  const [search, setSearch] = useState("");
  const [groupId, setGroupId] = useState(0);
  const [editing, setEditing] = useState<EducationStudent | null | undefined>();
  const [form, setForm] = useState<EducationStudentWrite>(EMPTY_STUDENT);
  const [fee, setFee] = useState("");
  const [card, setCard] = useState<EducationStudentCard | null>(null);
  const [transfer, setTransfer] = useState(false);
  const [transferGroup, setTransferGroup] = useState(0);
  const [transferDate, setTransferDate] = useState(localDate);
  const [transferNote, setTransferNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function reload() {
    setLoading(true);
    setError("");
    try {
      const [groupRows, studentRows] = await Promise.all([
        api.getEducationGroups(),
        api.getEducationStudents(),
      ]);
      setGroups(groupRows);
      setStudents(studentRows);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void reload();
  }, [api]);

  function open(student?: EducationStudent) {
    setEditing(student ?? null);
    setForm(
      student
        ? {
            full_name: student.full_name,
            group_id: student.group_id,
            phone: student.phone,
            parent_name: student.parent_name,
            parent_phone: student.parent_phone,
            birth_date: student.birth_date,
            joined_date: student.joined_date,
            monthly_fee: student.monthly_fee,
            payment_start_date: student.payment_start_date,
            lesson_package_override: student.lesson_package_override,
            note: student.note,
          }
        : {
            ...EMPTY_STUDENT,
            joined_date: localDate(),
            payment_start_date: localDate(),
          },
    );
    setFee(student?.monthly_fee ? String(student.monthly_fee) : "");
  }

  async function save() {
    if (!form.full_name.trim()) {
      setError("O'quvchi ism-familiyasini kiriting.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = { ...form, monthly_fee: numeric(fee) };
      if (editing) await api.updateEducationStudent(editing.id, body);
      else await api.createEducationStudent(body);
      setEditing(undefined);
      await reload();
      if (card && editing) await openCard(editing.id);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!editing || !window.confirm("O'quvchi faol ro'yxatdan chiqarilsinmi?")) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteEducationStudent(editing.id);
      setEditing(undefined);
      setCard(null);
      await reload();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function openCard(studentId: number) {
    setError("");
    try {
      setCard(await api.getEducationStudentCard(studentId));
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function move() {
    if (!card || !transferGroup || !transferDate) {
      setError("Yangi guruh va o'tkazish sanasini tanlang.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.transferEducationStudent(card.student.id, {
        group_id: transferGroup,
        transfer_date: transferDate,
        note: transferNote,
      });
      setTransfer(false);
      await reload();
      await openCard(card.student.id);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  const rows = useMemo(
    () =>
      students.filter((student) => {
        if (groupId && student.group_id !== groupId) return false;
        const query = search.trim().toLocaleLowerCase("uz");
        return (
          !query ||
          [
            student.full_name,
            student.phone,
            student.parent_name,
            student.parent_phone,
            student.group_name,
          ]
            .join(" ")
            .toLocaleLowerCase("uz")
            .includes(query)
        );
      }),
    [students, groupId, search],
  );

  if (card)
    return (
      <Shell
        title="O'quvchi kartasi"
        caption={card.student.full_name}
        onBack={() => setCard(null)}
      >
        <ErrorBox value={error} />
        <section className="education-management-v1656__intro">
          <h2>{card.student.full_name}</h2>
          <p>
            {card.student.group_name || "Guruhga biriktirilmagan"}
            {card.student.course_name ? ` · ${card.student.course_name}` : ""}
            <br />
            📞 {card.student.phone || "—"}
            <br />
            👪 {card.student.parent_name || "Ota-ona"} ·{" "}
            {card.student.parent_phone || "—"}
          </p>
        </section>
        <section className="education-management-v1656__totals three">
          <span>
            Hisoblandi<b>{money(card.payment.expected)}</b>
          </span>
          <span>
            To'landi<b className="positive">{money(card.payment.paid)}</b>
          </span>
          <span>
            Qarz
            <b className={card.payment.debt ? "negative" : "positive"}>
              {money(card.payment.debt)}
            </b>
          </span>
        </section>
        <section className="education-management-v1656__totals three">
          <span>
            Jami dars<b>{card.attendance.total}</b>
          </span>
          <span>
            Qatnashdi<b>{card.attendance.attended}</b>
          </span>
          <span>
            Davomat<b>{card.attendance.percent}%</b>
          </span>
        </section>
        <div className="education-management-v1656__actions two">
          <button type="button" onClick={() => open(card.student)}>
            Tahrirlash
          </button>
          <button
            type="button"
            onClick={() => {
              setTransferGroup(0);
              setTransferDate(localDate());
              setTransferNote("");
              setTransfer(true);
            }}
          >
            Guruhga ko'chirish
          </button>
        </div>
        <h2 className="education-management-v1656__section-title">Guruhlar tarixi</h2>
        <section className="education-management-v1656__history">
          {card.group_history.map((row) => (
            <article key={row.id}>
              <div>
                <b>{row.group_name || "Guruh"}</b>
                <small>
                  {row.started_date || "—"} — {row.ended_date || "Hozirgacha"}
                  {row.note ? ` · ${row.note}` : ""}
                </small>
              </div>
            </article>
          ))}
        </section>
        {!card.group_history.length ? (
          <p className="education-management-v1656__muted">Guruh tarixi yo'q.</p>
        ) : null}
        <h2 className="education-management-v1656__section-title">To'lovlar tarixi</h2>
        <section className="education-management-v1656__history">
          {card.payments.map((row) => (
            <article className={row.voided_at ? "voided" : ""} key={row.id}>
              <div>
                <b>{money(row.amount)}</b>
                <small>
                  {row.payment_month} · {row.pay_type === "karta" ? "Karta" : "Naqd"}
                  {row.note ? ` · ${row.note}` : ""}
                  {row.voided_at ? " · Bekor qilingan" : ""}
                </small>
              </div>
            </article>
          ))}
        </section>
        {!card.payments.length ? (
          <p className="education-management-v1656__muted">To'lovlar yo'q.</p>
        ) : null}
        {editing !== undefined ? (
          <StudentModal
            editing={editing}
            form={form}
            fee={fee}
            groups={groups}
            busy={busy}
            setForm={setForm}
            setFee={setFee}
            onClose={() => setEditing(undefined)}
            onSave={() => void save()}
            onRemove={() => void remove()}
          />
        ) : null}
        {transfer ? (
          <Modal
            title="Guruhga ko'chirish"
            actions={
              <>
                <button
                  disabled={busy}
                  type="button"
                  onClick={() => setTransfer(false)}
                >
                  Bekor qilish
                </button>
                <button disabled={busy} type="button" onClick={() => void move()}>
                  Ko'chirish
                </button>
              </>
            }
          >
            <p>Joriy guruh: {card.student.group_name || "biriktirilmagan"}</p>
            <label>
              Yangi guruh
              <select
                value={transferGroup || ""}
                onChange={(event) => setTransferGroup(Number(event.target.value) || 0)}
              >
                <option value="">Guruhni tanlang</option>
                {groups
                  .filter((group) => group.id !== card.student.group_id)
                  .map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              O'tkazish sanasi
              <input
                type="date"
                value={transferDate}
                onChange={(event) => setTransferDate(event.target.value)}
              />
            </label>
            <label>
              Izoh
              <textarea
                maxLength={300}
                value={transferNote}
                onChange={(event) => setTransferNote(event.target.value)}
              />
            </label>
          </Modal>
        ) : null}
      </Shell>
    );

  return (
    <Shell title="O'quvchilar" caption="O'quvchi va to'lov holatlari" onBack={onBack}>
      <ErrorBox value={error} />
      <section className="education-management-v1656__toolbar">
        <div>
          <b>O'quvchilar</b>
          <small>{students.length} nafar faol o'quvchi</small>
        </div>
        <button type="button" onClick={() => open()}>
          + O'quvchi
        </button>
      </section>
      <section className="education-management-v1656__filters two">
        <input
          type="search"
          placeholder="Ism yoki telefon..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select
          value={groupId || ""}
          onChange={(event) => setGroupId(Number(event.target.value) || 0)}
        >
          <option value="">Barcha guruhlar</option>
          {groups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </select>
      </section>
      {loading ? (
        <div className="education-management-v1656__empty">Yuklanmoqda…</div>
      ) : null}
      <section className="education-management-v1656__cards">
        {rows.map((student) => (
          <article key={student.id}>
            <header>
              <div>
                <b>{student.full_name}</b>
                <small>
                  {student.group_name || "Guruhga biriktirilmagan"}
                  {student.course_name ? ` · ${student.course_name}` : ""}
                </small>
              </div>
              <em>›</em>
            </header>
            <p>
              📞 {student.phone || "—"}
              <br />
              👪 {student.parent_name || "Ota-ona"} · {student.parent_phone || "—"}
            </p>
            <button
              className="education-management-v1656__primary"
              type="button"
              onClick={() => void openCard(student.id)}
            >
              To'liq kartani ochish
            </button>
          </article>
        ))}
      </section>
      {!loading && !rows.length ? (
        <div className="education-management-v1656__empty">
          <h3>O'quvchi topilmadi</h3>
          <p>Yangi o'quvchi qo'shing yoki qidiruvni o'zgartiring.</p>
        </div>
      ) : null}
      {editing !== undefined ? (
        <StudentModal
          editing={editing}
          form={form}
          fee={fee}
          groups={groups}
          busy={busy}
          setForm={setForm}
          setFee={setFee}
          onClose={() => setEditing(undefined)}
          onSave={() => void save()}
          onRemove={() => void remove()}
        />
      ) : null}
    </Shell>
  );
}

function StudentModal({
  editing,
  form,
  fee,
  groups,
  busy,
  setForm,
  setFee,
  onClose,
  onSave,
  onRemove,
}: {
  editing: EducationStudent | null;
  form: EducationStudentWrite;
  fee: string;
  groups: EducationGroup[];
  busy: boolean;
  setForm: (value: EducationStudentWrite) => void;
  setFee: (value: string) => void;
  onClose: () => void;
  onSave: () => void;
  onRemove: () => void;
}) {
  return (
    <Modal
      title={editing ? "O'quvchini tahrirlash" : "Yangi o'quvchi"}
      actions={
        <>
          {editing ? (
            <button className="danger" disabled={busy} type="button" onClick={onRemove}>
              Ro'yxatdan chiqarish
            </button>
          ) : null}
          <button disabled={busy} type="button" onClick={onClose}>
            Bekor qilish
          </button>
          <button disabled={busy} type="button" onClick={onSave}>
            Saqlash
          </button>
        </>
      }
    >
      <label>
        Ism-familiya
        <input
          maxLength={120}
          value={form.full_name}
          onChange={(event) => setForm({ ...form, full_name: event.target.value })}
        />
      </label>
      <label>
        Guruh
        <select
          disabled={Boolean(editing)}
          value={form.group_id || ""}
          onChange={(event) =>
            setForm({ ...form, group_id: Number(event.target.value) || null })
          }
        >
          <option value="">Guruhni tanlang</option>
          {groups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </select>
      </label>
      {editing ? (
        <p>
          Guruhni almashtirish uchun o'quvchi kartasidagi “Guruhga ko'chirish”
          tugmasidan foydalaning.
        </p>
      ) : null}
      <div className="education-management-v1656__filters two">
        <label>
          Telefon
          <input
            maxLength={40}
            value={form.phone}
            onChange={(event) => setForm({ ...form, phone: event.target.value })}
          />
        </label>
        <label>
          Ota-ona
          <input
            maxLength={160}
            value={form.parent_name}
            onChange={(event) => setForm({ ...form, parent_name: event.target.value })}
          />
        </label>
      </div>
      <label>
        Ota-ona telefoni
        <input
          maxLength={40}
          value={form.parent_phone}
          onChange={(event) => setForm({ ...form, parent_phone: event.target.value })}
        />
      </label>
      <div className="education-management-v1656__filters two">
        <label>
          Tug'ilgan sana
          <input
            type="date"
            value={form.birth_date}
            onChange={(event) => setForm({ ...form, birth_date: event.target.value })}
          />
        </label>
        <label>
          Qabul sanasi
          <input
            type="date"
            value={form.joined_date}
            onChange={(event) => setForm({ ...form, joined_date: event.target.value })}
          />
        </label>
      </div>
      <label>
        Oylik to'lov
        <input
          inputMode="numeric"
          value={fee}
          onChange={(event) => setFee(event.target.value)}
        />
      </label>
      <div className="education-management-v1656__filters two">
        <label>
          To'lov boshlanishi
          <input
            type="date"
            value={form.payment_start_date}
            onChange={(event) =>
              setForm({ ...form, payment_start_date: event.target.value })
            }
          />
        </label>
        <label>
          Shaxsiy dars paketi
          <input
            inputMode="numeric"
            value={form.lesson_package_override || ""}
            onChange={(event) =>
              setForm({ ...form, lesson_package_override: numeric(event.target.value) })
            }
          />
        </label>
      </div>
      <label>
        Izoh
        <textarea
          maxLength={2000}
          value={form.note}
          onChange={(event) => setForm({ ...form, note: event.target.value })}
        />
      </label>
    </Modal>
  );
}
