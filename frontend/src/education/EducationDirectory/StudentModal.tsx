import type {
  EducationGroup,
  EducationStudent,
  EducationStudentWrite,
} from "../../api/types";

import { Modal, numeric } from "./shared";

export function StudentModal({
  editing,
  form,
  fee,
  groups,
  busy,
  setForm,
  setFee,
  onClose,
  onSave,
  onRemove,
}: {
  editing: EducationStudent | null;
  form: EducationStudentWrite;
  fee: string;
  groups: EducationGroup[];
  busy: boolean;
  setForm: (value: EducationStudentWrite) => void;
  setFee: (value: string) => void;
  onClose: () => void;
  onSave: () => void;
  onRemove: () => void;
}) {
  return (
    <Modal
      title={editing ? "O'quvchini tahrirlash" : "Yangi o'quvchi"}
      actions={
        <>
          {editing ? (
            <button className="danger" disabled={busy} type="button" onClick={onRemove}>
              Ro'yxatdan chiqarish
            </button>
          ) : null}
          <button disabled={busy} type="button" onClick={onClose}>
            Bekor qilish
          </button>
          <button disabled={busy} type="button" onClick={onSave}>
            Saqlash
          </button>
        </>
      }
    >
      <label>
        Ism-familiya
        <input
          maxLength={120}
          value={form.full_name}
          onChange={(event) => setForm({ ...form, full_name: event.target.value })}
        />
      </label>
      <label>
        Guruh
        <select
          disabled={Boolean(editing)}
          value={form.group_id || ""}
          onChange={(event) =>
            setForm({ ...form, group_id: Number(event.target.value) || null })
          }
        >
          <option value="">Guruhni tanlang</option>
          {groups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </select>
      </label>
      {editing ? (
        <p>
          Guruhni almashtirish uchun o'quvchi kartasidagi “Guruhga ko'chirish”
          tugmasidan foydalaning.
        </p>
      ) : null}
      <div className="education-management-v1656__filters two">
        <label>
          Telefon
          <input
            maxLength={40}
            value={form.phone}
            onChange={(event) => setForm({ ...form, phone: event.target.value })}
          />
        </label>
        <label>
          Ota-ona
          <input
            maxLength={160}
            value={form.parent_name}
            onChange={(event) => setForm({ ...form, parent_name: event.target.value })}
          />
        </label>
      </div>
      <label>
        Ota-ona telefoni
        <input
          maxLength={40}
          value={form.parent_phone}
          onChange={(event) => setForm({ ...form, parent_phone: event.target.value })}
        />
      </label>
      <div className="education-management-v1656__filters two">
        <label>
          Tug'ilgan sana
          <input
            type="date"
            value={form.birth_date}
            onChange={(event) => setForm({ ...form, birth_date: event.target.value })}
          />
        </label>
        <label>
          Qabul sanasi
          <input
            type="date"
            value={form.joined_date}
            onChange={(event) => setForm({ ...form, joined_date: event.target.value })}
          />
        </label>
      </div>
      <label>
        Oylik to'lov
        <input
          inputMode="numeric"
          value={fee}
          onChange={(event) => setFee(event.target.value)}
        />
      </label>
      <div className="education-management-v1656__filters two">
        <label>
          To'lov boshlanishi
          <input
            type="date"
            value={form.payment_start_date}
            onChange={(event) =>
              setForm({ ...form, payment_start_date: event.target.value })
            }
          />
        </label>
        <label>
          Shaxsiy dars paketi
          <input
            inputMode="numeric"
            value={form.lesson_package_override || ""}
            onChange={(event) =>
              setForm({ ...form, lesson_package_override: numeric(event.target.value) })
            }
          />
        </label>
      </div>
      <label>
        Izoh
        <textarea
          maxLength={2000}
          value={form.note}
          onChange={(event) => setForm({ ...form, note: event.target.value })}
        />
      </label>
    </Modal>
  );
}
