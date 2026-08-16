import type {
  OrderChatRead,
  OrderCreate,
  OrderCreateResponse,
  OrderMessageRead,
  OrderPaymentStatus,
  OrderProblemReason,
  OrderProblemSolution,
  OrderRead,
  OrderStatus,
} from "./types";
import type { ApiTransport } from "./http";

export function createOrdersClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  return {
    createOrder(body: OrderCreate): Promise<OrderCreateResponse> {
      return request("POST", "/api/v1/orders", body, true);
    },

    getMyOrders(): Promise<OrderRead[]> {
      return request("GET", "/api/v1/orders/my", undefined, true);
    },

    getOrderInbox(): Promise<OrderRead[]> {
      return request("GET", "/api/v1/orders/inbox", undefined, true);
    },

    markOrderSeen(orderId: number): Promise<OrderRead> {
      return request("PUT", `/api/v1/orders/${orderId}/seen`, {}, true);
    },

    changeOrderStatus(orderId: number, status: OrderStatus): Promise<OrderRead> {
      return request("PUT", `/api/v1/orders/${orderId}/status`, { status }, true);
    },

    submitOrderPayment(orderId: number): Promise<OrderRead> {
      return request("POST", `/api/v1/orders/${orderId}/payment/submit`, {}, true);
    },

    decideOrderPayment(
      orderId: number,
      status: OrderPaymentStatus,
      debtorId: number | null = null,
    ): Promise<OrderRead> {
      return request(
        "POST",
        `/api/v1/orders/${orderId}/payment`,
        { status, ...(debtorId ? { debtor_id: debtorId } : {}) },
        true,
      );
    },

    openOrderProblem(
      orderId: number,
      body: { reason: OrderProblemReason; note: string },
    ): Promise<OrderRead> {
      return request("POST", `/api/v1/orders/${orderId}/problem`, body, true);
    },

    chooseOrderProblemSolution(
      orderId: number,
      solution: OrderProblemSolution,
    ): Promise<OrderRead> {
      return request(
        "PUT",
        `/api/v1/orders/${orderId}/problem/solution`,
        { solution },
        true,
      );
    },

    handoffOrder(orderId: number): Promise<OrderRead> {
      return request("POST", `/api/v1/orders/${orderId}/handoff`, {}, true);
    },

    receiveOrder(orderId: number): Promise<OrderRead> {
      return request("POST", `/api/v1/orders/${orderId}/received`, {}, true);
    },

    getOrderChat(orderId: number): Promise<OrderChatRead> {
      return request("GET", `/api/v1/orders/${orderId}/chat`, undefined, true);
    },

    sendOrderChatMessage(
      orderId: number,
      body: { text: string; reply_to_id: number | null },
    ): Promise<OrderMessageRead> {
      return request("POST", `/api/v1/orders/${orderId}/chat`, body, true);
    },

    sendOrderChatImage(
      orderId: number,
      body: {
        object_key: string;
        file_name: string;
        text?: string;
        reply_to_id?: number | null;
      },
    ): Promise<OrderMessageRead> {
      return request("POST", `/api/v1/orders/${orderId}/chat/image`, body, true);
    },

    editOrderChatMessage(
      orderId: number,
      messageId: number,
      text: string,
    ): Promise<OrderMessageRead> {
      return request(
        "PUT",
        `/api/v1/orders/${orderId}/chat/${messageId}`,
        { text },
        true,
      );
    },

    deleteOrderChatMessage(
      orderId: number,
      messageId: number,
    ): Promise<OrderMessageRead> {
      return request(
        "DELETE",
        `/api/v1/orders/${orderId}/chat/${messageId}`,
        undefined,
        true,
      );
    },
  };
}

export type OrdersClient = ReturnType<typeof createOrdersClient>;
