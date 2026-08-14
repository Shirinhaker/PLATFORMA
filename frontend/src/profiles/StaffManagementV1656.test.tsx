import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { StaffManagementV1656 } from "./StaffManagementV1656";


const member = {
  id: 11,
  name: "Ali Valiyev",
  profession: "Kassir",
  phone: "+998901234567",
  salary: 2_500_000,
  hire_date: "2026-08-01",
  status: "active" as const,
  note: "",
  login: "ali",
  can_login: true,
  has_password: true,
  permissions: ["kassa", "debts"],
  schedule: {},
  created_at: "2026-08-01T08:00:00Z",
  fired_at: null,
};


function api() {
  return {
    getStaffSetup: vi.fn().mockResolvedValue({
      active: [member],
      fired: [],
      active_count: 1,
      fired_count: 0,
      total_salary: 2_500_000,
      firm_login: "b_turon",
      business_direction: "Savdo",
      professions: ["Sotuvchi", "Kassir"],
      permission_definitions: [
        { key: "kassa", label: "Kassa", icon: "🧾" },
        { key: "debts", label: "Qarz daftari", icon: "📒" },
      ],
      permission_templates: [
        { key: "cashier", label: "Kassir", permissions: ["kassa", "debts"] },
      ],
    }),
    createStaffMember: vi.fn().mockResolvedValue(member),
    updateStaffMember: vi.fn().mockResolvedValue(member),
    fireStaffMember: vi.fn().mockResolvedValue({ ...member, status: "fired" }),
    rehireStaffMember: vi.fn().mockResolvedValue(member),
    deleteStaffMember: vi.fn().mockResolvedValue(undefined),
    updateStaffAccess: vi.fn().mockResolvedValue(member),
    updateStaffSchedule: vi.fn().mockResolvedValue(member),
    createStaffProfession: vi.fn().mockResolvedValue({ professions: ["Sotuvchi", "Kassir"] }),
    getStaffAttendance: vi.fn().mockResolvedValue({
      date: "2026-08-03",
      weekday: 0,
      staff: [],
    }),
    updateStaffAttendance: vi.fn(),
  };
}


it("replaces the read-only cabinet list with live staff management", async () => {
  const user = userEvent.setup();
  const client = api();
  render(<StaffManagementV1656 api={client} onBack={vi.fn()} />);

  expect(await screen.findByText("Ali Valiyev")).toBeInTheDocument();
  expect(screen.getByText("2 500 000 so‘m")).toBeInTheDocument();
  expect(screen.queryByText(/password/i)).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "+ Xodim qo‘shish" }));
  await user.type(screen.getByLabelText("F.I.Sh."), "Vali Karimov");
  await user.selectOptions(screen.getByLabelText("Lavozimi"), "Kassir");
  await user.click(screen.getByRole("button", { name: "Saqlash" }));

  expect(client.createStaffMember).toHaveBeenCalledWith(expect.objectContaining({
    name: "Vali Karimov",
    profession: "Kassir",
  }));
});


it("edits access without ever displaying the stored password", async () => {
  const user = userEvent.setup();
  const client = api();
  render(<StaffManagementV1656 api={client} onBack={vi.fn()} />);

  await user.click(await screen.findByRole("button", { name: /Ali Valiyev/ }));
  expect(screen.getByText("Parol o‘rnatilgan")).toBeInTheDocument();
  expect(screen.getByLabelText("Yangi parol (ixtiyoriy)")).toHaveValue("");
  await user.click(screen.getByRole("button", { name: "Kirish va vakolatni saqlash" }));

  expect(client.updateStaffAccess).toHaveBeenCalledWith(11, {
    can_login: true,
    login: "ali",
    password: "",
    permissions: ["kassa", "debts"],
  });
});
