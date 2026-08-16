import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  AccountType,
  MessageConversationRead,
  MessageProfileRead,
  MessageRead,
} from "../api/types";
import "./Messages.css";

export type MessagesApi = Pick<
  ApiClient,
  | "getMessageConversations"
  | "getMessageThread"
  | "sendMessage"
  | "sendMessageImage"
  | "editMessage"
  | "deleteMessage"
  | "createUploadGrant"
  | "uploadGrantedFile"
>;

export type MessagePeer = {
  kind: AccountType;
  publicId: string;
  name: string;
  avatarUrl?: string;
};

type Props = {
  api: MessagesApi;
  onBack(): void;
  initialPeer?: MessagePeer | null;
  onOpenProfile?(kind: AccountType, publicId: string): void;
};

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

function errorText(reason: unknown) {
  return reason instanceof Error ? reason.message : "Amal bajarilmadi.";
}

function initials(name: string) {
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

function messageDay(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "";
  return date.toLocaleDateString("uz-UZ");
}

function peerFromConversation(row: MessageConversationRead): MessagePeer {
  return {
    kind: row.target_kind,
    publicId: row.target_public_id,
    name: row.name,
    avatarUrl: row.avatar_url,
  };
}

export function Messages({ api, onBack, initialPeer = null, onOpenProfile }: Props) {
  const [peer, setPeer] = useState<MessagePeer | null>(initialPeer);
  const [other, setOther] = useState<MessageProfileRead | null>(null);
  const [conversations, setConversations] = useState<MessageConversationRead[]>([]);
  const [messages, setMessages] = useState<MessageRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [text, setText] = useState("");
  const [menu, setMenu] = useState<MessageRead | null>(null);
  const [replyTo, setReplyTo] = useState<MessageRead | null>(null);
  const [editing, setEditing] = useState<MessageRead | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<MessageRead | null>(null);
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [photoUrl, setPhotoUrl] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLElement>(null);
  const shouldScrollRef = useRef(true);
  const peerKind = peer?.kind;
  const peerPublicId = peer?.publicId;

  const loadConversations = useCallback(
    async (showLoading = true) => {
      if (showLoading) setLoading(true);
      try {
        setConversations(await api.getMessageConversations());
        setError("");
      } catch (reason) {
        setError(errorText(reason));
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [api],
  );

  const loadThread = useCallback(
    async (showLoading = true) => {
      if (!peerKind || !peerPublicId) return;
      const scroller = rootRef.current?.closest(
        ".app-shell__content",
      ) as HTMLElement | null;
      shouldScrollRef.current =
        showLoading ||
        !scroller ||
        scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 140;
      if (showLoading) setLoading(true);
      try {
        const result = await api.getMessageThread(peerKind, peerPublicId);
        setOther(result.other);
        setMessages(result.messages);
        setPeer((current) =>
          current
            ? {
                ...current,
                name: result.other.name || current.name,
                avatarUrl: result.other.avatar_url,
              }
            : current,
        );
        setError("");
      } catch (reason) {
        setError(errorText(reason));
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [api, peerKind, peerPublicId],
  );

  useEffect(() => {
    if (peerKind && peerPublicId) void loadThread();
    else void loadConversations();
  }, [loadConversations, loadThread, peerKind, peerPublicId]);

  useEffect(() => {
    if (!peerKind || !peerPublicId) return undefined;
    const poll = window.setInterval(() => {
      void loadThread(false);
    }, 3000);
    return () => window.clearInterval(poll);
  }, [loadThread, peerKind, peerPublicId]);

  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL?.(previewUrl);
    },
    [previewUrl],
  );

  useEffect(() => {
    if (!notice) return undefined;
    const timeout = window.setTimeout(() => setNotice(""), 2400);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  useEffect(() => {
    if (!peer || !shouldScrollRef.current) return;
    const scroller = rootRef.current?.closest(
      ".app-shell__content",
    ) as HTMLElement | null;
    if (scroller && typeof scroller.scrollTo === "function") {
      window.requestAnimationFrame(() => {
        scroller.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });
      });
    }
    shouldScrollRef.current = false;
  }, [messages, peer]);

  const grouped = useMemo(() => {
    const result: Array<{ day: string; rows: MessageRead[] }> = [];
    messages.forEach((message) => {
      const day = messageDay(message.created_at);
      const current = result[result.length - 1];
      if (!current || current.day !== day) result.push({ day, rows: [message] });
      else current.rows.push(message);
    });
    return result;
  }, [messages]);

  function clearImage() {
    if (previewUrl) URL.revokeObjectURL?.(previewUrl);
    setPendingImage(null);
    setPreviewUrl("");
    if (fileRef.current) fileRef.current.value = "";
  }

  function chooseImage(file: File) {
    if (!file.type.startsWith("image/")) {
      setError("Faqat rasm tanlang.");
      clearImage();
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setError("Rasm hajmi 8 MB dan oshmasin.");
      clearImage();
      return;
    }
    if (previewUrl) URL.revokeObjectURL?.(previewUrl);
    setPendingImage(file);
    setPreviewUrl(
      typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : "",
    );
    setError("");
  }

  async function send() {
    if (!peer) return;
    const clean = text.trim();
    if (editing) {
      if (!clean) {
        setError("Tahrirlash uchun matn kiriting.");
        return;
      }
      setBusy(true);
      setError("");
      try {
        const next = await api.editMessage(editing.id, clean);
        setMessages((current) =>
          current.map((row) => (row.id === next.id ? next : row)),
        );
        setEditing(null);
        setText("");
        void loadConversations(false);
      } catch (reason) {
        setError(errorText(reason));
      } finally {
        setBusy(false);
      }
      return;
    }
    if (!clean && !pendingImage) return;
    setBusy(true);
    setError("");
    shouldScrollRef.current = true;
    try {
      let next: MessageRead;
      if (pendingImage) {
        const grant = await api.createUploadGrant({
          purpose: "chat_image",
          filename: pendingImage.name,
          content_type: pendingImage.type,
          size_bytes: pendingImage.size,
        });
        await api.uploadGrantedFile(grant, pendingImage);
        next = await api.sendMessageImage({
          target_kind: peer.kind,
          target_public_id: peer.publicId,
          object_key: grant.object_key,
          file_name: pendingImage.name,
          text: clean,
          reply_to_id: replyTo?.id ?? null,
        });
        clearImage();
      } else {
        next = await api.sendMessage({
          target_kind: peer.kind,
          target_public_id: peer.publicId,
          text: clean,
          reply_to_id: replyTo?.id ?? null,
        });
      }
      setMessages((current) => [...current, next]);
      setText("");
      setReplyTo(null);
      void loadConversations(false);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function removeMessage() {
    if (!deleteTarget) return;
    setBusy(true);
    setError("");
    try {
      const next = await api.deleteMessage(deleteTarget.id);
      setMessages((current) => current.map((row) => (row.id === next.id ? next : row)));
      setDeleteTarget(null);
      void loadConversations(false);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function copyMessage(message: MessageRead) {
    const clean = message.text.trim();
    if (!clean) {
      setNotice("Nusxalanadigan matn yo‘q.");
      return;
    }
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(clean);
      } else {
        const area = document.createElement("textarea");
        area.value = clean;
        area.style.position = "fixed";
        area.style.left = "-9999px";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      setNotice("Matn nusxalandi.");
    } catch {
      setNotice("Nusxalab bo‘lmadi. Matnni qo‘lda belgilang.");
    }
  }

  function leaveThread() {
    setMenu(null);
    setReplyTo(null);
    setEditing(null);
    setText("");
    clearImage();
    if (initialPeer) {
      onBack();
      return;
    }
    setPeer(null);
    setOther(null);
    setMessages([]);
  }

  if (!peer) {
    return (
      <main ref={rootRef} className="messages-v1656">
        <header className="messages-v1656__heading">
          <button type="button" onClick={onBack}>
            ←
          </button>
          <h1>Suhbatlar</h1>
        </header>
        {error ? (
          <p className="messages-v1656__error" role="alert">
            {error}
          </p>
        ) : null}
        {loading ? (
          <div className="chat-day">Yuklanmoqda...</div>
        ) : conversations.length ? (
          <section className="chats-list">
            {conversations.map((conversation) => (
              <button
                type="button"
                className="conv"
                key={`${conversation.target_kind}:${conversation.target_public_id}`}
                aria-label={`${conversation.name}: ${conversation.last}`}
                onClick={() => setPeer(peerFromConversation(conversation))}
              >
                <span className="conv-av">
                  {conversation.avatar_url ? (
                    <img src={conversation.avatar_url} alt="" />
                  ) : (
                    initials(conversation.name)
                  )}
                </span>
                <span className="conv-main">
                  <span className="conv-name">{conversation.name}</span>
                  <span className="conv-last">{conversation.last}</span>
                </span>
                {conversation.unread > 0 ? (
                  <span className="conv-badge">{conversation.unread}</span>
                ) : null}
              </button>
            ))}
          </section>
        ) : (
          <div className="empty chat-empty">
            <h3>Suhbatlar yo&apos;q</h3>
            <p>E&apos;lon yoki sahifadan «Xabar yozish» orqali suhbat boshlang.</p>
          </div>
        )}
      </main>
    );
  }

  const shownName = other?.name || peer.name;
  const shownAvatar = other?.avatar_url || peer.avatarUrl || "";
  return (
    <main ref={rootRef} className="messages-v1656 messages-v1656--thread">
      <header className="messages-v1656__thread-heading">
        <button type="button" className="chat-back" onClick={leaveThread}>
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
        {loading && !messages.length ? (
          <div className="chat-day">Yuklanmoqda...</div>
        ) : null}
        {!loading && !messages.length ? (
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
                    onClick={() => setMenu(message)}
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
                        onClick={() => setPhotoUrl(message.media_url)}
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
              onClick={() => setReplyTo(null)}
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
                setEditing(null);
                setText("");
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
              onClick={clearImage}
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
                if (file) chooseImage(file);
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
            onChange={(event) => setText(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send();
              }
            }}
          />
          <button
            type="button"
            className="chat-send"
            aria-label={editing ? "Saqlash" : "Yuborish"}
            disabled={busy || (!text.trim() && !pendingImage)}
            onClick={() => void send()}
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
              setReplyTo(menu);
              setEditing(null);
              setMenu(null);
            }}
          >
            ↩️ Javob berish
          </button>
          <button
            type="button"
            onClick={() => {
              void copyMessage(menu);
              setMenu(null);
            }}
          >
            📋 Nusxalash
          </button>
          {menu.mine && menu.text.trim() ? (
            <button
              type="button"
              onClick={() => {
                setEditing(menu);
                setReplyTo(null);
                clearImage();
                setText(menu.text);
                setMenu(null);
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
                setDeleteTarget(menu);
                setMenu(null);
              }}
            >
              🗑 O‘chirish
            </button>
          ) : null}
          <button type="button" onClick={() => setMenu(null)}>
            Yopish
          </button>
        </div>
      ) : null}

      {deleteTarget ? (
        <div className="messages-v1656__confirm-backdrop">
          <div className="messages-v1656__confirm" role="dialog" aria-modal="true">
            <p>Bu xabar o‘chirilsinmi?</p>
            <div>
              <button type="button" onClick={() => setDeleteTarget(null)}>
                Bekor qilish
              </button>
              <button
                type="button"
                className="danger"
                disabled={busy}
                onClick={() => void removeMessage()}
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
            onClick={() => setPhotoUrl("")}
          >
            ×
          </button>
          <img src={photoUrl} alt="Rasm" />
        </div>
      ) : null}
    </main>
  );
}
