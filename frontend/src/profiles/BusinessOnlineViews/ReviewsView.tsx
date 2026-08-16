// `BusinessOnlineViews.tsx` dan ajratildi.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { money } from "../business-profile-config";
import { notifyTime, recordId, recordText } from "./shared";

export function ReviewsView({
  rows,
  ratingSum,
  ratingCount,
  replyId,
  reply,
  setReplyId,
  setReply,
  busy,
  save,
}: {
  rows: BusinessOnlineRecord[];
  ratingSum: number;
  ratingCount: number;
  replyId: number | string | null;
  reply: string;
  setReplyId: (id: number | string | null) => void;
  setReply: (value: string) => void;
  busy: boolean;
  save: (id: number | string, reply: string) => Promise<void>;
}) {
  const average = ratingCount ? (ratingSum / ratingCount).toFixed(1) : "0";
  const [replyError, setReplyError] = useState("");
  return (
    <section>
      {replyError && (
        <div className="app-toast on" role="alert">
          {replyError}
        </div>
      )}
      <div className="panel-card business-review-summary">
        <div>
          <div className="idesc">O'rtacha baho</div>
          <div className="business-review-average">
            {average} <span>★</span>
          </div>
        </div>
        <div className="business-review-count">
          <div className="idesc">Jami fikr</div>
          <div>{rows.length}</div>
        </div>
      </div>
      <div className="idesc business-review-hint">
        Mijoz fikrini o'chirib bo'lmaydi. Har bir fikrga javob berishingiz va
        javobingizni yangilashingiz mumkin.
      </div>
      <div className="business-review-list">
        {rows.length ? (
          rows.map((row, index) => {
            const id = recordId(row, index);
            const ownerReply = recordText(
              row,
              "owner_reply",
              "business_reply",
              "reply",
            );
            const activeReply = replyId === id ? reply : ownerReply;
            return (
              <article className="sp-review-card" key={String(id)}>
                <div className="business-review-card-head">
                  <div>
                    <b>
                      {recordText(row, "user_name", "reviewer_name", "name") || "Mijoz"}
                    </b>
                    <div className="idesc business-review-date">
                      {notifyTime(row.created_at)}
                    </div>
                  </div>
                  <span
                    className="business-review-stars"
                    aria-label={`5 dan ${Math.max(0, Math.min(5, Number(row.stars ?? row.rating ?? 0)))} baho`}
                  >
                    {Array.from({ length: 5 }, (_, star) => (
                      <span
                        className="rv-star"
                        style={{
                          color:
                            star < Number(row.stars ?? row.rating ?? 0)
                              ? "#f5a623"
                              : "#d1d5db",
                        }}
                        key={star}
                      >
                        ★
                      </span>
                    ))}
                  </span>
                </div>
                <div className="idesc business-review-comment">
                  {recordText(row, "comment", "text", "review") || "Matnsiz baho"}
                </div>
                {ownerReply && (
                  <div className="sp-owner-reply">
                    <b>Sizning javobingiz</b>
                    <div>{ownerReply}</div>
                  </div>
                )}
                <textarea
                  className="textarea"
                  placeholder="Mijozga javob yozing..."
                  value={activeReply}
                  onFocus={() => {
                    if (replyId !== id) {
                      setReplyId(id);
                      setReply(ownerReply);
                    }
                  }}
                  onChange={(event) => {
                    if (replyId !== id) setReplyId(id);
                    setReplyError("");
                    setReply(event.currentTarget.value);
                  }}
                />
                <button
                  type="button"
                  className="btn btn-soft btn-block"
                  disabled={busy}
                  onClick={() => {
                    const value = activeReply.trim();
                    if (!value) {
                      setReplyError("Javob matnini kiriting.");
                      return;
                    }
                    setReplyError("");
                    void save(id, value);
                  }}
                >
                  {ownerReply ? "Javobni yangilash" : "Javob berish"}
                </button>
              </article>
            );
          })
        ) : (
          <div className="empty business-review-empty">
            <h3>Hozircha fikr yo'q</h3>
            <p>Mijozlar qoldirgan baho va fikrlar shu yerda ko'rinadi.</p>
          </div>
        )}
      </div>
    </section>
  );
}
