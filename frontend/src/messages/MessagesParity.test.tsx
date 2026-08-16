import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { MessageRead } from "../api/types";
import { Messages, type MessagesApi } from "./Messages";

const peer = {
  target_kind: "business" as const,
  target_public_id: "b_0123456789abcdef",
  name: "Turon savdo",
  avatar_url: "",
  last: "Salom",
  created_at: "2026-08-09T12:00:00Z",
  unread: 2,
};

const incoming: MessageRead = {
  id: 11,
  text: "Assalomu alaykum",
  media_type: "text",
  media_url: "",
  file_name: "",
  reply_to_id: null,
  reply: null,
  edited_at: null,
  deleted_at: null,
  is_deleted: false,
  mine: false,
  sender_name: "Turon savdo",
  sender_kind: "business",
  created_at: "2026-08-09T12:00:00Z",
};

function api(overrides: Partial<MessagesApi> = {}): MessagesApi {
  return {
    getMessageConversations: vi.fn().mockResolvedValue([peer]),
    getMessageThread: vi.fn().mockResolvedValue({
      other: {
        kind: "business",
        public_id: peer.target_public_id,
        name: peer.name,
        avatar_url: "",
      },
      messages: [incoming],
    }),
    sendMessage: vi.fn().mockResolvedValue({ ...incoming, id: 12, mine: true }),
    sendMessageImage: vi.fn().mockResolvedValue({
      ...incoming,
      id: 13,
      mine: true,
      media_type: "photo",
      media_url: "https://media.test/chat.webp",
    }),
    editMessage: vi.fn().mockResolvedValue({ ...incoming, text: "Yangilandi" }),
    deleteMessage: vi.fn().mockResolvedValue({
      ...incoming,
      text: "",
      is_deleted: true,
    }),
    createUploadGrant: vi.fn().mockResolvedValue({
      object_key: "private/user/7/chat_image/test.webp",
      upload_url: "https://upload.test/chat",
      method: "PUT",
      headers: { "Content-Type": "image/webp" },
      expires_in_seconds: 900,
    }),
    uploadGrantedFile: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe("Messages", () => {
  it("shows v1656 conversation list, unread badge and opens the real thread", async () => {
    const client = api();
    render(<Messages api={client} onBack={vi.fn()} />);

    expect(await screen.findByText("Turon savdo")).toBeInTheDocument();
    expect(screen.getByText("2")).toHaveClass("conv-badge");

    await userEvent.click(screen.getByRole("button", { name: /Turon savdo/ }));

    expect(await screen.findByText("Assalomu alaykum")).toBeInTheDocument();
    expect(client.getMessageThread).toHaveBeenCalledWith(
      "business",
      "b_0123456789abcdef",
    );
    expect(screen.getByText("← Suhbatlar")).toBeInTheDocument();
  });

  it("sends a reply and supports an image-only v1656 message", async () => {
    const client = api();
    const user = userEvent.setup();
    render(
      <Messages
        api={client}
        initialPeer={{
          kind: "business",
          publicId: peer.target_public_id,
          name: peer.name,
        }}
        onBack={vi.fn()}
      />,
    );

    expect(await screen.findByText("Assalomu alaykum")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Xabar amallari" }));
    await user.click(screen.getByRole("button", { name: "↩️ Javob berish" }));
    await user.type(screen.getByPlaceholderText("Xabar yozing..."), "Javob");
    await user.click(screen.getByRole("button", { name: "Yuborish" }));

    await waitFor(() =>
      expect(client.sendMessage).toHaveBeenCalledWith({
        target_kind: "business",
        target_public_id: peer.target_public_id,
        text: "Javob",
        reply_to_id: 11,
      }),
    );

    const file = new File(["image"], "test.webp", { type: "image/webp" });
    await user.upload(screen.getByLabelText("📎 Rasm qo‘shish"), file);
    expect(await screen.findByAltText("Tanlangan rasm")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yuborish" }));

    await waitFor(() => {
      expect(client.createUploadGrant).toHaveBeenCalledWith({
        purpose: "chat_image",
        filename: "test.webp",
        content_type: "image/webp",
        size_bytes: file.size,
      });
      expect(client.uploadGrantedFile).toHaveBeenCalled();
      expect(client.sendMessageImage).toHaveBeenCalledWith(
        expect.objectContaining({
          target_kind: "business",
          target_public_id: peer.target_public_id,
          object_key: "private/user/7/chat_image/test.webp",
          file_name: "test.webp",
          text: "",
        }),
      );
    });
  });

  it("edits own text and keeps soft-deleted message in the thread", async () => {
    const mine = { ...incoming, id: 22, mine: true, sender_kind: "user" as const };
    const client = api({
      getMessageThread: vi.fn().mockResolvedValue({
        other: {
          kind: "business",
          public_id: peer.target_public_id,
          name: peer.name,
          avatar_url: "",
        },
        messages: [mine],
      }),
      editMessage: vi.fn().mockResolvedValue({
        ...mine,
        text: "Yangilandi",
        edited_at: "2026-08-09T12:01:00Z",
      }),
      deleteMessage: vi.fn().mockResolvedValue({
        ...mine,
        text: "",
        is_deleted: true,
        deleted_at: "2026-08-09T12:02:00Z",
      }),
    });
    const user = userEvent.setup();
    render(
      <Messages
        api={client}
        initialPeer={{
          kind: "business",
          publicId: peer.target_public_id,
          name: peer.name,
        }}
        onBack={vi.fn()}
      />,
    );

    await screen.findByText("Assalomu alaykum");
    await user.click(screen.getByRole("button", { name: "Xabar amallari" }));
    await user.click(screen.getByRole("button", { name: "✏️ Tahrirlash" }));
    const input = screen.getByPlaceholderText("Xabar yozing...");
    await user.clear(input);
    await user.type(input, "Yangilandi");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    await waitFor(() =>
      expect(client.editMessage).toHaveBeenCalledWith(22, "Yangilandi"),
    );

    await user.click(screen.getByRole("button", { name: "Xabar amallari" }));
    await user.click(screen.getByRole("button", { name: "🗑 O‘chirish" }));
    await user.click(screen.getByRole("button", { name: "O‘chirish" }));
    await waitFor(() => expect(client.deleteMessage).toHaveBeenCalledWith(22));
    expect(await screen.findByText("Xabar o‘chirildi")).toBeInTheDocument();
  });
});
