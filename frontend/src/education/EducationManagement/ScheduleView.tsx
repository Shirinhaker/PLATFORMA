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
  DAYS,
  EducationManagementApi,
  EducationShell,
  Empty,
  ErrorBox,
  GroupSelect,
  message,
} from "./shared";

export function ScheduleView({
  api,
  onBack,
}: {
  api: EducationManagementApi;
  onBack: () => void;
}) {
  const [groups, setGroups] = useState<EducationGroup[]>([]);
  const [groupId, setGroupId] = useState(0);
  const [teacher, setTeacher] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    api
      .getEducationGroups()
      .then((value) => {
        if (active) setGroups(value);
      })
      .catch((reason) => {
        if (active) setError(message(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);

  const teachers = useMemo(
    () =>
      Array.from(
        new Set(groups.map((group) => group.teacher_name.trim()).filter(Boolean)),
      ).sort((left, right) => left.localeCompare(right)),
    [groups],
  );
  const todayIndex = new Date().getDay();
  const today = todayIndex === 0 ? "sun" : (DAYS[todayIndex - 1]?.key ?? "mon");

  return (
    <EducationShell
      title="Dars jadvali"
      caption="Haftalik guruh va o'qituvchilar jadvali"
      onBack={onBack}
    >
      <ErrorBox value={error} />
      <section className="education-management-v1656__filters two">
        <GroupSelect groups={groups} value={groupId} onChange={setGroupId} all />
        <select value={teacher} onChange={(event) => setTeacher(event.target.value)}>
          <option value="">Barcha o'qituvchilar</option>
          {teachers.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </section>
      {loading ? (
        <Empty>Jadval yuklanmoqda…</Empty>
      ) : (
        DAYS.map((day) => {
          const lessons = groups
            .filter((group) => group.weekdays.split(",").includes(day.key))
            .filter((group) => !groupId || group.id === groupId)
            .filter((group) => !teacher || group.teacher_name === teacher)
            .sort((left, right) =>
              (left.lesson_from || "99:99").localeCompare(right.lesson_from || "99:99"),
            );
          return (
            <section className="education-management-v1656__day" key={day.key}>
              <header>
                <h2 className={day.key === today ? "today" : ""}>
                  {day.key === today ? "● " : ""}
                  {day.label}
                </h2>
                <small>{lessons.length} ta dars</small>
              </header>
              {lessons.length ? (
                lessons.map((group) => (
                  <article
                    className="education-management-v1656__lesson"
                    key={group.id}
                  >
                    <strong>
                      {group.lesson_from || "—"}
                      <small>{group.lesson_to || "—"} gacha</small>
                    </strong>
                    <div>
                      <b>{group.name}</b>
                      <small>📚 {group.course_name || "Kurs biriktirilmagan"}</small>
                      <small>
                        {group.teacher_name
                          ? `👤 ${group.teacher_name}`
                          : "O'qituvchi belgilanmagan"}
                        {group.room_name ? ` · 🚪 ${group.room_name}` : ""}
                      </small>
                    </div>
                  </article>
                ))
              ) : (
                <p className="education-management-v1656__muted">Dars belgilanmagan</p>
              )}
            </section>
          );
        })
      )}
    </EducationShell>
  );
}
