import type { RefObject } from "react";

import type { AccountType, MessageProfileRead, MessageRead } from "../api/types";

type MessageGroup = { day: string; rows: MessageRead[] };

type Props = {
  rootRef: RefObject<HTMLElement | null>;
  fileRef: RefObject<HTMLInputElement | null>;
  peer: {
    kind: AccountType;
    publicId: string;
    name: string;
    avatarUrl?: string;
  };
  other: MessageProfileRead | null;
  onOpenProfile?: (kind: AccountType, publicId: string) => void;
  error: string;
  notice: string;
  loading: boolean;
  messageCount: number;
  grouped: MessageGroup[];
  menu: MessageRead | null;
  replyTo: MessageRead | null;
  editing: MessageRead | null;
  deleteTarget: MessageRead | null;
  pendingImage: File | null;
  previewUrl: string;
  text: string;
  busy: boolean;
  photoUrl: string;
  onLeave: () => void;
  onMenu: (message: MessageRead | null) => void;
  onReply: (message: MessageRead | null) => void;
  onEdit: (message: MessageRead | null) => void;
  onDelete: (message: MessageRead | null) => void;
  onText: (value: string) => void;
  onPhotoUrl: (value: string) => void;
  onClearImage: () => void;
  onChooseImage: (file: File) => void;
  onSend: () => void | Promise<void>;
  onCopyMessage: (message: MessageRead) => void | Promise<void>;
  onRemoveMessage: () => void | Promise<void>;
};

export function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.length
    ? words
        .slice(0, 2)
        .map((word) => word.charAt(0).toUpperCase())
        .join("")
    : "S";
}

function messagePreview(
  message: Pick<MessageRead, "is_deleted" | "media_type" | "text">,
) {
  if (message.is_deleted) return "Xabar o‘chirildi";
  const text = message.text.trim();
  const value = message.media_type === "photo" ? text || "📷 Rasm" : text || "Xabar";
  return value.length > 80 ? `${value.slice(0, 80)}...` : value;
}

function messageTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "";
  return date.toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" });
}

export function MessagesThreadView({
  rootRef,
  fileRef,
  peer,
  other,
  onOpenProfile,
  error,
  notice,
  loading,
  messageCount,
  grouped,
  menu,
  replyTo,
  editing,
  deleteTarget,
  pendingImage,
  previewUrl,
  text,
  busy,
  photoUrl,
  onLeave,
  onMenu,
  onReply,
  onEdit,
  onDelete,
  onText,
  onPhotoUrl,
  onClearImage,
  onChooseImage,
  onSend,
  onCopyMessage,
  onRemoveMessage,
}: Props) {
  const shownName = other?.name || peer.name;
  const shownAvatar = other?.avatar_url || peer.avatarUrl || "";

  return (
    <main ref={rootRef} className="messages-v1656 messages-v1656--thread">
      <header className="messages-v1656__thread-heading">
        <button type="button" className="chat-back" onClick={onLeave}>
          ← Suhbatlar
        </button>
        <button
          type="button"
          className="messages-v1656__peer"
          disabled={!onOpenProfile}
          onClick={() => onOpenProfile?.(peer.kind, peer.publicId)}
        >
          <span className="conv-av">
            {shownAvatar ? <img src={shownAvatar} alt="" /> : initials(shownName)}
          </span>
          <span>{shownName}</span>
        </button>
      </header>
      {error ? (
        <p className="messages-v1656__error" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <div className="app-toast on" role="status">
          {notice}
        </div>
      ) : null}
      <section className="chat-thread" aria-label={shownName}>
        {loading && !messageCount ? (
          <div className="chat-day">Yuklanmoqda...</div>
        ) : null}
        {!loading && !messageCount ? (
          <div className="chat-day">
            Hozircha xabar yo&apos;q. Birinchi bo&apos;lib yozing!
          </div>
        ) : null}
        {grouped.map((group) => (
          <div className="messages-v1656__day-group" key={group.day || "day"}>
            {group.day ? <div className="chat-day">{group.day}</div> : null}
            {group.rows.map((message) => (
              <article
                className={`msg ${message.mine ? "me" : "them"}`}
                key={message.id}
              >
                {!message.is_deleted ? (
                  <button
                    type="button"
                    className="order-msg-menu-btn"
                    aria-label="Xabar amallari"
                    onClick={() => onMenu(message)}
                  >
                    ⋯
                  </button>
                ) : null}
                {message.is_deleted ? (
                  <div className="order-chat-deleted">Xabar o‘chirildi</div>
                ) : (
                  <>
                    {message.reply ? (
                      <div className="order-chat-reply-preview">
                        <b>↩ {message.reply.sender_name || "Xabar"}</b>
                        {messagePreview(message.reply)}
                      </div>
                    ) : null}
                    {message.media_type === "photo" && message.media_url ? (
                      <img
                        className="order-chat-photo"
                        src={message.media_url}
                        alt="Rasm"
                        title="Rasmni ochish"
                        onClick={() => onPhotoUrl(message.media_url)}
                      />
                    ) : null}
                    {message.text ? (
                      <div className="order-chat-text">{message.text}</div>
                    ) : null}
                  </>
                )}
                <span className="msg-time">
                  {messageTime(message.created_at)}
                  {message.edited_at ? " · Tahrirlangan" : ""}
                </span>
              </article>
            ))}
          </div>
        ))}
      </section>

      <section className="chat-compose">
        {replyTo ? (
          <div className="order-chat-state on">
            Javob berilyapti
            <small>{messagePreview(replyTo)}</small>
            <button
              type="button"
              aria-label="Javobni bekor qilish"
              onClick={() => onReply(null)}
            >
              ×
            </button>
          </div>
        ) : null}
        {editing ? (
          <div className="order-chat-state edit on">
            Xabar tahrirlanyapti
            <small>{messagePreview(editing)}</small>
            <button
              type="button"
              aria-label="Tahrirlashni bekor qilish"
              onClick={() => {
                onEdit(null);
                onText("");
              }}
            >
              ×
            </button>
          </div>
        ) : null}
        {pendingImage ? (
          <div className="order-chat-preview on">
            <button
              type="button"
              className="order-chat-preview-x"
              aria-label="Rasmni bekor qilish"
              onClick={onClearImage}
            >
              ×
            </button>
            <img src={previewUrl || undefined} alt="Tanlangan rasm" />
            <div className="idesc">
              Rasm tanlandi. Yuborish uchun pastdagi tugmani bosing.
            </div>
          </div>
        ) : null}
        <div className="chat-attach-row">
          <label className="chat-attach-btn">
            📎 Rasm qo‘shish
            <input
              ref={fileRef}
              className="chat-file"
              type="file"
              accept="image/*"
              aria-label="📎 Rasm qo‘shish"
              disabled={busy || Boolean(editing)}
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                if (file) onChooseImage(file);
              }}
            />
          </label>
        </div>
        <div className="chat-bar">
          <input
            className="chat-input"
            value={text}
            placeholder="Xabar yozing..."
            autoComplete="off"
            onChange={(event) => onText(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void onSend();
              }
            }}
          />
          <button
            type="button"
            className="chat-send"
            aria-label={editing ? "Saqlash" : "Yuborish"}
            disabled={busy || (!text.trim() && !pendingImage)}
            onClick={() => void onSend()}
          >
            {editing ? (
              "✓"
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
            )}
          </button>
        </div>
      </section>

      {menu ? (
        <div className="order-chat-action-menu on" role="menu">
          <button
            type="button"
            onClick={() => {
              onReply(menu);
              onEdit(null);
              onMenu(null);
            }}
          >
            ↩️ Javob berish
          </button>
          <button
            type="button"
            onClick={() => {
              void onCopyMessage(menu);
              onMenu(null);
            }}
          >
            📋 Nusxalash
          </button>
          {menu.mine && menu.text.trim() ? (
            <button
              type="button"
              onClick={() => {
                onEdit(menu);
                onReply(null);
                onClearImage();
                onText(menu.text);
                onMenu(null);
              }}
            >
              ✏️ Tahrirlash
            </button>
          ) : null}
          {menu.mine ? (
            <button
              type="button"
              className="danger"
              onClick={() => {
                onDelete(menu);
                onMenu(null);
              }}
            >
              🗑 O‘chirish
            </button>
          ) : null}
          <button type="button" onClick={() => onMenu(null)}>
            Yopish
          </button>
        </div>
      ) : null}

      {deleteTarget ? (
        <div className="messages-v1656__confirm-backdrop">
          <div className="messages-v1656__confirm" role="dialog" aria-modal="true">
            <p>Bu xabar o‘chirilsinmi?</p>
            <div>
              <button type="button" onClick={() => onDelete(null)}>
                Bekor qilish
              </button>
              <button
                type="button"
                className="danger"
                disabled={busy}
                onClick={() => void onRemoveMessage()}
              >
                O‘chirish
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {photoUrl ? (
        <div className="order-photo-viewer on" role="dialog" aria-modal="true">
          <button
            type="button"
            className="order-photo-viewer-x"
            aria-label="Yopish"
            onClick={() => onPhotoUrl("")}
          >
            ×
          </button>
          <img src={photoUrl} alt="Rasm" />
        </div>
      ) : null}
    </main>
  );
}
