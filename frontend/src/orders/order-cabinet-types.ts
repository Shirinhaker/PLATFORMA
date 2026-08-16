import type { ReactNode } from "react";

import type { ApiClient } from "../api/client";

export type OrdersApi = Pick<
  ApiClient,
  | "getMyOrders"
  | "getOrderInbox"
  | "markOrderSeen"
  | "changeOrderStatus"
  | "submitOrderPayment"
  | "decideOrderPayment"
  | "openOrderProblem"
  | "chooseOrderProblemSolution"
  | "handoffOrder"
  | "receiveOrder"
  | "getOrderChat"
  | "sendOrderChatMessage"
  | "sendOrderChatImage"
  | "editOrderChatMessage"
  | "deleteOrderChatMessage"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "getDebtors"
  | "createDebtor"
>;

export type OrdersCabinetProps = {
  api: OrdersApi;
  side: "customer" | "provider";
  category: "product" | "service";
  onBack(): void;
  onUnreadChange?(count: number): void;
  initialOrderId?: number | null;
  beforeList?: ReactNode;
};

export type OrdersTab = "active" | "problem" | "done";

export type OrderConfirmation =
  "handoff" | "received" | "delete-message" | "payment-confirm" | null;
