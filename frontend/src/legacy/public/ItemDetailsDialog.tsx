import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { PublicProfileItem } from "../../api/types";
import "./ItemDetailsDialog.css";

type Props = {
  item?: Omit<PublicProfileItem, "public_id" | "group_name">;
  education?: boolean;
  children?: ReactNode;
  onClose(): void;
};

export function ItemDetailsDialog({
  item,
  education = false,
  children,
  onClose,
}: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const element = dialog.current;
    const previousFocus = document.activeElement;
    const overflow = document.body.style.overflow;
    element?.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      element?.close();
      document.body.style.overflow = overflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) {
        previousFocus.focus({ preventScroll: true });
      }
    };
  }, []);
  const course = item;
  return createPortal(
    <dialog
      ref={dialog}
      className="item-details-dialog"
      aria-labelledby={titleId}
      aria-modal="true"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="item-details-panel">
        <header className="item-details-header">
          <div>
            <span>
              {item ? (item.kind === "service" ? "Xizmat" : "Mahsulot") : "Ma’lumot"}
            </span>
            <h2 id={titleId}>{item?.name || "Mahsulot va xizmat haqida"}</h2>
          </div>
          <button type="button" aria-label="Ma’lumot oynasini yopish" onClick={onClose}>
            ×
          </button>
        </header>
        {item ? (
          <>
            <img
              className="item-details-image"
              src={item.image_url || "/assets/catalog-placeholder.svg"}
              alt={item.name}
            />
            <div className="item-details-content">
              <p className="item-details-price">
                {item.price_text || "Narx kelishiladi"}
              </p>
              {item.unit ? <p>O‘lchov birligi: {item.unit}</p> : null}
              {item.note ? (
                <p className="item-details-description">{item.note}</p>
              ) : null}
              {education && course ? (
                <dl className="item-details-facts">
                  <dt>O‘qish shakli</dt>
                  <dd>
                    {course.course_mode === "online"
                      ? "Onlayn"
                      : course.course_mode === "hybrid"
                        ? "Aralash"
                        : "Offline"}
                  </dd>
                  {course.course_duration ? (
                    <>
                      <dt>Kurs davomiyligi</dt>
                      <dd>{course.course_duration}</dd>
                    </>
                  ) : null}
                  {course.lesson_duration ? (
                    <>
                      <dt>Dars davomiyligi</dt>
                      <dd>{course.lesson_duration} daqiqa</dd>
                    </>
                  ) : null}
                  {course.age_from || course.age_to ? (
                    <>
                      <dt>Yosh</dt>
                      <dd>
                        {course.age_from || 0}–{course.age_to || "+"}
                      </dd>
                    </>
                  ) : null}
                  <dt>Qabul</dt>
                  <dd>
                    {course.enrollment_status === "closed"
                      ? "Qabul yopiq"
                      : "Qabul ochiq"}
                  </dd>
                </dl>
              ) : null}
              {item.kind === "service" &&
              item.queue_enabled &&
              "today_queue_count" in item ? (
                <p>
                  Bugungi navbat: {Math.max(0, Number(item.today_queue_count) || 0)} ta
                </p>
              ) : null}
            </div>
          </>
        ) : null}
        <div className="item-details-actions">{children}</div>
      </div>
    </dialog>,
    document.body,
  );
}
