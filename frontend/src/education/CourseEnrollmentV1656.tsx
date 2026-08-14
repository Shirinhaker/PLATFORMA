import { type FormEvent, useState } from "react";

import type { ApiClient } from "../api/client";
import "./CourseEnrollmentV1656.css";


export type CourseEnrollmentTarget = {
  itemPublicId: string;
  courseName: string;
};

export type CourseEnrollmentApi = Pick<ApiClient, "createCourseEnrollment">;

type Props = {
  api: CourseEnrollmentApi;
  customerPhone: string;
  target: CourseEnrollmentTarget;
  onClose(): void;
  onMessage(message: string): void;
};


function errorText(reason: unknown) {
  return reason instanceof Error
    ? reason.message
    : "Arizani yuborib bo'lmadi. Qayta urinib ko'ring.";
}


export function CourseEnrollmentV1656({
  api,
  customerPhone,
  target,
  onClose,
  onMessage,
}: Props) {
  const [phone, setPhone] = useState(customerPhone);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanPhone = phone.trim();
    if (!cleanPhone) {
      onMessage("Telefon raqamini kiriting.");
      return;
    }
    setBusy(true);
    try {
      await api.createCourseEnrollment({
        course_item_public_id: target.itemPublicId,
        phone: cleanPhone,
        note: note.trim(),
      });
      onMessage("Arizangiz yuborildi ✅");
      onClose();
    } catch (reason) {
      onMessage(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="course-enrollment-v1656">
      <div className="app-modal-back on" onClick={onClose} />
      <form
        className="app-confirm on"
        role="dialog"
        aria-modal="true"
        onSubmit={(event) => void submit(event)}
      >
        <div className="acf-title">{target.courseName} kursiga yozilish</div>
        <label htmlFor="course-enrollment-phone">Telefon raqamingiz</label>
        <input
          autoFocus
          id="course-enrollment-phone"
          maxLength={30}
          type="tel"
          value={phone}
          onChange={(event) => setPhone(event.currentTarget.value)}
        />
        <label htmlFor="course-enrollment-note">Izoh</label>
        <textarea
          id="course-enrollment-note"
          maxLength={300}
          placeholder="Qulay vaqt yoki savolingiz — ixtiyoriy"
          value={note}
          onChange={(event) => setNote(event.currentTarget.value)}
        />
        <div className="acf-btns">
          <button type="button" onClick={onClose}>Bekor qilish</button>
          <button className="acf-ok" disabled={busy} type="submit">
            {busy ? "Yuborilmoqda..." : "Ariza yuborish"}
          </button>
        </div>
      </form>
    </div>
  );
}
