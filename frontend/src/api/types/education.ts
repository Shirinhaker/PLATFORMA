// `api/types.ts` dan ajratildi — domen bo'yicha.

export type EducationStatisticsPeriod = "day" | "month" | "year";

export type EducationStatisticsFinance = {
  calculated: number;
  paid: number;
  debt: number;
};

export type EducationStatisticsReport = {
  period: {
    type: EducationStatisticsPeriod;
    date: string;
    start: string;
    end: string;
  };
  education: {
    active_students: number;
    active_groups: number;
    new_enrollments: number;
    attendance_percent: number;
  };
  student_finance: EducationStatisticsFinance;
  teacher_finance: EducationStatisticsFinance;
  result: {
    other_expenses: number;
    cash_flow: number;
    accrual_result: number;
  };
  groups: Array<{
    id: number;
    name: string;
    active_students: number;
    attendance_percent: number;
    calculated: number;
    paid: number;
    debt: number;
  }>;
};

export type EducationGroup = {
  id: number;
  course_item_id: number | null;
  course_name: string;
  name: string;
  teacher_id: number | null;
  teacher_name: string;
  room_name: string;
  capacity: number;
  weekdays: string;
  lesson_from: string;
  lesson_to: string;
  start_date: string;
  end_date: string;
  billing_type: "monthly" | "attendance";
  package_lessons: number;
  package_price: number;
  student_count: number;
};

export type EducationGroupWrite = Omit<
  EducationGroup,
  "id" | "course_name" | "student_count" | "weekdays"
> & { weekdays: string[] };

export type EducationStudentWrite = {
  full_name: string;
  group_id: number | null;
  phone: string;
  parent_name: string;
  parent_phone: string;
  birth_date: string;
  joined_date: string;
  monthly_fee: number;
  payment_start_date: string;
  lesson_package_override: number;
  note: string;
};

export type EducationStudent = EducationStudentWrite & {
  id: number;
  group_name: string;
  course_name: string;
};

export type EducationStudentCard = {
  student: EducationStudent;
  attendance: {
    total: number;
    attended: number;
    percent: number;
    counts: Record<EducationAttendanceStatus, number>;
  };
  payment: {
    expected: number;
    paid: number;
    debt: number;
    total_paid: number;
  };
  payments: Array<{
    id: number;
    payment_month: string;
    amount: number;
    pay_type: "naqd" | "karta";
    note: string;
    voided_at: string | null;
    void_reason: string;
    created_at: string;
  }>;
  group_history: Array<{
    id: number;
    group_id: number;
    group_name: string;
    started_date: string;
    ended_date: string;
    note: string;
  }>;
};

export type EducationAttendanceStatus = "present" | "late" | "excused" | "absent";

export type EducationAttendanceStudent = {
  student_id: number;
  full_name: string;
  phone: string;
  attendance_status: EducationAttendanceStatus | "";
  attendance_note: string;
};

export type EducationAttendance = {
  group: EducationGroup;
  lesson_date: string;
  students: EducationAttendanceStudent[];
};

export type EducationAttendanceWrite = {
  group_id: number;
  lesson_date: string;
  entries: Array<{
    student_id: number;
    status: EducationAttendanceStatus | "";
    note: string;
  }>;
};

export type EducationPaymentControlStatus =
  "overdue" | "due_today" | "upcoming" | "paid";

export type EducationPaymentControlStudent = {
  id: number;
  group_id: number | null;
  full_name: string;
  phone: string;
  parent_phone: string;
  group_name: string;
  billing_type: "monthly" | "attendance";
  status: EducationPaymentControlStatus;
  start_date: string;
  next_due: string;
  expected: number;
  paid: number;
  debt: number;
  package_lessons: number;
  lessons_done: number;
  lessons_remaining: number;
  payable_now: number;
  payment_month: string;
};

export type EducationPaymentControl = {
  today: string;
  summary: {
    overdue: number;
    due_today: number;
    upcoming: number;
    paid: number;
    total_debt: number;
  };
  students: EducationPaymentControlStudent[];
};

export type EducationPaymentStudent = {
  student_id: number;
  full_name: string;
  phone: string;
  monthly_fee: number;
  group_name: string;
  billing_type: "monthly" | "attendance";
  package_lessons: number;
  package_price: number;
  chargeable_lessons: number;
  per_lesson_price: number;
  expected: number;
  paid: number;
  debt: number;
};

export type EducationPaymentHistory = {
  id: number;
  student_id: number | null;
  full_name: string;
  payment_month: string;
  amount: number;
  pay_type: "naqd" | "karta";
  note: string;
  voided_at: string | null;
  void_reason: string;
  created_at: string;
};

export type EducationPaymentMonth = {
  payment_month: string;
  students: EducationPaymentStudent[];
  history: EducationPaymentHistory[];
};

export type EducationPaymentCreate = {
  student_id: number;
  payment_month: string;
  amount: number;
  pay_type: "naqd" | "karta";
  note: string;
};

export type EducationTeacherWrite = {
  full_name: string;
  phone: string;
  specialty: string;
  hired_date: string;
  salary_type: "monthly" | "per_lesson";
  salary_amount: number;
  note: string;
};

export type EducationTeacher = EducationTeacherWrite & {
  id: number;
  group_count: number;
};

export type EducationPayrollTeacher = {
  id: number;
  full_name: string;
  salary_type: "monthly" | "per_lesson";
  salary_amount: number;
  lesson_count: number;
  expected: number;
  paid: number;
  debt: number;
};

export type EducationPayroll = {
  payment_month: string;
  teachers: EducationPayrollTeacher[];
  history: Array<{
    id: number;
    teacher_id: number | null;
    full_name: string;
    payment_month: string;
    amount: number;
    pay_type: "naqd" | "karta";
    note: string;
    created_at: string;
  }>;
};

export type EducationPayrollCreate = {
  teacher_id: number;
  payment_month: string;
  amount: number;
  pay_type: "naqd" | "karta";
  note: string;
};
