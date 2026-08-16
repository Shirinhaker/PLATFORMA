// `api/types.ts` dan ajratildi — domen bo'yicha.

export type StaffScheduleDay = {
  on: boolean;
  start: string;
  end: string;
};

export type StaffSchedule = Record<string, StaffScheduleDay>;

export type StaffMember = {
  id: number;
  name: string;
  profession: string;
  phone: string;
  salary: number;
  hire_date: string | null;
  status: "active" | "fired";
  note: string;
  login: string;
  can_login: boolean;
  has_password: boolean;
  permissions: string[];
  schedule: StaffSchedule;
  created_at: string;
  fired_at: string | null;
};

export type StaffMemberWrite = {
  name: string;
  profession: string;
  phone: string;
  salary: number;
  hire_date: string | null;
  note: string;
};

export type StaffPermission = { key: string; label: string; icon: string };

export type StaffPermissionTemplate = {
  key: string;
  label: string;
  permissions: string[];
};

export type StaffSetup = {
  active: StaffMember[];
  fired: StaffMember[];
  active_count: number;
  fired_count: number;
  total_salary: number;
  firm_login: string;
  business_direction: string;
  professions: string[];
  permission_definitions: StaffPermission[];
  permission_templates: StaffPermissionTemplate[];
};

export type StaffAccessWrite = {
  can_login: boolean;
  login: string;
  password: string;
  permissions: string[];
};

export type StaffAttendanceRow = {
  id: number;
  name: string;
  profession: string;
  status: string;
  time_in: string;
  time_out: string;
  sched_on: boolean;
  sched_start: string;
  sched_end: string;
  month_present: number;
  month_minutes: number;
};

export type StaffAttendance = {
  date: string;
  weekday: number;
  staff: StaffAttendanceRow[];
};
