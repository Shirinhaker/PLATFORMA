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
  EMPTY_PAYROLL,
  EducationManagementApi,
  EducationShell,
  Empty,
  ErrorBox,
  PayrollModal,
  localMonth,
  message,
  money,
} from "./shared";

export function PayrollView({
  api,
  onBack,
}: {
  api: EducationManagementApi;
  onBack: () => void;
}) {
  const [month, setMonth] = useState(localMonth);
  const [data, setData] = useState(EMPTY_PAYROLL);
  const [target, setTarget] = useState<EducationPayrollTeacher | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function reload() {
    setLoading(true);
    setError("");
    try {
      setData(await api.getEducationPayroll(month));
    } catch (reason) {
      setError(message(reason));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void reload();
  }, [api, month]);
  async function pay(amount: number, payType: "naqd" | "karta", note: string) {
    if (!target || amount <= 0) {
      setError("To'lov summasini kiriting.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.createEducationPayroll({
        teacher_id: target.id,
        payment_month: month,
        amount,
        pay_type: payType,
        note,
      });
      setTarget(null);
      await reload();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }
  async function remove(paymentId: number) {
    if (!window.confirm("Maosh to'lovi va unga bog'langan xarajat o'chirilsinmi?"))
      return;
    setBusy(true);
    setError("");
    try {
      await api.deleteEducationPayroll(paymentId);
      await reload();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }
  const totals = data.teachers.reduce(
    (result, teacher) => ({
      expected: result.expected + teacher.expected,
      paid: result.paid + teacher.paid,
      debt: result.debt + teacher.debt,
    }),
    { expected: 0, paid: 0, debt: 0 },
  );
  return (
    <EducationShell
      title="O'qituvchi maoshi"
      caption="Oy bo'yicha hisoblangan va to'langan maoshlar"
      onBack={onBack}
    >
      <ErrorBox value={error} />
      <input
        className="education-management-v1656__month"
        type="month"
        value={month}
        onChange={(event) => setMonth(event.target.value)}
      />
      <section className="education-management-v1656__totals three">
        <span>
          Hisoblandi<b>{money(totals.expected)}</b>
        </span>
        <span>
          To'landi<b className="positive">{money(totals.paid)}</b>
        </span>
        <span>
          Qoldi<b className="negative">{money(totals.debt)}</b>
        </span>
      </section>
      {loading ? <Empty>Yuklanmoqda…</Empty> : null}
      <section className="education-management-v1656__cards">
        {data.teachers.map((teacher) => (
          <article key={teacher.id}>
            <header>
              <div>
                <b>{teacher.full_name}</b>
                <small>
                  {teacher.salary_type === "per_lesson"
                    ? `${teacher.lesson_count} dars × ${money(teacher.salary_amount)}`
                    : `Oylik ${money(teacher.salary_amount)}`}
                </small>
              </div>
              <em>
                {teacher.debt > 0
                  ? `Qoldi ${money(teacher.debt)}`
                  : teacher.expected
                    ? "To'langan"
                    : "Hisob yo'q"}
              </em>
            </header>
            <p>
              Hisoblandi: {money(teacher.expected)} · To'landi: {money(teacher.paid)}
            </p>
            {teacher.debt > 0 ? (
              <button
                className="education-management-v1656__primary"
                type="button"
                onClick={() => setTarget(teacher)}
              >
                Maosh to'lash
              </button>
            ) : null}
          </article>
        ))}
      </section>
      {!loading && !data.teachers.length ? (
        <Empty>
          <h3>O'qituvchilar yo'q</h3>
        </Empty>
      ) : null}
      <h2 className="education-management-v1656__section-title">
        Maosh to'lovlari tarixi
      </h2>
      <section className="education-management-v1656__history">
        {data.history.map((payment) => (
          <article key={payment.id}>
            <div>
              <b>{payment.full_name}</b>
              <small>
                {money(payment.amount)} ·{" "}
                {payment.pay_type === "karta" ? "Karta" : "Naqd"}
                {payment.note ? ` · ${payment.note}` : ""}
              </small>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => void remove(payment.id)}
            >
              O'chirish
            </button>
          </article>
        ))}
      </section>
      {!data.history.length ? (
        <p className="education-management-v1656__muted">Bu oyda maosh to'lovi yo'q.</p>
      ) : null}
      {target ? (
        <PayrollModal
          target={target}
          month={month}
          busy={busy}
          onClose={() => setTarget(null)}
          onSave={(amount, payType, note) => void pay(amount, payType, note)}
        />
      ) : null}
    </EducationShell>
  );
}
