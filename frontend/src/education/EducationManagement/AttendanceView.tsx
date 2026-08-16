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
  ATTENDANCE_OPTIONS,
  EducationManagementApi,
  EducationShell,
  Empty,
  ErrorBox,
  GroupSelect,
  localDate,
  message,
} from "./shared";

export function AttendanceView({
  api,
  onBack,
}: {
  api: EducationManagementApi;
  onBack: () => void;
}) {
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

  async function load() {
    if (!groupId) {
      setError("Guruhni tanlang.");
      return;
    }
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
    setStudents((rows) =>
      rows.map((row) =>
        row.student_id === studentId ? { ...row, attendance_status: status } : row,
      ),
    );
  }

  async function save() {
    const missing = students.filter((student) => !student.attendance_status).length;
    if (missing) {
      setError(`${missing} nafar o'quvchining davomati belgilanmagan.`);
      return;
    }
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

  const counts = Object.fromEntries(
    ATTENDANCE_OPTIONS.map(({ status }) => [
      status,
      students.filter((student) => student.attendance_status === status).length,
    ]),
  );

  return (
    <EducationShell
      title="Davomat"
      caption="O'quvchilarning darsga qatnashuvi"
      onBack={onBack}
    >
      <section className="education-management-v1656__intro">
        <b>Davomatni belgilash</b>
        <p>Guruh va sanani tanlang. Avval saqlangan davomat avtomatik ochiladi.</p>
      </section>
      <ErrorBox value={error} />
      {notice ? <p className="education-management-v1656__success">{notice}</p> : null}
      <section className="education-management-v1656__filters two">
        <GroupSelect groups={groups} value={groupId} onChange={setGroupId} />
        <input
          type="date"
          value={lessonDate}
          onChange={(event) => setLessonDate(event.target.value)}
        />
      </section>
      <div className="education-management-v1656__actions two">
        <button type="button" disabled={busy} onClick={() => void load()}>
          Ko'rish
        </button>
        <button
          type="button"
          disabled={busy || !students.length}
          onClick={() =>
            setStudents((rows) =>
              rows.map((row) => ({ ...row, attendance_status: "present" })),
            )
          }
        >
          Barchasi keldi
        </button>
      </div>
      {students.length ? (
        <p className="education-management-v1656__summary-line">
          Jami: {students.length} · Keldi: {counts.present} · Kechikdi: {counts.late} ·
          Sababli: {counts.excused} · Sababsiz: {counts.absent}
        </p>
      ) : null}
      {loaded && !students.length ? (
        <Empty>
          <h3>O'quvchilar yo'q</h3>
          <p>Tanlangan guruhga avval o'quvchilarni biriktiring.</p>
        </Empty>
      ) : null}
      <section className="education-management-v1656__cards">
        {students.map((student) => (
          <article key={student.student_id}>
            <header>
              <div>
                <b>{student.full_name}</b>
                {student.phone ? <small>{student.phone}</small> : null}
              </div>
              <small>#{student.student_id}</small>
            </header>
            <div className="education-management-v1656__attendance-buttons">
              {ATTENDANCE_OPTIONS.map((option) => (
                <button
                  type="button"
                  key={option.status}
                  className={
                    student.attendance_status === option.status
                      ? `active ${option.status}`
                      : ""
                  }
                  onClick={() => mark(student.student_id, option.status)}
                >
                  {option.icon} {option.label}
                </button>
              ))}
            </div>
          </article>
        ))}
      </section>
      {students.length ? (
        <button
          className="education-management-v1656__primary"
          type="button"
          disabled={busy}
          onClick={() => void save()}
        >
          Davomatni saqlash
        </button>
      ) : null}
    </EducationShell>
  );
}
