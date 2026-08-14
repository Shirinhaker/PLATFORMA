import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CourseEnrollmentV1656 } from "./CourseEnrollmentV1656";


const target = {
  itemPublicId: "s_english",
  courseName: "Ingliz tili",
};


describe("v1656 kursga yozilish pariteti", () => {
  it("telefon va ixtiyoriy izohni yuborib, monolitdagi xabarni beradi", async () => {
    const user = userEvent.setup();
    const api = {
      createCourseEnrollment: vi.fn().mockResolvedValue({ ok: true, id: 91 }),
    };
    const onClose = vi.fn();
    const onMessage = vi.fn();

    render(
      <CourseEnrollmentV1656
        api={api}
        customerPhone="+998901234567"
        target={target}
        onClose={onClose}
        onMessage={onMessage}
      />,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Ingliz tili kursiga yozilish"))
      .toHaveClass("acf-title");
    expect(screen.getByLabelText("Telefon raqamingiz"))
      .toHaveValue("+998901234567");
    await user.type(
      screen.getByLabelText("Izoh"),
      "Kechki guruh qulay",
    );
    await user.click(screen.getByRole("button", { name: "Ariza yuborish" }));

    expect(api.createCourseEnrollment).toHaveBeenCalledWith({
      course_item_public_id: "s_english",
      phone: "+998901234567",
      note: "Kechki guruh qulay",
    });
    expect(onMessage).toHaveBeenCalledWith("Arizangiz yuborildi ✅");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("bo'sh telefonni serverga yubormaydi", async () => {
    const user = userEvent.setup();
    const api = { createCourseEnrollment: vi.fn() };
    const onMessage = vi.fn();

    render(
      <CourseEnrollmentV1656
        api={api}
        customerPhone=""
        target={target}
        onClose={vi.fn()}
        onMessage={onMessage}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Ariza yuborish" }));
    expect(api.createCourseEnrollment).not.toHaveBeenCalled();
    expect(onMessage).toHaveBeenCalledWith("Telefon raqamini kiriting.");
  });

  it("server xabarini ko'rsatib, formadagi ma'lumotni saqlab qoladi", async () => {
    const user = userEvent.setup();
    const api = {
      createCourseEnrollment: vi.fn().mockRejectedValue(
        new Error("Siz bu kursga avval yozilgansiz."),
      ),
    };
    const onClose = vi.fn();
    const onMessage = vi.fn();

    render(
      <CourseEnrollmentV1656
        api={api}
        customerPhone="+998901234567"
        target={target}
        onClose={onClose}
        onMessage={onMessage}
      />,
    );
    await user.type(screen.getByLabelText("Izoh"), "Ertalab");
    await user.click(screen.getByRole("button", { name: "Ariza yuborish" }));

    expect(onMessage).toHaveBeenCalledWith(
      "Siz bu kursga avval yozilgansiz.",
    );
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Izoh")).toHaveValue("Ertalab");
  });
});
