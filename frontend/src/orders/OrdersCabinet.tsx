import { useEffect, useMemo, useRef, useState } from "react";
import type {
  OrderMessageRead,
  OrderProblemReason,
  OrderRead,
  OrderStatus,
} from "../api/types";
import { DebtorPicker } from "../profiles/DebtorPicker";
import { OrderChatPanel } from "./OrderChatPanel";
import { OrderConfirmDialog } from "./OrderConfirmDialog";
import { OrderDetailOverview } from "./OrderDetailOverview";
import { OrderList } from "./OrderList";
import { OrderProblemDialog } from "./OrderProblemDialog";
import { OrderWorkflowPanel } from "./OrderWorkflowPanel";
import { errorText, isActive, isService } from "./order-cabinet-helpers";
import type {
  OrderConfirmation,
  OrdersApi,
  OrdersCabinetProps,
  OrdersTab,
} from "./order-cabinet-types";
import "./Orders.css";

export type { OrdersApi } from "./order-cabinet-types";

export function OrdersCabinet({
  api,
  side,
  category,
  onBack,
  onUnreadChange,
  initialOrderId = null,
  beforeList,
}: OrdersCabinetProps) {
  const [orders, setOrders] = useState<OrderRead[]>([]);
  const [tab, setTab] = useState<OrdersTab>("active");
  const [selected, setSelected] = useState<OrderRead | null>(null);
  const [messages, setMessages] = useState<OrderMessageRead[]>([]);
  const [text, setText] = useState("");
  const [replyTo, setReplyTo] = useState<OrderMessageRead | null>(null);
  const [editing, setEditing] = useState<OrderMessageRead | null>(null);
  const [messageMenu, setMessageMenu] = useState<OrderMessageRead | null>(null);
  const [photoUrl, setPhotoUrl] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<OrderMessageRead | null>(null);
  const [confirmation, setConfirmation] = useState<OrderConfirmation>(null);
  const [problemOpen, setProblemOpen] = useState(false);
  const [problemReason, setProblemReason] =
    useState<OrderProblemReason>("not_received");
  const [problemNote, setProblemNote] = useState("");
  const [debtPickerOpen, setDebtPickerOpen] = useState(false);
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  const [pendingImageUrl, setPendingImageUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const chatFileRef = useRef<HTMLInputElement | null>(null);
  const initialHandledRef = useRef(false);
  const unreadChangeRef = useRef(onUnreadChange);

  useEffect(() => {
    unreadChangeRef.current = onUnreadChange;
  }, [onUnreadChange]);

  useEffect(() => {
    if (!messageMenu && !photoUrl) return undefined;
    function closeOverlay(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setMessageMenu(null);
      setPhotoUrl("");
    }
    function closeMenu(event: MouseEvent) {
      if (!messageMenu || !(event.target instanceof Element)) return;
      if (event.target.closest(".order-chat-action-menu, .order-msg-menu-btn")) return;
      setMessageMenu(null);
    }
    document.addEventListener("keydown", closeOverlay);
    document.addEventListener("click", closeMenu);
    return () => {
      document.removeEventListener("keydown", closeOverlay);
      document.removeEventListener("click", closeMenu);
    };
  }, [messageMenu, photoUrl]);

  useEffect(() => {
    if (!pendingImage) {
      setPendingImageUrl("");
      return undefined;
    }
    if (typeof URL.createObjectURL !== "function") return undefined;
    const url = URL.createObjectURL(pendingImage);
    setPendingImageUrl(url);
    return () => {
      if (typeof URL.revokeObjectURL === "function") URL.revokeObjectURL(url);
    };
  }, [pendingImage]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const rows = await (side === "customer"
        ? api.getMyOrders()
        : api.getOrderInbox());
      setOrders(rows);
      if (!initialHandledRef.current && initialOrderId) {
        initialHandledRef.current = true;
        const target = rows.find((row) => row.id === initialOrderId);
        if (target && isService(target) === (category === "service")) {
          void openDetail(target);
        }
      }
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // API App davomida barqaror, tomon o‘zgarsa qayta yuklanadi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, side]);

  const categoryOrders = useMemo(
    () => orders.filter((order) => isService(order) === (category === "service")),
    [category, orders],
  );
  const active = categoryOrders.filter(isActive);
  const problem = categoryOrders.filter((order) => order.problem_open);
  const done = categoryOrders.filter(
    (order) => !isActive(order) && !order.problem_open,
  );
  const shown = tab === "active" ? active : tab === "problem" ? problem : done;

  useEffect(() => {
    unreadChangeRef.current?.(categoryOrders.filter((order) => order.is_unread).length);
  }, [categoryOrders]);

  useEffect(() => {
    if (loading || shown.length || tab !== "active") return;
    if (problem.length) setTab("problem");
    else if (done.length) setTab("done");
  }, [done.length, loading, problem.length, shown.length, tab]);

  function replaceOrder(next: OrderRead) {
    setOrders((current) =>
      current.map((order) => (order.id === next.id ? next : order)),
    );
    setSelected((current) => (current?.id === next.id ? next : current));
  }

  async function openDetail(order: OrderRead) {
    setSelected({ ...order, is_unread: false });
    setMessages([]);
    setError("");
    try {
      const [seen, chat] = await Promise.all([
        api.markOrderSeen(order.id),
        api.getOrderChat(order.id),
      ]);
      replaceOrder({ ...seen, is_unread: false });
      setMessages(chat.messages);
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  async function mutate(action: () => Promise<OrderRead>): Promise<boolean> {
    setBusy(true);
    setError("");
    try {
      replaceOrder(await action());
      return true;
    } catch (reason) {
      setError(errorText(reason));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(status: OrderStatus) {
    if (!selected) return;
    await mutate(() => api.changeOrderStatus(selected.id, status));
  }

  async function sendMessage() {
    if (!selected) return;
    const clean = text.trim();
    if (editing) {
      if (pendingImage) {
        setError(
          "Tahrirlash paytida rasm yuborilmaydi. Avval tahrirlashni yakunlang yoki X bilan bekor qiling.",
        );
        return;
      }
      if (!clean) return;
      setBusy(true);
      try {
        const next = await api.editOrderChatMessage(selected.id, editing.id, clean);
        setMessages((current) =>
          current.map((message) => (message.id === next.id ? next : message)),
        );
        setEditing(null);
        setText("");
        await load();
      } catch (reason) {
        setError(errorText(reason));
      } finally {
        setBusy(false);
      }
      return;
    }
    if (pendingImage) {
      await uploadImage(pendingImage, clean);
      return;
    }
    if (!clean) return;
    setBusy(true);
    try {
      const next = await api.sendOrderChatMessage(selected.id, {
        text: clean,
        reply_to_id: replyTo?.id ?? null,
      });
      setMessages((current) => [...current, next]);
      setText("");
      setReplyTo(null);
      await load();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  function chooseImage(file: File) {
    if (!file.type.startsWith("image/")) {
      setError("Faqat rasm tanlang.");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      setError("Rasm hajmi 8 MB dan oshmasin.");
      return;
    }
    setError("");
    setPendingImage(file);
  }

  async function uploadImage(file: File, cleanText: string) {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const grant = await api.createUploadGrant({
        purpose: "order_chat_image",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await api.uploadGrantedFile(grant, file);
      const next = await api.sendOrderChatImage(selected.id, {
        object_key: grant.object_key,
        file_name: file.name,
        text: cleanText,
        reply_to_id: replyTo?.id ?? null,
      });
      setMessages((current) => [...current, next]);
      setText("");
      setReplyTo(null);
      setPendingImage(null);
      if (chatFileRef.current) chatFileRef.current.value = "";
      await load();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function removeMessage() {
    if (!selected || !deleteTarget) return;
    setBusy(true);
    try {
      const next = await api.deleteOrderChatMessage(selected.id, deleteTarget.id);
      setMessages((current) =>
        current.map((message) => (message.id === next.id ? next : message)),
      );
      setDeleteTarget(null);
      setConfirmation(null);
      await load();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function copyMessage(message: OrderMessageRead) {
    const clean = message.text.trim();
    if (!clean) {
      setError("Nusxalanadigan matn yo‘q.");
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
        area.focus();
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      setError("Matn nusxalandi.");
    } catch {
      setError("Nusxalab bo‘lmadi. Matnni qo‘lda belgilang.");
    }
  }

  if (selected) {
    return (
      <>
        <button
          type="button"
          aria-label="Buyurtma tafsilotini yopish"
          className="order-detail-backdrop on"
          onClick={() => setSelected(null)}
        />
        <main className="order-detail-sheet on">
          <button
            type="button"
            className="order-close"
            aria-label="Yopish"
            onClick={() => setSelected(null)}
          >
            ×
          </button>
          <div className="order-grip" />
          <h1 className="lead order-detail-title">
            {side === "customer" ? "Mening buyurtmam" : "Kelgan buyurtma"} №
            {selected.id}
          </h1>
          <div className="lead-sub order-detail-subtitle">
            {selected.title || "Buyurtma"}
          </div>
          {error ? (
            <p className="app-toast on" role="alert">
              {error}
            </p>
          ) : null}

          <OrderDetailOverview selected={selected} side={side} />

          <OrderWorkflowPanel
            selected={selected}
            side={side}
            busy={busy}
            chatFileRef={chatFileRef}
            onNotice={setError}
            onSubmitPayment={() => mutate(() => api.submitOrderPayment(selected.id))}
            onConfirmationChange={setConfirmation}
            onProblemOpenChange={setProblemOpen}
            onChooseProblemSolution={(solution) =>
              mutate(() => api.chooseOrderProblemSolution(selected.id, solution))
            }
            onChangeStatus={changeStatus}
            onDebtPickerOpenChange={setDebtPickerOpen}
          />

          <OrderChatPanel
            messages={messages}
            replyTo={replyTo}
            editing={editing}
            messageMenu={messageMenu}
            pendingImage={pendingImage}
            pendingImageUrl={pendingImageUrl}
            photoUrl={photoUrl}
            text={text}
            busy={busy}
            chatFileRef={chatFileRef}
            onMessageMenuChange={setMessageMenu}
            onPhotoUrlChange={setPhotoUrl}
            onReplyToChange={setReplyTo}
            onEditingChange={setEditing}
            onTextChange={setText}
            onPendingImageChange={setPendingImage}
            onChooseImage={chooseImage}
            onSendMessage={sendMessage}
            onCopyMessage={copyMessage}
            onDeleteTargetChange={setDeleteTarget}
            onConfirmationChange={setConfirmation}
            onClose={() => setSelected(null)}
          />

          <OrderProblemDialog
            open={problemOpen}
            reason={problemReason}
            note={problemNote}
            busy={busy}
            onReasonChange={setProblemReason}
            onNoteChange={setProblemNote}
            onOpenChange={setProblemOpen}
            onSubmit={async () => {
              if (
                await mutate(() =>
                  api.openOrderProblem(selected.id, {
                    reason: problemReason,
                    note: problemNote.trim(),
                  }),
                )
              )
                setProblemOpen(false);
            }}
          />

          {confirmation ? (
            <OrderConfirmDialog
              kind={confirmation}
              onCancel={() => {
                setConfirmation(null);
                setDeleteTarget(null);
              }}
              onConfirm={() => {
                if (confirmation === "delete-message") void removeMessage();
                else if (confirmation === "received")
                  void (async () => {
                    if (await mutate(() => api.receiveOrder(selected.id)))
                      setConfirmation(null);
                  })();
                else if (confirmation === "payment-confirm")
                  void (async () => {
                    if (
                      await mutate(() =>
                        api.decideOrderPayment(selected.id, "confirmed"),
                      )
                    )
                      setConfirmation(null);
                  })();
                else
                  void (async () => {
                    if (await mutate(() => api.handoffOrder(selected.id)))
                      setConfirmation(null);
                  })();
              }}
            />
          ) : null}
          {debtPickerOpen ? (
            <DebtorPicker
              api={api}
              title="Tashqi buyurtmani qarzga yozish"
              onCancel={() => setDebtPickerOpen(false)}
              onSelect={(debtorId) => {
                void (async () => {
                  if (
                    await mutate(() =>
                      api.decideOrderPayment(selected.id, "debt", debtorId),
                    )
                  ) {
                    setDebtPickerOpen(false);
                  }
                })();
              }}
            />
          ) : null}
        </main>
      </>
    );
  }

  return (
    <OrderList
      api={api}
      side={side}
      category={category}
      error={error}
      beforeList={beforeList}
      tab={tab}
      active={active}
      problem={problem}
      done={done}
      shown={shown}
      loading={loading}
      busy={busy}
      onBack={onBack}
      onTabChange={setTab}
      onOpenDetail={openDetail}
      onMutate={mutate}
      onSelect={setSelected}
      onConfirmationChange={setConfirmation}
      onProblemOpen={setProblemOpen}
    />
  );
}
