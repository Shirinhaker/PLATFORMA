import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  EducationManagement,
  type EducationManagementApi,
  type EducationManagementView,
} from "./EducationManagement";

const group = {
  id: 1,
  course_item_id: 51,
  course_name: "Ingliz tili",
  name: "Starter",
  teacher_id: 2,
  teacher_name: "Aziza Ustoz",
  room_name: "A1",
  capacity: 12,
  weekdays: "mon,wed,fri",
  lesson_from: "09:00",
  lesson_to: "10:00",
  start_date: "2026-08-01",
  end_date: "",
  billing_type: "monthly" as const,
  package_lessons: 0,
  package_price: 0,
  student_count: 1,
};

function api(): EducationManagementApi {
  return {
    getBusinessOnlineResource: vi
      .fn()
      .mockResolvedValue({ resource: "items", items: [] }),
    getEducationGroups: vi.fn().mockResolvedValue([group]),
    createEducationGroup: vi.fn().mockResolvedValue({ ok: true, id: 2 }),
    updateEducationGroup: vi.fn().mockResolvedValue({ ok: true }),
    deleteEducationGroup: vi.fn().mockResolvedValue(undefined),
    getEducationStudents: vi.fn().mockResolvedValue([]),
    createEducationStudent: vi.fn().mockResolvedValue({ ok: true, id: 2 }),
    updateEducationStudent: vi.fn().mockResolvedValue({ ok: true }),
    deleteEducationStudent: vi.fn().mockResolvedValue(undefined),
    getEducationStudentCard: vi.fn(),
    transferEducationStudent: vi
      .fn()
      .mockResolvedValue({ ok: true, group_id: 1, group_name: "Starter" }),
    getEducationAttendance: vi.fn().mockResolvedValue({
      group,
      lesson_date: "2026-08-10",
      students: [
        {
          student_id: 9,
          full_name: "Ali Valiyev",
          phone: "+99890",
          attendance_status: "",
          attendance_note: "",
        },
      ],
    }),
    saveEducationAttendance: vi.fn().mockResolvedValue({ ok: true, saved: 1 }),
    getEducationPaymentControl: vi.fn().mockResolvedValue({
      today: "2026-08-10",
      summary: { overdue: 1, due_today: 0, upcoming: 0, paid: 0, total_debt: 500 },
      students: [
        {
          id: 9,
          group_id: 1,
          full_name: "Ali Valiyev",
          phone: "",
          parent_phone: "",
          group_name: "Starter",
          billing_type: "monthly",
          status: "overdue",
          start_date: "2026-07-10",
          next_due: "2026-08-10",
          expected: 500,
          paid: 0,
          debt: 500,
          package_lessons: 0,
          lessons_done: 0,
          lessons_remaining: 0,
          payable_now: 500,
          payment_month: "2026-08",
        },
      ],
    }),
    getEducationPayments: vi
      .fn()
      .mockResolvedValue({ payment_month: "2026-08", students: [], history: [] }),
    createEducationPayment: vi
      .fn()
      .mockResolvedValue({ ok: true, id: 1, receipt_no: 1 }),
    voidEducationPayment: vi.fn().mockResolvedValue({ ok: true, voided: true }),
    getEducationTeachers: vi.fn().mockResolvedValue([]),
    createEducationTeacher: vi.fn().mockResolvedValue({ ok: true, id: 1 }),
    updateEducationTeacher: vi.fn().mockResolvedValue({ ok: true }),
    deleteEducationTeacher: vi.fn().mockResolvedValue(undefined),
    getEducationPayroll: vi.fn().mockResolvedValue({
      payment_month: "2026-08",
      teachers: [
        {
          id: 2,
          full_name: "Aziza Ustoz",
          salary_type: "monthly",
          salary_amount: 1_000,
          lesson_count: 0,
          expected: 1_000,
          paid: 0,
          debt: 1_000,
        },
      ],
      history: [],
    }),
    createEducationPayroll: vi.fn().mockResolvedValue({ ok: true, id: 1 }),
    deleteEducationPayroll: vi.fn().mockResolvedValue(undefined),
  };
}

function open(view: EducationManagementView, client = api()) {
  render(<EducationManagement api={client} view={view} onBack={vi.fn()} />);
  return client;
}

describe("EducationManagement", () => {
  it("guruhni typed modul orqali tahrirlaydi", async () => {
    const user = userEvent.setup();
    const client = open("education-groups");
    await screen.findByText(/Ingliz tili/);
    await user.click(screen.getByRole("button", { name: "Tahrirlash" }));
    const name = screen.getByLabelText("Guruh nomi");
    await user.clear(name);
    await user.type(name, "Starter Plus");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    await waitFor(() =>
      expect(client.updateEducationGroup).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          name: "Starter Plus",
          weekdays: ["mon", "wed", "fri"],
        }),
      ),
    );
  });

  it("o'quvchi kartasini ochib, guruh ko'chirishini saqlaydi", async () => {
    const user = userEvent.setup();
    const client = api();
    const second = { ...group, id: 2, name: "Intermediate", student_count: 0 };
    const student = {
      id: 9,
      full_name: "Ali Valiyev",
      group_id: 1,
      group_name: "Starter",
      course_name: "Ingliz tili",
      phone: "+99890",
      parent_name: "Vali",
      parent_phone: "+99891",
      birth_date: "",
      joined_date: "2026-08-01",
      monthly_fee: 500_000,
      payment_start_date: "2026-08-01",
      lesson_package_override: 0,
      note: "",
    };
    vi.mocked(client.getEducationGroups).mockResolvedValue([group, second]);
    vi.mocked(client.getEducationStudents).mockResolvedValue([student]);
    vi.mocked(client.getEducationStudentCard).mockResolvedValue({
      student,
      attendance: {
        total: 4,
        attended: 3,
        percent: 75,
        counts: { present: 2, late: 1, excused: 0, absent: 1 },
      },
      payment: { expected: 500_000, paid: 200_000, debt: 300_000, total_paid: 200_000 },
      payments: [],
      group_history: [
        {
          id: 1,
          group_id: 1,
          group_name: "Starter",
          started_date: "2026-08-01",
          ended_date: "",
          note: "Boshlang'ich guruh",
        },
      ],
    });
    open("education-students", client);
    await user.click(
      await screen.findByRole("button", { name: "To'liq kartani ochish" }),
    );
    expect(await screen.findByText("75%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Guruhga ko'chirish" }));
    await user.selectOptions(screen.getByLabelText("Yangi guruh"), "2");
    await user.click(screen.getByRole("button", { name: "Ko'chirish" }));
    await waitFor(() =>
      expect(client.transferEducationStudent).toHaveBeenCalledWith(
        9,
        expect.objectContaining({ group_id: 2 }),
      ),
    );
  });

  it("guruh ma'lumotidan haftalik dars jadvalini tuzadi", async () => {
    const client = open("education-schedule");
    await screen.findAllByText("Starter");
    expect(
      document.querySelectorAll(".education-management-v1656__lesson"),
    ).toHaveLength(3);
    expect(screen.getAllByText(/Aziza Ustoz/)).toHaveLength(4);
    expect(client.getEducationGroups).toHaveBeenCalledOnce();
  });

  it("davomatni yuklab, barcha o'quvchini keldi deb saqlaydi", async () => {
    const user = userEvent.setup();
    const client = open("education-attendance");
    await user.selectOptions(await screen.findByRole("combobox"), "1");
    await user.click(screen.getByRole("button", { name: "Ko'rish" }));
    expect(await screen.findByText("Ali Valiyev")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Barchasi keldi" }));
    await user.click(screen.getByRole("button", { name: "Davomatni saqlash" }));
    await waitFor(() =>
      expect(client.saveEducationAttendance).toHaveBeenCalledWith(
        expect.objectContaining({
          group_id: 1,
          entries: [{ student_id: 9, status: "present", note: "" }],
        }),
      ),
    );
  });

  it("qarzdor o'quvchi to'lovini Kassa zanjiriga yuboradi", async () => {
    const user = userEvent.setup();
    const client = open("education-payments");
    await user.click(await screen.findByRole("button", { name: /Ali Valiyev/ }));
    await user.click(screen.getByRole("button", { name: "To'lov olish" }));
    await user.click(screen.getByRole("button", { name: "To'lovni qabul qilish" }));
    await waitFor(() =>
      expect(client.createEducationPayment).toHaveBeenCalledWith({
        student_id: 9,
        payment_month: "2026-08",
        amount: 500,
        pay_type: "naqd",
        note: "",
      }),
    );
  });

  it("o'qituvchi maoshini Xarajatlar bilan bog'langan APIga yuboradi", async () => {
    const user = userEvent.setup();
    const client = open("education-payroll");
    await user.click(await screen.findByRole("button", { name: "Maosh to'lash" }));
    await user.click(screen.getByRole("button", { name: "Maoshni to'lash" }));
    await waitFor(() =>
      expect(client.createEducationPayroll).toHaveBeenCalledWith(
        expect.objectContaining({
          teacher_id: 2,
          amount: 1_000,
          pay_type: "naqd",
        }),
      ),
    );
  });
});
