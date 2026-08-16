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
  EMPTY_PAYMENTS,
  EducationManagementApi,
  Empty,
  ErrorBox,
  GroupSelect,
  PaymentModal,
  PaymentTarget,
  localMonth,
  message,
  money,
} from "./shared";

export function PaymentHistoryPane({
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
    setLoading(true);
    setError("");
    try {
      setData(await api.getEducationPayments(month, groupId));
    } catch (reason) {
      setError(message(reason));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void reload();
  }, [api, month, groupId]);

  async function pay(amount: number, payType: "naqd" | "karta", note: string) {
    if (!target || amount <= 0) {
      setError("To'lov summasini kiriting.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.createEducationPayment({
        student_id: target.student_id,
        payment_month: target.payment_month,
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

  async function voidPayment(paymentId: number) {
    const reason = window.prompt("To'lovni bekor qilish sababini kiriting:")?.trim();
    if (!reason) return;
    setBusy(true);
    setError("");
    try {
      await api.voidEducationPayment(paymentId, reason);
      await reload();
    } catch (problem) {
      setError(message(problem));
    } finally {
      setBusy(false);
    }
  }

  const totals = data.students.reduce(
    (result, student) => ({
      expected: result.expected + student.expected,
      paid: result.paid + student.paid,
      debt: result.debt + student.debt,
    }),
    { expected: 0, paid: 0, debt: 0 },
  );
  return (
    <>
      <ErrorBox value={error} />
      <section className="education-management-v1656__filters two">
        <input
          type="month"
          value={month}
          onChange={(event) => setMonth(event.target.value)}
        />
        <GroupSelect groups={groups} value={groupId} onChange={setGroupId} all />
      </section>
      <section className="education-management-v1656__totals three">
        <span>
          Hisoblandi<b>{money(totals.expected)}</b>
        </span>
        <span>
          To'landi<b className="positive">{money(totals.paid)}</b>
        </span>
        <span>
          Qarz<b className="negative">{money(totals.debt)}</b>
        </span>
      </section>
      {loading ? <Empty>Yuklanmoqda…</Empty> : null}
      <section className="education-management-v1656__cards">
        {data.students.map((student: EducationPaymentStudent) => {
          const open = expanded === student.student_id;
          const full = student.expected > 0 && student.debt === 0;
          const status = full
            ? "To'langan"
            : student.paid > 0
              ? "Qisman"
              : "To'lanmagan";
          return (
            <article key={student.student_id} className="collapsible">
              <button
                type="button"
                className="education-management-v1656__card-toggle"
                onClick={() => setExpanded(open ? 0 : student.student_id)}
              >
                <b>{student.full_name}</b>
                <span>›</span>
              </button>
              {open ? (
                <div className="education-management-v1656__details">
                  <p>
                    Guruh: {student.group_name || "Guruhsiz"}
                    <br />
                    Holat: {status}
                    <br />
                    Hisoblandi: {money(student.expected)}
                    <br />
                    To'landi: {money(student.paid)}
                    <br />
                    Qoldi: {money(student.debt)}
                    {student.billing_type === "attendance" ? (
                      <>
                        <br />
                        Darslar: {student.chargeable_lessons} ×{" "}
                        {money(student.per_lesson_price)}
                      </>
                    ) : null}
                  </p>
                  {student.debt ? (
                    <button
                      className="education-management-v1656__primary"
                      type="button"
                      onClick={() =>
                        setTarget({
                          student_id: student.student_id,
                          full_name: student.full_name,
                          payment_month: month,
                          debt: student.debt,
                        })
                      }
                    >
                      To'lov qabul qilish
                    </button>
                  ) : null}
                </div>
              ) : null}
            </article>
          );
        })}
      </section>
      <h2 className="education-management-v1656__section-title">To'lovlar tarixi</h2>
      <section className="education-management-v1656__history">
        {data.history.map((payment) => (
          <article key={payment.id} className={payment.voided_at ? "voided" : ""}>
            <div>
              <b>{payment.full_name}</b>
              <small>
                {money(payment.amount)} ·{" "}
                {payment.pay_type === "karta" ? "Karta" : "Naqd"}
                {payment.note ? ` · ${payment.note}` : ""}
                {payment.voided_at
                  ? ` · Bekor qilingan: ${payment.void_reason || "Sabab ko'rsatilmagan"}`
                  : ""}
              </small>
            </div>
            {canVoid && !payment.voided_at ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void voidPayment(payment.id)}
              >
                Bekor qilish
              </button>
            ) : null}
          </article>
        ))}
      </section>
      {!data.history.length ? (
        <p className="education-management-v1656__muted">Bu oy uchun to'lovlar yo'q.</p>
      ) : null}
      {target ? (
        <PaymentModal
          target={target}
          busy={busy}
          onClose={() => setTarget(null)}
          onSave={(amount, payType, note) => void pay(amount, payType, note)}
        />
      ) : null}
    </>
  );
}
