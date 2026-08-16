// `BusinessOnlineViews.tsx` dan ajratildi.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { money } from "../business-profile-config";
import { notifyTime, recordId, recordText } from "./shared";

export function MessagesView({
  rows,
  value,
  setValue,
  busy,
  send,
  edit,
  remove,
}: {
  rows: BusinessOnlineRecord[];
  value: string;
  setValue: (value: string) => void;
  busy: boolean;
  send: (
    peer: { id: string; kind: string },
    text: string,
    replyToId?: number | string,
  ) => Promise<void>;
  edit?: (id: number | string, text: string) => Promise<void>;
  remove?: (id: number | string) => Promise<void>;
}) {
  const [peerKey, setPeerKey] = useState<string | null>(null);
  const [menuId, setMenuId] = useState<number | string | null>(null);
  const [replyMessage, setReplyMessage] = useState<BusinessOnlineRecord | null>(null);
  const [editMessage, setEditMessage] = useState<BusinessOnlineRecord | null>(null);
  const [deleteMessage, setDeleteMessage] = useState<BusinessOnlineRecord | null>(null);
  const [notice, setNotice] = useState("");
  const conversations = useMemo(() => {
    const result = new Map<string, BusinessOnlineRecord>();
    rows.forEach((row, index) => {
      const id =
        recordText(row, "target_id", "peer_id", "receiver_id", "user_id") ||
        String(recordId(row, index));
      const kind =
        recordText(row, "target_kind", "peer_kind", "receiver_kind") || "user";
      const key = `${kind}:${id}`;
      const previous = result.get(key);
      result.set(key, {
        ...(previous ?? {}),
        ...row,
        _key: key,
        _peer_id: id,
        _peer_kind: kind,
      });
    });
    return [...result.values()];
  }, [rows]);
  const peer = conversations.find((row) => row._key === peerKey) ?? null;
  const peerName = peer
    ? recordText(peer, "name", "target_name", "peer_name", "receiver_name") || "Suhbat"
    : "";
  const thread = peer
    ? rows.filter((row, index) => {
        const id =
          recordText(row, "target_id", "peer_id", "receiver_id", "user_id") ||
          String(recordId(row, index));
        const kind =
          recordText(row, "target_kind", "peer_kind", "receiver_kind") || "user";
        return `${kind}:${id}` === peerKey;
      })
    : [];

  function messagePreview(row: BusinessOnlineRecord) {
    const text = recordText(row, "text", "message", "body").trim();
    if (text) return text.length > 80 ? `${text.slice(0, 80)}...` : text;
    return recordText(row, "media_type") === "photo" ? "📷 Rasm" : "Xabar";
  }

  async function copyMessage(row: BusinessOnlineRecord) {
    const text = recordText(row, "text", "message", "body").trim();
    if (!text) {
      setNotice("Nusxalanadigan matn yo‘q.");
      return;
    }
    await navigator.clipboard?.writeText(text);
    setNotice("Matn nusxalandi.");
  }

  if (!peer) {
    return (
      <section className="chats-list">
        {conversations.length ? (
          conversations.map((row) => {
            const name =
              recordText(row, "name", "target_name", "peer_name", "receiver_name") ||
              "Suhbat";
            const initials = name
              .trim()
              .split(/\s+/)
              .slice(0, 2)
              .map((part) => part.charAt(0))
              .join("")
              .toLocaleUpperCase("uz");
            return (
              <button
                type="button"
                className="conv"
                key={String(row._key)}
                onClick={() => setPeerKey(String(row._key))}
              >
                <span className="conv-av">{initials || "S"}</span>
                <span className="conv-main">
                  <span className="conv-name">{name}</span>
                  <span className="conv-last">
                    {recordText(row, "last", "text", "message", "body")}
                  </span>
                </span>
                {Number(row.unread ?? 0) > 0 && (
                  <span className="conv-badge">{Number(row.unread)}</span>
                )}
              </button>
            );
          })
        ) : (
          <div className="empty chat-empty">
            <h3>Suhbatlar yo'q</h3>
            <p>E'lon yoki sahifadan «Xabar yozish» orqali suhbat boshlang.</p>
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="chat-screen" aria-label={peerName}>
      <button
        type="button"
        className="chat-back"
        onClick={() => {
          setPeerKey(null);
          setMenuId(null);
          setReplyMessage(null);
          setEditMessage(null);
        }}
      >
        ← Suhbatlar
      </button>
      <div className="chat-thread">
        {thread.length ? (
          thread.map((row, index) => {
            const deleted = Boolean(row.is_deleted);
            const mine =
              recordText(row, "sender_kind") === "business" || Boolean(row.mine);
            return (
              <div
                className={`msg ${mine ? "me" : "them"}`}
                key={String(recordId(row, index))}
              >
                {!deleted && (
                  <button
                    type="button"
                    className="order-msg-menu-btn"
                    aria-label="Xabar amallari"
                    onClick={() => setMenuId(recordId(row, index))}
                  >
                    ⋯
                  </button>
                )}
                {deleted ? (
                  <div className="order-chat-deleted">Xabar o‘chirildi</div>
                ) : (
                  <>
                    {row.reply && typeof row.reply === "object" && (
                      <div className="order-chat-reply-preview">
                        <b>
                          ↩{" "}
                          {recordText(
                            row.reply as BusinessOnlineRecord,
                            "sender_name",
                          ) || "Xabar"}
                        </b>
                        {messagePreview(row.reply as BusinessOnlineRecord)}
                      </div>
                    )}
                    <div className="order-chat-text">
                      {recordText(row, "text", "message", "body")}
                    </div>
                  </>
                )}
                <span className="msg-time">
                  {notifyTime(row.created_at)}
                  {row.edited_at ? " · Tahrirlangan" : ""}
                </span>
              </div>
            );
          })
        ) : (
          <div className="chat-day">Hozircha xabar yo'q. Birinchi bo'lib yozing!</div>
        )}
      </div>
      {notice && (
        <div className="app-toast on" role="status">
          {notice}
        </div>
      )}
      {menuId !== null &&
        (() => {
          const row = thread.find((item, index) => recordId(item, index) === menuId);
          if (!row) return null;
          const mine =
            recordText(row, "sender_kind") === "business" || Boolean(row.mine);
          return (
            <div className="order-chat-action-menu on" role="menu">
              <button
                type="button"
                onClick={() => {
                  setReplyMessage(row);
                  setEditMessage(null);
                  setMenuId(null);
                }}
              >
                ↩️ Javob berish
              </button>
              <button
                type="button"
                onClick={() => {
                  setMenuId(null);
                  void copyMessage(row);
                }}
              >
                📋 Nusxalash
              </button>
              {mine && recordText(row, "text", "message", "body").trim() && (
                <button
                  type="button"
                  onClick={() => {
                    setEditMessage(row);
                    setReplyMessage(null);
                    setValue(recordText(row, "text", "message", "body"));
                    setMenuId(null);
                  }}
                >
                  ✏️ Tahrirlash
                </button>
              )}
              {mine && (
                <button
                  type="button"
                  className="danger"
                  onClick={() => {
                    setDeleteMessage(row);
                    setMenuId(null);
                  }}
                >
                  🗑 O‘chirish
                </button>
              )}
              <button type="button" onClick={() => setMenuId(null)}>
                Yopish
              </button>
            </div>
          );
        })()}
      <div className="chat-compose">
        {replyMessage && (
          <div className="order-chat-state on">
            Javob berilyapti
            <small>{messagePreview(replyMessage)}</small>
            <button
              type="button"
              aria-label="Javobni bekor qilish"
              onClick={() => setReplyMessage(null)}
            >
              ×
            </button>
          </div>
        )}
        {editMessage && (
          <div className="order-chat-state edit on">
            Xabar tahrirlanyapti
            <small>{messagePreview(editMessage)}</small>
            <button
              type="button"
              aria-label="Tahrirlashni bekor qilish"
              onClick={() => {
                setEditMessage(null);
                setValue("");
              }}
            >
              ×
            </button>
          </div>
        )}
        <div className="chat-attach-row">
          <label className="chat-attach-btn">
            📎 Rasm qo‘shish
            <input className="chat-file" type="file" accept="image/*" />
          </label>
        </div>
        <div className="chat-bar">
          <input
            className="chat-input"
            value={value}
            onChange={(event) => setValue(event.currentTarget.value)}
            placeholder="Xabar yozing..."
            autoComplete="off"
          />
          <button
            type="button"
            className="chat-send"
            aria-label={editMessage ? "Saqlash" : "Yuborish"}
            disabled={busy || !value.trim()}
            onClick={async () => {
              if (editMessage) {
                await edit?.(recordId(editMessage), value.trim());
                setEditMessage(null);
                setValue("");
                return;
              }
              const target = {
                id: String(peer._peer_id),
                kind: String(peer._peer_kind),
              };
              if (replyMessage) {
                await send(target, value.trim(), recordId(replyMessage));
              } else {
                await send(target, value.trim());
              }
              setReplyMessage(null);
            }}
          >
            {editMessage ? (
              "✓"
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
            )}
          </button>
        </div>
      </div>
      {deleteMessage && (
        <>
          <button
            type="button"
            className="app-modal-back on"
            aria-label="Bekor qilish"
            onClick={() => setDeleteMessage(null)}
          />
          <div className="app-confirm on" role="dialog" aria-modal="true">
            <p className="acf-text">Bu xabar o‘chirilsinmi?</p>
            <div className="acf-btns">
              <button
                type="button"
                className="acf-cancel"
                onClick={() => setDeleteMessage(null)}
              >
                Bekor qilish
              </button>
              <button
                type="button"
                className="acf-ok danger"
                disabled={busy}
                onClick={async () => {
                  await remove?.(recordId(deleteMessage));
                  setDeleteMessage(null);
                }}
              >
                O‘chirish
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
