import type { RefObject } from "react";

import type { OrderMessageRead } from "../api/types";
import { createdText, messagePreview } from "./order-cabinet-helpers";
import type { OrderConfirmation } from "./order-cabinet-types";

type OrderChatPanelProps = {
  messages: OrderMessageRead[];
  replyTo: OrderMessageRead | null;
  editing: OrderMessageRead | null;
  messageMenu: OrderMessageRead | null;
  pendingImage: File | null;
  pendingImageUrl: string;
  photoUrl: string;
  text: string;
  busy: boolean;
  chatFileRef: RefObject<HTMLInputElement | null>;
  onMessageMenuChange(message: OrderMessageRead | null): void;
  onPhotoUrlChange(url: string): void;
  onReplyToChange(message: OrderMessageRead | null): void;
  onEditingChange(message: OrderMessageRead | null): void;
  onTextChange(text: string): void;
  onPendingImageChange(file: File | null): void;
  onChooseImage(file: File): void;
  onSendMessage(): void | Promise<void>;
  onCopyMessage(message: OrderMessageRead): void | Promise<void>;
  onDeleteTargetChange(message: OrderMessageRead | null): void;
  onConfirmationChange(confirmation: OrderConfirmation): void;
  onClose(): void;
};

export function OrderChatPanel({
  messages,
  replyTo,
  editing,
  messageMenu,
  pendingImage,
  pendingImageUrl,
  photoUrl,
  text,
  busy,
  chatFileRef,
  onMessageMenuChange,
  onPhotoUrlChange,
  onReplyToChange,
  onEditingChange,
  onTextChange,
  onPendingImageChange,
  onChooseImage,
  onSendMessage,
  onCopyMessage,
  onDeleteTargetChange,
  onConfirmationChange,
  onClose,
}: OrderChatPanelProps) {
  return (
    <>
      <section className="panel-card order-chat-box">
        <b>💬 Buyurtma chati</b>
        <div className="idesc">
          Bu suhbat faqat shu buyurtmaga bog‘langan. Umumiy chatga aralashmaydi.
        </div>
        <div className="order-chat-list">
          {!messages.length ? (
            <div className="order-chat-empty">
              Hozircha buyurtma bo‘yicha xabar yo‘q.
            </div>
          ) : (
            messages.map((message) => (
              <div className={`msg ${message.mine ? "me" : "them"}`} key={message.id}>
                {message.is_deleted ? (
                  <div className="order-chat-deleted">Xabar o‘chirildi</div>
                ) : (
                  <>
                    <button
                      type="button"
                      className="order-msg-menu-btn"
                      aria-label="Xabar amallari"
                      onClick={() => onMessageMenuChange(message)}
                    >
                      ⋯
                    </button>
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
                        role="button"
                        tabIndex={0}
                        onClick={() => onPhotoUrlChange(message.media_url)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ")
                            onPhotoUrlChange(message.media_url);
                        }}
                      />
                    ) : null}
                    {message.text ? (
                      <div className="order-chat-text">{message.text}</div>
                    ) : null}
                  </>
                )}
                <span className="msg-time">
                  {message.mine ? "Siz" : message.sender_name} ·{" "}
                  {createdText(message.created_at)}
                  {message.edited_at ? " · Tahrirlangan" : ""}
                </span>
              </div>
            ))
          )}
        </div>
        {replyTo ? (
          <div className="order-chat-state on">
            Javob berilyapti<small>{messagePreview(replyTo)}</small>
            <button
              type="button"
              aria-label="Javobni bekor qilish"
              onClick={() => onReplyToChange(null)}
            >
              ×
            </button>
          </div>
        ) : null}
        {editing ? (
          <div className="order-chat-state edit on">
            Xabar tahrirlanyapti<small>{messagePreview(editing)}</small>
            <button
              type="button"
              aria-label="Tahrirlashni bekor qilish"
              onClick={() => {
                onEditingChange(null);
                onTextChange("");
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
              onClick={() => {
                onPendingImageChange(null);
                if (chatFileRef.current) chatFileRef.current.value = "";
              }}
            >
              ×
            </button>
            {pendingImageUrl ? (
              <img src={pendingImageUrl} alt="Tanlangan rasm" />
            ) : null}
            <div className="idesc">
              Rasm tanlandi. Yuborish uchun chatdagi “Yuborish” tugmasini bosing.
            </div>
          </div>
        ) : null}
        <div className="order-chat-attach-row">
          <label className="order-chat-attach-btn">
            📎 Rasm qo‘shish
            <input
              ref={chatFileRef}
              className="order-chat-file"
              type="file"
              accept="image/*"
              disabled={busy || Boolean(editing)}
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                if (file) onChooseImage(file);
              }}
            />
          </label>
        </div>
        <div className="order-chat-send">
          <input
            placeholder="Buyurtma bo‘yicha xabar yozing..."
            value={text}
            onChange={(event) => onTextChange(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void onSendMessage();
              }
            }}
          />
          <button type="button" disabled={busy} onClick={() => void onSendMessage()}>
            {editing ? "Saqlash" : "Yuborish"}
          </button>
        </div>
      </section>
      {messageMenu ? (
        <div className="order-chat-action-menu on">
          <button
            type="button"
            onClick={() => {
              onReplyToChange(messageMenu);
              onEditingChange(null);
              onMessageMenuChange(null);
            }}
          >
            ↩️ Javob berish
          </button>
          <button
            type="button"
            onClick={() => {
              void onCopyMessage(messageMenu);
              onMessageMenuChange(null);
            }}
          >
            📋 Nusxalash
          </button>
          {messageMenu.mine && messageMenu.text.trim() ? (
            <button
              type="button"
              onClick={() => {
                onEditingChange(messageMenu);
                onReplyToChange(null);
                onTextChange(messageMenu.text);
                onPendingImageChange(null);
                onMessageMenuChange(null);
              }}
            >
              ✏️ Tahrirlash
            </button>
          ) : null}
          {messageMenu.mine ? (
            <button
              type="button"
              className="danger"
              onClick={() => {
                onDeleteTargetChange(messageMenu);
                onConfirmationChange("delete-message");
                onMessageMenuChange(null);
              }}
            >
              🗑 O‘chirish
            </button>
          ) : null}
        </div>
      ) : null}
      {photoUrl ? (
        <div
          className="order-photo-viewer on"
          role="dialog"
          aria-label="Buyurtma chati rasmi"
          onClick={(event) => {
            if (event.currentTarget === event.target) onPhotoUrlChange("");
          }}
        >
          <button
            type="button"
            className="order-photo-viewer-x"
            aria-label="Rasmni yopish"
            onClick={() => onPhotoUrlChange("")}
          >
            ×
          </button>
          <img src={photoUrl} alt="Buyurtma chati rasmi" />
        </div>
      ) : null}
      <button
        type="button"
        className="btn btn-soft btn-block"
        onClick={() => onClose()}
      >
        Yopish
      </button>
    </>
  );
}
