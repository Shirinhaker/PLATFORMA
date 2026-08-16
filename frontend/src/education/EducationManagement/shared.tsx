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
import { AttendanceView } from "./AttendanceView";
import { PaymentControlPane } from "./PaymentControlPane";
import { PaymentHistoryPane } from "./PaymentHistoryPane";
import { PayrollView } from "./PayrollView";
import { ScheduleView } from "./ScheduleView";
import { TeachersView } from "./TeachersView";

export type EducationManagementView =
  | "education-groups"
  | "education-students"
  | "education-schedule"
  | "education-attendance"
  | "education-payments"
  | "education-teachers"
  | "education-payroll";

export type EducationManagementApi = Pick<
  ApiClient,
  | "getBusinessOnlineResource"
  | "getEducationGroups"
  | "createEducationGroup"
  | "updateEducationGroup"
  | "deleteEducationGroup"
  | "getEducationStudents"
  | "createEducationStudent"
  | "updateEducationStudent"
  | "deleteEducationStudent"
  | "getEducationStudentCard"
  | "transferEducationStudent"
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

export const DAYS = [
  { key: "mon", label: "Dushanba" },
  { key: "tue", label: "Seshanba" },
  { key: "wed", label: "Chorshanba" },
  { key: "thu", label: "Payshanba" },
  { key: "fri", label: "Juma" },
  { key: "sat", label: "Shanba" },
  { key: "sun", label: "Yakshanba" },
] as const;

export const ATTENDANCE_OPTIONS: Array<{
  status: EducationAttendanceStatus;
  label: string;
  icon: string;
}> = [
  { status: "present", label: "Keldi", icon: "✓" },
  { status: "late", label: "Kechikdi", icon: "⏱" },
  { status: "excused", label: "Sababli", icon: "ℹ" },
  { status: "absent", label: "Sababsiz", icon: "✕" },
];

export const EMPTY_CONTROL: EducationPaymentControl = {
  today: "",
  summary: { overdue: 0, due_today: 0, upcoming: 0, paid: 0, total_debt: 0 },
  students: [],
};

export const EMPTY_PAYMENTS: EducationPaymentMonth = {
  payment_month: "",
  students: [],
  history: [],
};

export const EMPTY_PAYROLL: EducationPayroll = {
  payment_month: "",
  teachers: [],
  history: [],
};

export function localDate() {
  const value = new Date();
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
  return value.toISOString().slice(0, 10);
}

export function localMonth() {
  return localDate().slice(0, 7);
}

export function money(value: number) {
  return `${Math.trunc(Number(value || 0)).toLocaleString("uz-UZ")} so'm`;
}

export function numeric(value: string) {
  return Number(value.replace(/[^0-9]/g, "")) || 0;
}

export function message(error: unknown) {
  return error instanceof Error ? error.message : "So'rov bajarilmadi.";
}

export function EducationShell({
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

export function ErrorBox({ value }: { value: string }) {
  return value ? (
    <p className="education-management-v1656__error" role="alert">
      {value}
    </p>
  ) : null;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="education-management-v1656__empty">{children}</div>;
}

export function GroupSelect({
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
    <select
      value={value || ""}
      onChange={(event) => onChange(Number(event.target.value) || 0)}
    >
      <option value="">{all ? "Barcha guruhlar" : "Guruhni tanlang"}</option>
      {groups.map((group) => (
        <option key={group.id} value={group.id}>
          {group.name}
        </option>
      ))}
    </select>
  );
}

export type PaymentTarget = {
  student_id: number;
  full_name: string;
  payment_month: string;
  debt: number;
};

export function PaymentModal({
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
      <section
        className="education-management-v1656__modal"
        role="dialog"
        aria-modal="true"
        aria-label="O'quvchi to'lovi"
      >
        <h2>{target.full_name}</h2>
        <p>Qoldi: {money(target.debt)}</p>
        <label>
          Oy
          <input type="month" readOnly value={target.payment_month} />
        </label>
        <label>
          To'lov summasi
          <input
            inputMode="numeric"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </label>
        <label>
          To'lov turi
          <select
            value={payType}
            onChange={(event) => setPayType(event.target.value as "naqd" | "karta")}
          >
            <option value="naqd">Naqd</option>
            <option value="karta">Karta</option>
          </select>
        </label>
        <label>
          Izoh
          <input
            maxLength={200}
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
        <div className="education-management-v1656__modal-actions">
          <button type="button" disabled={busy} onClick={onClose}>
            Bekor qilish
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onSave(numeric(amount), payType, note)}
          >
            To'lovni qabul qilish
          </button>
        </div>
      </section>
    </div>
  );
}

export function PaymentsView({
  api,
  onBack,
  canVoid,
}: {
  api: EducationManagementApi;
  onBack: () => void;
  canVoid: boolean;
}) {
  const [view, setView] = useState<"control" | "payments">("control");
  const [groups, setGroups] = useState<EducationGroup[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api
      .getEducationGroups()
      .then((value) => {
        if (active) setGroups(value);
      })
      .catch((reason) => {
        if (active) setError(message(reason));
      });
    return () => {
      active = false;
    };
  }, [api]);
  return (
    <EducationShell
      title="To'lov nazorati"
      caption="Muddati kelgan va yaqin to'lovlar"
      onBack={onBack}
    >
      <ErrorBox value={error} />
      <nav className="education-management-v1656__tabs">
        <button
          type="button"
          className={view === "control" ? "active" : ""}
          onClick={() => setView("control")}
        >
          To'lov nazorati
        </button>
        <button
          type="button"
          className={view === "payments" ? "active" : ""}
          onClick={() => setView("payments")}
        >
          To'lovlar va tarix
        </button>
      </nav>
      {view === "control" ? (
        <PaymentControlPane api={api} groups={groups} canVoid={canVoid} />
      ) : (
        <PaymentHistoryPane api={api} groups={groups} canVoid={canVoid} />
      )}
    </EducationShell>
  );
}

export const EMPTY_TEACHER: EducationTeacherWrite = {
  full_name: "",
  phone: "",
  specialty: "",
  hired_date: localDate(),
  salary_type: "monthly",
  salary_amount: 0,
  note: "",
};

export function PayrollModal({
  target,
  month,
  busy,
  onClose,
  onSave,
}: {
  target: EducationPayrollTeacher;
  month: string;
  busy: boolean;
  onClose: () => void;
  onSave: (amount: number, payType: "naqd" | "karta", note: string) => void;
}) {
  const [amount, setAmount] = useState(String(target.debt));
  const [payType, setPayType] = useState<"naqd" | "karta">("naqd");
  const [note, setNote] = useState("");
  return (
    <div className="education-management-v1656__modal-back">
      <section
        className="education-management-v1656__modal"
        role="dialog"
        aria-modal="true"
      >
        <h2>{target.full_name}</h2>
        <p>
          Hisoblandi: {money(target.expected)} · To'landi: {money(target.paid)} · Qoldi:{" "}
          {money(target.debt)}
        </p>
        <label>
          Oy
          <input type="month" readOnly value={month} />
        </label>
        <label>
          To'lov summasi
          <input
            inputMode="numeric"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </label>
        <label>
          To'lov turi
          <select
            value={payType}
            onChange={(event) => setPayType(event.target.value as "naqd" | "karta")}
          >
            <option value="naqd">Naqd</option>
            <option value="karta">Karta</option>
          </select>
        </label>
        <label>
          Izoh
          <input
            maxLength={200}
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
        <div className="education-management-v1656__modal-actions">
          <button type="button" disabled={busy} onClick={onClose}>
            Bekor qilish
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onSave(numeric(amount), payType, note)}
          >
            Maoshni to'lash
          </button>
        </div>
      </section>
    </div>
  );
}

export function EducationManagement({
  api,
  view,
  onBack,
  canVoidPayments = true,
}: {
  api: EducationManagementApi;
  view: EducationManagementView;
  onBack: () => void;
  canVoidPayments?: boolean;
}) {
  if (view === "education-groups") return <EducationGroups api={api} onBack={onBack} />;
  if (view === "education-students")
    return <EducationStudents api={api} onBack={onBack} />;
  if (view === "education-schedule") return <ScheduleView api={api} onBack={onBack} />;
  if (view === "education-attendance")
    return <AttendanceView api={api} onBack={onBack} />;
  if (view === "education-payments")
    return <PaymentsView api={api} onBack={onBack} canVoid={canVoidPayments} />;
  if (view === "education-teachers") return <TeachersView api={api} onBack={onBack} />;
  return <PayrollView api={api} onBack={onBack} />;
}
