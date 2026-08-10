import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { ApiClient } from "../api/client";
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
} from "../api/types";
import "./EducationManagementV1656.css";


export type EducationManagementView =
  | "education-schedule"
  | "education-attendance"
  | "education-payments"
  | "education-teachers"
  | "education-payroll";

export type EducationManagementApi = Pick<
  ApiClient,
  | "getEducationGroups"
  | "getEducationAttendance"
  | "saveEducationAttendance"
  | "getEducationPaymentControl"
  | "getEducationPayments"
  | "createEducationPayment"
  | "voidEducationPayment"
  | "getEducationTeachers"
  | "createEducationTeacher"
  | "updateEducationTeacher"
  | "deleteEducationTeacher"
  | "getEducationPayroll"
  | "createEducationPayroll"
  | "deleteEducationPayroll"
>;

const DAYS = [
  { key: "mon", label: "Dushanba" },
  { key: "tue", label: "Seshanba" },
  { key: "wed", label: "Chorshanba" },
  { key: "thu", label: "Payshanba" },
  { key: "fri", label: "Juma" },
  { key: "sat", label: "Shanba" },
  { key: "sun", label: "Yakshanba" },
] as const;

const ATTENDANCE_OPTIONS: Array<{
  status: EducationAttendanceStatus;
  label: string;
  icon: string;
}> = [
  { status: "present", label: "Keldi", icon: "✓" },
  { status: "late", label: "Kechikdi", icon: "⏱" },
  { status: "excused", label: "Sababli", icon: "ℹ" },
  { status: "absent", label: "Sababsiz", icon: "✕" },
];

const EMPTY_CONTROL: EducationPaymentControl = {
  today: "",
  summary: { overdue: 0, due_today: 0, upcoming: 0, paid: 0, total_debt: 0 },
  students: [],
};

const EMPTY_PAYMENTS: EducationPaymentMonth = {
  payment_month: "",
  students: [],
  history: [],
};

const EMPTY_PAYROLL: EducationPayroll = {
  payment_month: "",
  teachers: [],
  history: [],
};

function localDate() {
  const value = new Date();
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
  return value.toISOString().slice(0, 10);
}

function localMonth() {
  return localDate().slice(0, 7);
}

function money(value: number) {
  return `${Math.trunc(Number(value || 0)).toLocaleString("uz-UZ")} so'm`;
}

function numeric(value: string) {
  return Number(value.replace(/[^0-9]/g, "")) || 0;
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "So'rov bajarilmadi.";
}

function EducationShell({
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
        <button type="button" onClick={onBack}>← Kabinetga qaytish</button>
        <div><h1>{title}</h1><p>{caption}</p></div>
      </header>
      {children}
    </main>
  );
}

function ErrorBox({ value }: { value: string }) {
  return value ? <p className="education-management-v1656__error" role="alert">{value}</p> : null;
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="education-management-v1656__empty">{children}</div>;
}

function GroupSelect({
  groups,
  value,
  onChange,
  all = false,
}: {
  groups: EducationGroup[];
  value: number;
  onChange: (value: number) => void;
  all?: boolean;
}) {
  return (
    <select value={value || ""} onChange={(event) => onChange(Number(event.target.value) || 0)}>
      <option value="">{all ? "Barcha guruhlar" : "Guruhni tanlang"}</option>
      {groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
    </select>
  );
}

function ScheduleView({ api, onBack }: { api: EducationManagementApi; onBack: () => void }) {
  const [groups, setGroups] = useState<EducationGroup[]>([]);
  const [groupId, setGroupId] = useState(0);
  const [teacher, setTeacher] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.getEducationGroups()
      .then((value) => { if (active) setGroups(value); })
      .catch((reason) => { if (active) setError(message(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api]);

  const teachers = useMemo(() => Array.from(new Set(
    groups.map((group) => group.teacher_name.trim()).filter(Boolean),
  )).sort((left, right) => left.localeCompare(right)), [groups]);
  const todayIndex = new Date().getDay();
  const today = todayIndex === 0 ? "sun" : (DAYS[todayIndex - 1]?.key ?? "mon");

  return (
    <EducationShell title="Dars jadvali" caption="Haftalik guruh va o'qituvchilar jadvali" onBack={onBack}>
      <ErrorBox value={error} />
      <section className="education-management-v1656__filters two">
        <GroupSelect groups={groups} value={groupId} onChange={setGroupId} all />
        <select value={teacher} onChange={(event) => setTeacher(event.target.value)}>
          <option value="">Barcha o'qituvchilar</option>
          {teachers.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
      </section>
      {loading ? <Empty>Jadval yuklanmoqda…</Empty> : DAYS.map((day) => {
        const lessons = groups
          .filter((group) => group.weekdays.split(",").includes(day.key))
          .filter((group) => !groupId || group.id === groupId)
          .filter((group) => !teacher || group.teacher_name === teacher)
          .sort((left, right) => (left.lesson_from || "99:99").localeCompare(right.lesson_from || "99:99"));
        return (
          <section className="education-management-v1656__day" key={day.key}>
            <header><h2 className={day.key === today ? "today" : ""}>{day.key === today ? "● " : ""}{day.label}</h2><small>{lessons.length} ta dars</small></header>
            {lessons.length ? lessons.map((group) => (
              <article className="education-management-v1656__lesson" key={group.id}>
                <strong>{group.lesson_from || "—"}<small>{group.lesson_to || "—"} gacha</small></strong>
                <div><b>{group.name}</b><small>📚 {group.course_name || "Kurs biriktirilmagan"}</small><small>{group.teacher_name ? `👤 ${group.teacher_name}` : "O'qituvchi belgilanmagan"}{group.room_name ? ` · 🚪 ${group.room_name}` : ""}</small></div>
              </article>
            )) : <p className="education-management-v1656__muted">Dars belgilanmagan</p>}
          </section>
        );
      })}
    </EducationShell>
  );
}

function AttendanceView({ api, onBack }: { api: EducationManagementApi; onBack: () => void }) {
  const [groups, setGroups] = useState<EducationGroup[]>([]);
  const [groupId, setGroupId] = useState(0);
  const [lessonDate, setLessonDate] = useState(localDate);
  const [students, setStudents] = useState<EducationAttendanceStudent[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    api.getEducationGroups()
      .then((value) => { if (active) setGroups(value); })
      .catch((reason) => { if (active) setError(message(reason)); });
    return () => { active = false; };
  }, [api]);

  async function load() {
    if (!groupId) { setError("Guruhni tanlang."); return; }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const value = await api.getEducationAttendance(groupId, lessonDate);
      setStudents(value.students);
      setLoaded(true);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  function mark(studentId: number, status: EducationAttendanceStatus) {
    setStudents((rows) => rows.map((row) => (
      row.student_id === studentId ? { ...row, attendance_status: status } : row
    )));
  }

  async function save() {
    const missing = students.filter((student) => !student.attendance_status).length;
    if (missing) { setError(`${missing} nafar o'quvchining davomati belgilanmagan.`); return; }
    setBusy(true);
    setError("");
    try {
      const result = await api.saveEducationAttendance({
        group_id: groupId,
        lesson_date: lessonDate,
        entries: students.map((student) => ({
          student_id: student.student_id,
          status: student.attendance_status,
          note: student.attendance_note,
        })),
      });
      setNotice(`${result.saved} nafar o'quvchi davomati saqlandi.`);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  const counts = Object.fromEntries(ATTENDANCE_OPTIONS.map(({ status }) => [
    status, students.filter((student) => student.attendance_status === status).length,
  ]));

  return (
    <EducationShell title="Davomat" caption="O'quvchilarning darsga qatnashuvi" onBack={onBack}>
      <section className="education-management-v1656__intro"><b>Davomatni belgilash</b><p>Guruh va sanani tanlang. Avval saqlangan davomat avtomatik ochiladi.</p></section>
      <ErrorBox value={error} />
      {notice ? <p className="education-management-v1656__success">{notice}</p> : null}
      <section className="education-management-v1656__filters two">
        <GroupSelect groups={groups} value={groupId} onChange={setGroupId} />
        <input type="date" value={lessonDate} onChange={(event) => setLessonDate(event.target.value)} />
      </section>
      <div className="education-management-v1656__actions two">
        <button type="button" disabled={busy} onClick={() => void load()}>Ko'rish</button>
        <button type="button" disabled={busy || !students.length} onClick={() => setStudents((rows) => rows.map((row) => ({ ...row, attendance_status: "present" })))}>Barchasi keldi</button>
      </div>
      {students.length ? <p className="education-management-v1656__summary-line">Jami: {students.length} · Keldi: {counts.present} · Kechikdi: {counts.late} · Sababli: {counts.excused} · Sababsiz: {counts.absent}</p> : null}
      {loaded && !students.length ? <Empty><h3>O'quvchilar yo'q</h3><p>Tanlangan guruhga avval o'quvchilarni biriktiring.</p></Empty> : null}
      <section className="education-management-v1656__cards">
        {students.map((student) => (
          <article key={student.student_id}>
            <header><div><b>{student.full_name}</b>{student.phone ? <small>{student.phone}</small> : null}</div><small>#{student.student_id}</small></header>
            <div className="education-management-v1656__attendance-buttons">
              {ATTENDANCE_OPTIONS.map((option) => (
                <button type="button" key={option.status} className={student.attendance_status === option.status ? `active ${option.status}` : ""} onClick={() => mark(student.student_id, option.status)}>{option.icon} {option.label}</button>
              ))}
            </div>
          </article>
        ))}
      </section>
      {students.length ? <button className="education-management-v1656__primary" type="button" disabled={busy} onClick={() => void save()}>Davomatni saqlash</button> : null}
    </EducationShell>
  );
}

type PaymentTarget = {
  student_id: number;
  full_name: string;
  payment_month: string;
  debt: number;
};

function PaymentModal({
  target,
  busy,
  onClose,
  onSave,
}: {
  target: PaymentTarget;
  busy: boolean;
  onClose: () => void;
  onSave: (amount: number, payType: "naqd" | "karta", note: string) => void;
}) {
  const [amount, setAmount] = useState(() => String(target.debt));
  const [payType, setPayType] = useState<"naqd" | "karta">("naqd");
  const [note, setNote] = useState("");
  return (
    <div className="education-management-v1656__modal-back">
      <section className="education-management-v1656__modal" role="dialog" aria-modal="true" aria-label="O'quvchi to'lovi">
        <h2>{target.full_name}</h2><p>Qoldi: {money(target.debt)}</p>
        <label>Oy<input type="month" readOnly value={target.payment_month} /></label>
        <label>To'lov summasi<input inputMode="numeric" value={amount} onChange={(event) => setAmount(event.target.value)} /></label>
        <label>To'lov turi<select value={payType} onChange={(event) => setPayType(event.target.value as "naqd" | "karta")}><option value="naqd">Naqd</option><option value="karta">Karta</option></select></label>
        <label>Izoh<input maxLength={200} value={note} onChange={(event) => setNote(event.target.value)} /></label>
        <div className="education-management-v1656__modal-actions"><button type="button" disabled={busy} onClick={onClose}>Bekor qilish</button><button type="button" disabled={busy} onClick={() => onSave(numeric(amount), payType, note)}>To'lovni qabul qilish</button></div>
      </section>
    </div>
  );
}

function PaymentControlPane({
  api,
  groups,
  canVoid,
}: {
  api: EducationManagementApi;
  groups: EducationGroup[];
  canVoid: boolean;
}) {
  const [groupId, setGroupId] = useState(0);
  const [data, setData] = useState(EMPTY_CONTROL);
  const [filter, setFilter] = useState<"attention" | EducationPaymentControlStatus | "all">("attention");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState(0);
  const [target, setTarget] = useState<PaymentTarget | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function reload(selected = groupId) {
    setLoading(true);
    setError("");
    try { setData(await api.getEducationPaymentControl(selected)); }
    catch (reason) { setError(message(reason)); }
    finally { setLoading(false); }
  }

  useEffect(() => { void reload(groupId); }, [api, groupId]);

  const rows = data.students.filter((student) => {
    if (filter === "attention" && !["overdue", "due_today", "upcoming"].includes(student.status)) return false;
    if (filter !== "attention" && filter !== "all" && student.status !== filter) return false;
    const query = search.trim().toLocaleLowerCase("uz");
    return !query || [student.full_name, student.phone, student.parent_phone, student.group_name].join(" ").toLocaleLowerCase("uz").includes(query);
  });

  async function pay(amount: number, payType: "naqd" | "karta", note: string) {
    if (!target || amount <= 0) { setError("To'lov summasini kiriting."); return; }
    setBusy(true);
    setError("");
    try {
      await api.createEducationPayment({ student_id: target.student_id, payment_month: target.payment_month, amount, pay_type: payType, note });
      setTarget(null);
      await reload();
    } catch (reason) { setError(message(reason)); }
    finally { setBusy(false); }
  }

  void canVoid;
  return (
    <>
      <ErrorBox value={error} />
      <nav className="education-management-v1656__tabs compact">
        {(["attention", "overdue", "due_today", "upcoming", "all"] as const).map((value) => <button type="button" key={value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{{ attention: "E'tibor kerak", overdue: "Muddati o'tgan", due_today: "Bugun", upcoming: "Yaqin", all: "Barchasi" }[value]}</button>)}
      </nav>
      <section className="education-management-v1656__filters two"><input type="search" placeholder="Ism yoki telefon..." value={search} onChange={(event) => setSearch(event.target.value)} /><GroupSelect groups={groups} value={groupId} onChange={setGroupId} all /></section>
      <section className="education-management-v1656__totals three"><span>Muddati o'tgan<b className="negative">{data.summary.overdue}</b></span><span>Bugun<b className="warning">{data.summary.due_today}</b></span><span>Jami qarz<b>{money(data.summary.total_debt)}</b></span></section>
      {loading ? <Empty>Yuklanmoqda…</Empty> : null}
      <section className="education-management-v1656__cards">
        {rows.map((student) => {
          const open = expanded === student.id;
          const statusLabel = { overdue: "Muddati o'tgan", due_today: "Bugun to'lanadi", upcoming: "Yaqinlashmoqda", paid: "To'langan" }[student.status];
          return <article key={student.id} className="collapsible"><button type="button" className="education-management-v1656__card-toggle" aria-expanded={open} onClick={() => setExpanded(open ? 0 : student.id)}><b>{student.full_name}</b><span>›</span></button>{open ? <div className="education-management-v1656__details"><p>Holat: <em className={student.status}>{statusLabel}</em><br />Guruh: {student.group_name || "Guruhsiz"}<br />To'lov turi: {student.billing_type === "attendance" ? "Dars paketi" : "Oylik"}<br />{student.billing_type === "attendance" ? `${student.lessons_done} dars hisoblandi · ${student.lessons_remaining} dars qoldi` : `Keyingi muddat: ${student.next_due || "—"}`}<br />Qarz: {money(student.debt)}</p>{student.debt ? <button className="education-management-v1656__primary" type="button" onClick={() => setTarget({ student_id: student.id, full_name: student.full_name, payment_month: student.payment_month, debt: student.payable_now || student.debt })}>To'lov olish</button> : null}</div> : null}</article>;
        })}
      </section>
      {!loading && !rows.length ? <Empty><h3>O'quvchi topilmadi</h3><p>Tanlangan holatda to'lov mavjud emas.</p></Empty> : null}
      {target ? <PaymentModal target={target} busy={busy} onClose={() => setTarget(null)} onSave={(amount, payType, note) => void pay(amount, payType, note)} /> : null}
    </>
  );
}

function PaymentHistoryPane({
  api,
  groups,
  canVoid,
}: {
  api: EducationManagementApi;
  groups: EducationGroup[];
  canVoid: boolean;
}) {
  const [month, setMonth] = useState(localMonth);
  const [groupId, setGroupId] = useState(0);
  const [data, setData] = useState(EMPTY_PAYMENTS);
  const [expanded, setExpanded] = useState(0);
  const [target, setTarget] = useState<PaymentTarget | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function reload() {
    setLoading(true); setError("");
    try { setData(await api.getEducationPayments(month, groupId)); }
    catch (reason) { setError(message(reason)); }
    finally { setLoading(false); }
  }
  useEffect(() => { void reload(); }, [api, month, groupId]);

  async function pay(amount: number, payType: "naqd" | "karta", note: string) {
    if (!target || amount <= 0) { setError("To'lov summasini kiriting."); return; }
    setBusy(true); setError("");
    try { await api.createEducationPayment({ student_id: target.student_id, payment_month: target.payment_month, amount, pay_type: payType, note }); setTarget(null); await reload(); }
    catch (reason) { setError(message(reason)); }
    finally { setBusy(false); }
  }

  async function voidPayment(paymentId: number) {
    const reason = window.prompt("To'lovni bekor qilish sababini kiriting:")?.trim();
    if (!reason) return;
    setBusy(true); setError("");
    try { await api.voidEducationPayment(paymentId, reason); await reload(); }
    catch (problem) { setError(message(problem)); }
    finally { setBusy(false); }
  }

  const totals = data.students.reduce((result, student) => ({ expected: result.expected + student.expected, paid: result.paid + student.paid, debt: result.debt + student.debt }), { expected: 0, paid: 0, debt: 0 });
  return (
    <>
      <ErrorBox value={error} />
      <section className="education-management-v1656__filters two"><input type="month" value={month} onChange={(event) => setMonth(event.target.value)} /><GroupSelect groups={groups} value={groupId} onChange={setGroupId} all /></section>
      <section className="education-management-v1656__totals three"><span>Hisoblandi<b>{money(totals.expected)}</b></span><span>To'landi<b className="positive">{money(totals.paid)}</b></span><span>Qarz<b className="negative">{money(totals.debt)}</b></span></section>
      {loading ? <Empty>Yuklanmoqda…</Empty> : null}
      <section className="education-management-v1656__cards">
        {data.students.map((student: EducationPaymentStudent) => {
          const open = expanded === student.student_id;
          const full = student.expected > 0 && student.debt === 0;
          const status = full ? "To'langan" : student.paid > 0 ? "Qisman" : "To'lanmagan";
          return <article key={student.student_id} className="collapsible"><button type="button" className="education-management-v1656__card-toggle" onClick={() => setExpanded(open ? 0 : student.student_id)}><b>{student.full_name}</b><span>›</span></button>{open ? <div className="education-management-v1656__details"><p>Guruh: {student.group_name || "Guruhsiz"}<br />Holat: {status}<br />Hisoblandi: {money(student.expected)}<br />To'landi: {money(student.paid)}<br />Qoldi: {money(student.debt)}{student.billing_type === "attendance" ? <><br />Darslar: {student.chargeable_lessons} × {money(student.per_lesson_price)}</> : null}</p>{student.debt ? <button className="education-management-v1656__primary" type="button" onClick={() => setTarget({ student_id: student.student_id, full_name: student.full_name, payment_month: month, debt: student.debt })}>To'lov qabul qilish</button> : null}</div> : null}</article>;
        })}
      </section>
      <h2 className="education-management-v1656__section-title">To'lovlar tarixi</h2>
      <section className="education-management-v1656__history">{data.history.map((payment) => <article key={payment.id} className={payment.voided_at ? "voided" : ""}><div><b>{payment.full_name}</b><small>{money(payment.amount)} · {payment.pay_type === "karta" ? "Karta" : "Naqd"}{payment.note ? ` · ${payment.note}` : ""}{payment.voided_at ? ` · Bekor qilingan: ${payment.void_reason || "Sabab ko'rsatilmagan"}` : ""}</small></div>{canVoid && !payment.voided_at ? <button type="button" disabled={busy} onClick={() => void voidPayment(payment.id)}>Bekor qilish</button> : null}</article>)}</section>
      {!data.history.length ? <p className="education-management-v1656__muted">Bu oy uchun to'lovlar yo'q.</p> : null}
      {target ? <PaymentModal target={target} busy={busy} onClose={() => setTarget(null)} onSave={(amount, payType, note) => void pay(amount, payType, note)} /> : null}
    </>
  );
}

function PaymentsView({ api, onBack, canVoid }: { api: EducationManagementApi; onBack: () => void; canVoid: boolean }) {
  const [view, setView] = useState<"control" | "payments">("control");
  const [groups, setGroups] = useState<EducationGroup[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api.getEducationGroups().then((value) => { if (active) setGroups(value); }).catch((reason) => { if (active) setError(message(reason)); });
    return () => { active = false; };
  }, [api]);
  return <EducationShell title="To'lov nazorati" caption="Muddati kelgan va yaqin to'lovlar" onBack={onBack}><ErrorBox value={error} /><nav className="education-management-v1656__tabs"><button type="button" className={view === "control" ? "active" : ""} onClick={() => setView("control")}>To'lov nazorati</button><button type="button" className={view === "payments" ? "active" : ""} onClick={() => setView("payments")}>To'lovlar va tarix</button></nav>{view === "control" ? <PaymentControlPane api={api} groups={groups} canVoid={canVoid} /> : <PaymentHistoryPane api={api} groups={groups} canVoid={canVoid} />}</EducationShell>;
}

const EMPTY_TEACHER: EducationTeacherWrite = { full_name: "", phone: "", specialty: "", hired_date: localDate(), salary_type: "monthly", salary_amount: 0, note: "" };

function TeachersView({ api, onBack }: { api: EducationManagementApi; onBack: () => void }) {
  const [teachers, setTeachers] = useState<EducationTeacher[]>([]);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<EducationTeacher | null | undefined>();
  const [form, setForm] = useState<EducationTeacherWrite>(EMPTY_TEACHER);
  const [salary, setSalary] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function reload() {
    setLoading(true); setError("");
    try { setTeachers(await api.getEducationTeachers()); }
    catch (reason) { setError(message(reason)); }
    finally { setLoading(false); }
  }
  useEffect(() => { void reload(); }, [api]);

  function open(teacher?: EducationTeacher) {
    setEditing(teacher ?? null);
    setForm(teacher ? { full_name: teacher.full_name, phone: teacher.phone, specialty: teacher.specialty, hired_date: teacher.hired_date, salary_type: teacher.salary_type, salary_amount: teacher.salary_amount, note: teacher.note } : { ...EMPTY_TEACHER, hired_date: localDate() });
    setSalary(teacher?.salary_amount ? String(teacher.salary_amount) : "");
  }

  async function save() {
    if (!form.full_name.trim()) { setError("O'qituvchi ism-familiyasini kiriting."); return; }
    setBusy(true); setError("");
    const body = { ...form, salary_amount: numeric(salary) };
    try { if (editing) await api.updateEducationTeacher(editing.id, body); else await api.createEducationTeacher(body); setEditing(undefined); await reload(); }
    catch (reason) { setError(message(reason)); }
    finally { setBusy(false); }
  }

  async function remove() {
    if (!editing || !window.confirm("O'qituvchi faol ro'yxatdan chiqarilsinmi? Guruhlardagi eski nomi saqlanadi.")) return;
    setBusy(true); setError("");
    try { await api.deleteEducationTeacher(editing.id); setEditing(undefined); await reload(); }
    catch (reason) { setError(message(reason)); }
    finally { setBusy(false); }
  }

  const rows = teachers.filter((teacher) => !search.trim() || [teacher.full_name, teacher.phone, teacher.specialty].join(" ").toLocaleLowerCase("uz").includes(search.trim().toLocaleLowerCase("uz")));
  return <EducationShell title="O'qituvchilar" caption="O'qituvchi, fan va ish haqi" onBack={onBack}><ErrorBox value={error} /><section className="education-management-v1656__toolbar"><div><b>O'qituvchilar</b><small>{teachers.length} nafar faol o'qituvchi</small></div><button type="button" onClick={() => open()}>+ O'qituvchi</button></section><input className="education-management-v1656__search" type="search" placeholder="Ism yoki fan bo'yicha qidirish..." value={search} onChange={(event) => setSearch(event.target.value)} />{loading ? <Empty>Yuklanmoqda…</Empty> : null}<section className="education-management-v1656__cards">{rows.map((teacher) => <button className="education-management-v1656__teacher" type="button" key={teacher.id} onClick={() => open(teacher)}><span>🧑‍🏫</span><div><b>{teacher.full_name}</b><small>{teacher.specialty || "Mutaxassislik belgilanmagan"}</small><em>{teacher.phone ? `📞 ${teacher.phone} · ` : ""}👥 {teacher.group_count} guruh{teacher.salary_amount ? ` · 💰 ${money(teacher.salary_amount)} ${teacher.salary_type === "per_lesson" ? "/ dars" : "/ oy"}` : ""}</em></div><i>›</i></button>)}</section>{!loading && !rows.length ? <Empty><h3>O'qituvchi topilmadi</h3><p>Yangi o'qituvchi qo'shing yoki qidiruvni o'zgartiring.</p></Empty> : null}{editing !== undefined ? <div className="education-management-v1656__modal-back"><section className="education-management-v1656__modal" role="dialog" aria-modal="true"><h2>{editing ? "O'qituvchini tahrirlash" : "Yangi o'qituvchi"}</h2><label>Ism-familiya<input value={form.full_name} maxLength={120} onChange={(event) => setForm({ ...form, full_name: event.target.value })} /></label><label>Telefon raqami<input value={form.phone} maxLength={30} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label><label>Fan yoki mutaxassisligi<input value={form.specialty} maxLength={120} onChange={(event) => setForm({ ...form, specialty: event.target.value })} /></label><label>Ishga kirgan sana<input type="date" value={form.hired_date} onChange={(event) => setForm({ ...form, hired_date: event.target.value })} /></label><label>Ish haqi turi<select value={form.salary_type} onChange={(event) => setForm({ ...form, salary_type: event.target.value as "monthly" | "per_lesson" })}><option value="monthly">Oylik maosh</option><option value="per_lesson">Har bir dars uchun</option></select></label><label>Ish haqi summasi<input inputMode="numeric" value={salary} onChange={(event) => setSalary(event.target.value)} /></label><label>Izoh<textarea value={form.note} maxLength={500} onChange={(event) => setForm({ ...form, note: event.target.value })} /></label><div className="education-management-v1656__modal-actions">{editing ? <button type="button" className="danger" disabled={busy} onClick={() => void remove()}>Ro'yxatdan chiqarish</button> : null}<button type="button" disabled={busy} onClick={() => setEditing(undefined)}>Bekor qilish</button><button type="button" disabled={busy} onClick={() => void save()}>Saqlash</button></div></section></div> : null}</EducationShell>;
}

function PayrollModal({ target, month, busy, onClose, onSave }: { target: EducationPayrollTeacher; month: string; busy: boolean; onClose: () => void; onSave: (amount: number, payType: "naqd" | "karta", note: string) => void }) {
  const [amount, setAmount] = useState(String(target.debt));
  const [payType, setPayType] = useState<"naqd" | "karta">("naqd");
  const [note, setNote] = useState("");
  return <div className="education-management-v1656__modal-back"><section className="education-management-v1656__modal" role="dialog" aria-modal="true"><h2>{target.full_name}</h2><p>Hisoblandi: {money(target.expected)} · To'landi: {money(target.paid)} · Qoldi: {money(target.debt)}</p><label>Oy<input type="month" readOnly value={month} /></label><label>To'lov summasi<input inputMode="numeric" value={amount} onChange={(event) => setAmount(event.target.value)} /></label><label>To'lov turi<select value={payType} onChange={(event) => setPayType(event.target.value as "naqd" | "karta")}><option value="naqd">Naqd</option><option value="karta">Karta</option></select></label><label>Izoh<input maxLength={200} value={note} onChange={(event) => setNote(event.target.value)} /></label><div className="education-management-v1656__modal-actions"><button type="button" disabled={busy} onClick={onClose}>Bekor qilish</button><button type="button" disabled={busy} onClick={() => onSave(numeric(amount), payType, note)}>Maoshni to'lash</button></div></section></div>;
}

function PayrollView({ api, onBack }: { api: EducationManagementApi; onBack: () => void }) {
  const [month, setMonth] = useState(localMonth);
  const [data, setData] = useState(EMPTY_PAYROLL);
  const [target, setTarget] = useState<EducationPayrollTeacher | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function reload() { setLoading(true); setError(""); try { setData(await api.getEducationPayroll(month)); } catch (reason) { setError(message(reason)); } finally { setLoading(false); } }
  useEffect(() => { void reload(); }, [api, month]);
  async function pay(amount: number, payType: "naqd" | "karta", note: string) { if (!target || amount <= 0) { setError("To'lov summasini kiriting."); return; } setBusy(true); setError(""); try { await api.createEducationPayroll({ teacher_id: target.id, payment_month: month, amount, pay_type: payType, note }); setTarget(null); await reload(); } catch (reason) { setError(message(reason)); } finally { setBusy(false); } }
  async function remove(paymentId: number) { if (!window.confirm("Maosh to'lovi va unga bog'langan xarajat o'chirilsinmi?")) return; setBusy(true); setError(""); try { await api.deleteEducationPayroll(paymentId); await reload(); } catch (reason) { setError(message(reason)); } finally { setBusy(false); } }
  const totals = data.teachers.reduce((result, teacher) => ({ expected: result.expected + teacher.expected, paid: result.paid + teacher.paid, debt: result.debt + teacher.debt }), { expected: 0, paid: 0, debt: 0 });
  return <EducationShell title="O'qituvchi maoshi" caption="Oy bo'yicha hisoblangan va to'langan maoshlar" onBack={onBack}><ErrorBox value={error} /><input className="education-management-v1656__month" type="month" value={month} onChange={(event) => setMonth(event.target.value)} /><section className="education-management-v1656__totals three"><span>Hisoblandi<b>{money(totals.expected)}</b></span><span>To'landi<b className="positive">{money(totals.paid)}</b></span><span>Qoldi<b className="negative">{money(totals.debt)}</b></span></section>{loading ? <Empty>Yuklanmoqda…</Empty> : null}<section className="education-management-v1656__cards">{data.teachers.map((teacher) => <article key={teacher.id}><header><div><b>{teacher.full_name}</b><small>{teacher.salary_type === "per_lesson" ? `${teacher.lesson_count} dars × ${money(teacher.salary_amount)}` : `Oylik ${money(teacher.salary_amount)}`}</small></div><em>{teacher.debt > 0 ? `Qoldi ${money(teacher.debt)}` : teacher.expected ? "To'langan" : "Hisob yo'q"}</em></header><p>Hisoblandi: {money(teacher.expected)} · To'landi: {money(teacher.paid)}</p>{teacher.debt > 0 ? <button className="education-management-v1656__primary" type="button" onClick={() => setTarget(teacher)}>Maosh to'lash</button> : null}</article>)}</section>{!loading && !data.teachers.length ? <Empty><h3>O'qituvchilar yo'q</h3></Empty> : null}<h2 className="education-management-v1656__section-title">Maosh to'lovlari tarixi</h2><section className="education-management-v1656__history">{data.history.map((payment) => <article key={payment.id}><div><b>{payment.full_name}</b><small>{money(payment.amount)} · {payment.pay_type === "karta" ? "Karta" : "Naqd"}{payment.note ? ` · ${payment.note}` : ""}</small></div><button type="button" disabled={busy} onClick={() => void remove(payment.id)}>O'chirish</button></article>)}</section>{!data.history.length ? <p className="education-management-v1656__muted">Bu oyda maosh to'lovi yo'q.</p> : null}{target ? <PayrollModal target={target} month={month} busy={busy} onClose={() => setTarget(null)} onSave={(amount, payType, note) => void pay(amount, payType, note)} /> : null}</EducationShell>;
}

export function EducationManagementV1656({ api, view, onBack, canVoidPayments = true }: { api: EducationManagementApi; view: EducationManagementView; onBack: () => void; canVoidPayments?: boolean }) {
  if (view === "education-schedule") return <ScheduleView api={api} onBack={onBack} />;
  if (view === "education-attendance") return <AttendanceView api={api} onBack={onBack} />;
  if (view === "education-payments") return <PaymentsView api={api} onBack={onBack} canVoid={canVoidPayments} />;
  if (view === "education-teachers") return <TeachersView api={api} onBack={onBack} />;
  return <PayrollView api={api} onBack={onBack} />;
}
