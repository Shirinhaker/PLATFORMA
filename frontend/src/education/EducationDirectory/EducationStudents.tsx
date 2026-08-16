import { useEffect, useMemo, useState } from "react";

import type {
  EducationGroup,
  EducationStudent,
  EducationStudentCard,
  EducationStudentWrite,
} from "../../api/types";

import { StudentModal } from "./StudentModal";
import {
  EMPTY_STUDENT,
  ErrorBox,
  Modal,
  Shell,
  errorMessage,
  localDate,
  money,
  numeric,
  type EducationDirectoryApi,
} from "./shared";

export function EducationStudents({
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
