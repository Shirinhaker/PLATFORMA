import { useCallback, useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { DiningOrder, DiningPayType } from "../api/types";
import { DebtorPicker } from "../profiles/DebtorPicker";
import {
  CancelModal,
  ConfirmModal,
  EditBillModal,
  FinalizePanel,
  OpenPanel,
  ProblemModal,
  ProblemPanel,
} from "./BusinessDiningCashViews";
import "./BusinessDiningCash.css";

export type BusinessDiningCashApi = Pick<
  ApiClient,
  | "getDiningOrders"
  | "confirmDiningPayment"
  | "updateDiningCashierItems"
  | "finalizeDiningOrder"
  | "cancelDiningOrder"
  | "openDiningProblem"
  | "resolveDiningProblem"
  | "getDebtors"
  | "createDebtor"
>;

const CASH_METHODS: ReadonlyArray<keyof BusinessDiningCashApi> = [
  "getDiningOrders",
  "confirmDiningPayment",
  "updateDiningCashierItems",
  "finalizeDiningOrder",
  "cancelDiningOrder",
  "openDiningProblem",
  "resolveDiningProblem",
  "getDebtors",
  "createDebtor",
];

export function supportsDiningCashApi(api: object): api is BusinessDiningCashApi {
  return CASH_METHODS.every(
    (method) => typeof (api as Partial<BusinessDiningCashApi>)[method] === "function",
  );
}

type Tab = "open" | "problem" | "done";

type Modal =
  | { kind: "edit"; order: DiningOrder }
  | { kind: "problem"; order: DiningOrder }
  | { kind: "cancel"; order: DiningOrder }
  | { kind: "debt"; order: DiningOrder }
  | { kind: "pay"; order: DiningOrder; payType: DiningPayType }
  | { kind: "resolve"; order: DiningOrder }
  | { kind: "finalize"; order: DiningOrder };

type Props = {
  api: BusinessDiningCashApi;
  onChanged?: () => void;
};

function reason(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

export function BusinessDiningCash({ api, onChanged }: Props) {
  const [orders, setOrders] = useState<DiningOrder[]>([]);
  const [tab, setTab] = useState<Tab>("open");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<Modal | null>(null);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await api.getDiningOrders();
      setOrders(rows.filter((row) => row.kind === "order"));
    } catch (error) {
      setFailed(true);
      setMessage(reason(error));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!message || failed) return;
    const timeout = window.setTimeout(() => setMessage(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [message, failed]);

  function report(text: string) {
    setFailed(false);
    setMessage(text);
    onChanged?.();
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
      setModal(null);
      await load();
    } catch (error) {
      setFailed(true);
      setMessage(reason(error));
    } finally {
      setBusy(false);
    }
  }

  const open = orders.filter(
    (order) =>
      order.status === "active" &&
      order.payment_status !== "confirmed" &&
      !order.problem_open,
  );
  const problems = orders.filter(
    (order) => order.problem_open && order.status === "active",
  );
  const finalize = orders.filter(
    (order) =>
      order.status === "active" &&
      order.payment_status === "confirmed" &&
      !order.problem_open,
  );

  if (loading) {
    return (
      <div className="dining-cash">
        <div className="idesc">Ichki hisoblar yuklanmoqda...</div>
      </div>
    );
  }

  return (
    <div className="dining-cash">
      <div className="dining-cash-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "open"}
          className={`seg-b${tab === "open" ? " on" : ""}`}
          onClick={() => setTab("open")}
        >
          Ochiq
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "problem"}
          className={`seg-b${tab === "problem" ? " on" : ""}`}
          onClick={() => setTab("problem")}
        >
          Muammoli
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "done"}
          className={`seg-b${tab === "done" ? " on" : ""}`}
          onClick={() => setTab("done")}
        >
          Yakunlangan
        </button>
      </div>

      {message ? (
        <div
          className={`dining-cash-message on${failed ? " error" : ""}`}
          role="status"
        >
          {message}
        </div>
      ) : null}

      {tab === "open" ? (
        <OpenPanel
          orders={open}
          busy={busy}
          onEdit={(order) => setModal({ kind: "edit", order })}
          onPay={(order, payType) => setModal({ kind: "pay", order, payType })}
          onDebt={(order) => setModal({ kind: "debt", order })}
          onProblem={(order) => setModal({ kind: "problem", order })}
          onCancel={(order) => setModal({ kind: "cancel", order })}
        />
      ) : null}

      {tab === "problem" ? (
        <ProblemPanel
          orders={problems}
          busy={busy}
          onResolve={(order) => setModal({ kind: "resolve", order })}
        />
      ) : null}

      {tab === "done" ? (
        <FinalizePanel
          orders={finalize}
          busy={busy}
          onFinalize={(order) => setModal({ kind: "finalize", order })}
        />
      ) : null}

      {modal?.kind === "edit" ? (
        <EditBillModal
          order={modal.order}
          busy={busy}
          onClose={() => setModal(null)}
          onSave={(items) =>
            void run(async () => {
              await api.updateDiningCashierItems(modal.order.id, items);
              report("Hisob yangilandi ✅");
            })
          }
        />
      ) : null}

      {modal?.kind === "problem" ? (
        <ProblemModal
          busy={busy}
          onClose={() => setModal(null)}
          onSave={(body) =>
            void run(async () => {
              await api.openDiningProblem(modal.order.id, body);
              setTab("problem");
              report("Hisob Muammoli bo‘limiga o‘tkazildi");
            })
          }
        />
      ) : null}

      {modal?.kind === "cancel" ? (
        <CancelModal
          busy={busy}
          onClose={() => setModal(null)}
          onConfirm={(text) =>
            void run(async () => {
              await api.cancelDiningOrder(modal.order.id, text);
              report("Ichki buyurtma bekor qilindi, stol bo‘shadi ✅");
            })
          }
        />
      ) : null}

      {modal?.kind === "debt" ? (
        <DebtorPicker
          api={api}
          title="Ichki hisobni qarzga yozish"
          onCancel={() => setModal(null)}
          onSelect={(debtorId) =>
            void run(async () => {
              await api.confirmDiningPayment(modal.order.id, {
                pay_type: "qarz",
                debtor_id: debtorId,
              });
              report("Ichki hisob qarz daftariga yozildi ✅");
            })
          }
        />
      ) : null}

      {modal?.kind === "pay" ? (
        <ConfirmModal
          text="To‘lov qabul qilinganini tasdiqlaysizmi?"
          okText="Tasdiqlash"
          busy={busy}
          onClose={() => setModal(null)}
          onConfirm={() =>
            void run(async () => {
              await api.confirmDiningPayment(modal.order.id, {
                pay_type: modal.payType,
              });
              report("To‘lov tasdiqlandi ✅");
            })
          }
        />
      ) : null}

      {modal?.kind === "resolve" ? (
        <ConfirmModal
          text="Muammo hal qilinganini tasdiqlaysizmi?"
          okText="Hal qilindi"
          busy={busy}
          onClose={() => setModal(null)}
          onConfirm={() =>
            void run(async () => {
              await api.resolveDiningProblem(modal.order.id);
              setTab("open");
              report("Hisob Ochiq bo‘limiga qaytdi ✅");
            })
          }
        />
      ) : null}

      {modal?.kind === "finalize" ? (
        <ConfirmModal
          text="Hisob yakunlansin va stol bo‘shatilsinmi?"
          okText="Yakunlash"
          busy={busy}
          onClose={() => setModal(null)}
          onConfirm={() =>
            void run(async () => {
              await api.finalizeDiningOrder(modal.order.id);
              report("Hisob yakunlandi, stol bo‘shadi ✅");
            })
          }
        />
      ) : null}
    </div>
  );
}
