import type { OrderProblemReason } from "../api/types";
import { PROBLEM_REASONS } from "./order-cabinet-helpers";

type OrderProblemDialogProps = {
  open: boolean;
  reason: OrderProblemReason;
  note: string;
  busy: boolean;
  onReasonChange(reason: OrderProblemReason): void;
  onNoteChange(note: string): void;
  onOpenChange(open: boolean): void;
  onSubmit(): unknown;
};

export function OrderProblemDialog({
  open,
  reason: problemReason,
  note: problemNote,
  busy,
  onReasonChange,
  onNoteChange,
  onOpenChange,
  onSubmit,
}: OrderProblemDialogProps) {
  const problemOpen = open;

  return (
    <>
      {problemOpen ? (
        <div className="order-confirm-backdrop">
          <section
            aria-label="To'lov bo'yicha muammo"
            aria-modal="true"
            className="order-confirm order-problem-dialog"
            role="dialog"
          >
            <b>To'lov bo'yicha muammo</b>
            <div className="lead-sub">
              Sababni tanlang. Muammo hal bo'lmaguncha tayyorlash, dostavka va yakunlash
              bloklanadi.
            </div>
            <label>
              Muammo sababi
              <select
                value={problemReason}
                onChange={(event) =>
                  onReasonChange(event.currentTarget.value as OrderProblemReason)
                }
              >
                {PROBLEM_REASONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Izoh
              <textarea
                placeholder="Muammoni qisqacha tushuntiring"
                value={problemNote}
                onChange={(event) => onNoteChange(event.currentTarget.value)}
              />
            </label>
            <div className="order-confirm-actions">
              <button
                type="button"
                className="mini-btn"
                onClick={() => onOpenChange(false)}
              >
                Bekor qilish
              </button>
              <button
                type="button"
                className="mini-btn warning"
                disabled={busy}
                onClick={() => void onSubmit()}
              >
                Muammoli buyurtmaga o'tkazish
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
