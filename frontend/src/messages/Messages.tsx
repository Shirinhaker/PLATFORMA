import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  AccountType,
  MessageConversationRead,
  MessageProfileRead,
  MessageRead,
} from "../api/types";
import { MessagesThreadView, initials } from "./MessagesThreadView";
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

  return (
    <MessagesThreadView
      rootRef={rootRef}
      fileRef={fileRef}
      peer={peer}
      other={other}
      onOpenProfile={onOpenProfile}
      error={error}
      notice={notice}
      loading={loading}
      messageCount={messages.length}
      grouped={grouped}
      menu={menu}
      replyTo={replyTo}
      editing={editing}
      deleteTarget={deleteTarget}
      pendingImage={pendingImage}
      previewUrl={previewUrl}
      text={text}
      busy={busy}
      photoUrl={photoUrl}
      onLeave={leaveThread}
      onMenu={setMenu}
      onReply={setReplyTo}
      onEdit={setEditing}
      onDelete={setDeleteTarget}
      onText={setText}
      onPhotoUrl={setPhotoUrl}
      onClearImage={clearImage}
      onChooseImage={chooseImage}
      onSend={send}
      onCopyMessage={copyMessage}
      onRemoveMessage={removeMessage}
    />
  );
}
