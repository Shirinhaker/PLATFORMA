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
  EMPTY_CONTROL,
  EducationManagementApi,
  Empty,
  ErrorBox,
  GroupSelect,
  PaymentModal,
  PaymentTarget,
  message,
  money,
} from "./shared";

export function PaymentControlPane({
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
  const [filter, setFilter] = useState<
    "attention" | EducationPaymentControlStatus | "all"
  >("attention");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState(0);
  const [target, setTarget] = useState<PaymentTarget | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function reload(selected = groupId) {
    setLoading(true);
    setError("");
    try {
      setData(await api.getEducationPaymentControl(selected));
    } catch (reason) {
      setError(message(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload(groupId);
  }, [api, groupId]);

  const rows = data.students.filter((student) => {
    if (
      filter === "attention" &&
      !["overdue", "due_today", "upcoming"].includes(student.status)
    )
      return false;
    if (filter !== "attention" && filter !== "all" && student.status !== filter)
      return false;
    const query = search.trim().toLocaleLowerCase("uz");
    return (
      !query ||
      [student.full_name, student.phone, student.parent_phone, student.group_name]
        .join(" ")
        .toLocaleLowerCase("uz")
        .includes(query)
    );
  });

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

  void canVoid;
  return (
    <>
      <ErrorBox value={error} />
      <nav className="education-management-v1656__tabs compact">
        {(["attention", "overdue", "due_today", "upcoming", "all"] as const).map(
          (value) => (
            <button
              type="button"
              key={value}
              className={filter === value ? "active" : ""}
              onClick={() => setFilter(value)}
            >
              {
                {
                  attention: "E'tibor kerak",
                  overdue: "Muddati o'tgan",
                  due_today: "Bugun",
                  upcoming: "Yaqin",
                  all: "Barchasi",
                }[value]
              }
            </button>
          ),
        )}
      </nav>
      <section className="education-management-v1656__filters two">
        <input
          type="search"
          placeholder="Ism yoki telefon..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <GroupSelect groups={groups} value={groupId} onChange={setGroupId} all />
      </section>
      <section className="education-management-v1656__totals three">
        <span>
          Muddati o'tgan<b className="negative">{data.summary.overdue}</b>
        </span>
        <span>
          Bugun<b className="warning">{data.summary.due_today}</b>
        </span>
        <span>
          Jami qarz<b>{money(data.summary.total_debt)}</b>
        </span>
      </section>
      {loading ? <Empty>Yuklanmoqda…</Empty> : null}
      <section className="education-management-v1656__cards">
        {rows.map((student) => {
          const open = expanded === student.id;
          const statusLabel = {
            overdue: "Muddati o'tgan",
            due_today: "Bugun to'lanadi",
            upcoming: "Yaqinlashmoqda",
            paid: "To'langan",
          }[student.status];
          return (
            <article key={student.id} className="collapsible">
              <button
                type="button"
                className="education-management-v1656__card-toggle"
                aria-expanded={open}
                onClick={() => setExpanded(open ? 0 : student.id)}
              >
                <b>{student.full_name}</b>
                <span>›</span>
              </button>
              {open ? (
                <div className="education-management-v1656__details">
                  <p>
                    Holat: <em className={student.status}>{statusLabel}</em>
                    <br />
                    Guruh: {student.group_name || "Guruhsiz"}
                    <br />
                    To'lov turi:{" "}
                    {student.billing_type === "attendance" ? "Dars paketi" : "Oylik"}
                    <br />
                    {student.billing_type === "attendance"
                      ? `${student.lessons_done} dars hisoblandi · ${student.lessons_remaining} dars qoldi`
                      : `Keyingi muddat: ${student.next_due || "—"}`}
                    <br />
                    Qarz: {money(student.debt)}
                  </p>
                  {student.debt ? (
                    <button
                      className="education-management-v1656__primary"
                      type="button"
                      onClick={() =>
                        setTarget({
                          student_id: student.id,
                          full_name: student.full_name,
                          payment_month: student.payment_month,
                          debt: student.payable_now || student.debt,
                        })
                      }
                    >
                      To'lov olish
                    </button>
                  ) : null}
                </div>
              ) : null}
            </article>
          );
        })}
      </section>
      {!loading && !rows.length ? (
        <Empty>
          <h3>O'quvchi topilmadi</h3>
          <p>Tanlangan holatda to'lov mavjud emas.</p>
        </Empty>
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
