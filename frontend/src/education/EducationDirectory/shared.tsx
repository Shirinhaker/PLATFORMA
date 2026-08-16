import type { ReactNode } from "react";

import type { ApiClient } from "../../api/client";
import type { EducationGroupWrite, EducationStudentWrite } from "../../api/types";

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

export const DAYS = [
  ["mon", "Du"],
  ["tue", "Se"],
  ["wed", "Chor"],
  ["thu", "Pay"],
  ["fri", "Ju"],
  ["sat", "Sha"],
  ["sun", "Yak"],
] as const;

export const EMPTY_GROUP: EducationGroupWrite = {
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

export const EMPTY_STUDENT: EducationStudentWrite = {
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

export function localDate() {
  const value = new Date();
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
  return value.toISOString().slice(0, 10);
}

export function money(value: number) {
  return `${Math.trunc(Number(value || 0)).toLocaleString("uz-UZ")} so'm`;
}

export function numeric(value: string) {
  return Number(value.replace(/[^0-9]/g, "")) || 0;
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So'rov bajarilmadi.";
}

export function Shell({
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

export function Modal({
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
