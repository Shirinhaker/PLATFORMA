import type { ApiTransport } from "./http";
import type {
  DiningBookingBody,
  DiningCashierLine,
  DiningItemInput,
  DiningOrder,
  DiningOrderBody,
  DiningPaymentBody,
  DiningPaymentResult,
  DiningPlace,
  DiningPlaceMove,
  DiningPlaceWrite,
} from "./types";

export function createDiningClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  return {
    getDiningPlaces(): Promise<DiningPlace[]> {
      return request("GET", "/api/v1/dining/places", undefined, true);
    },

    createDiningPlace(body: DiningPlaceWrite): Promise<DiningPlace> {
      return request("POST", "/api/v1/dining/places", body, true);
    },

    updateDiningPlace(placeId: number, body: DiningPlaceWrite): Promise<DiningPlace> {
      return request("PUT", `/api/v1/dining/places/${placeId}`, body, true);
    },

    moveDiningPlace(placeId: number, body: DiningPlaceMove): Promise<DiningPlace> {
      return request("PUT", `/api/v1/dining/places/${placeId}/position`, body, true);
    },

    deleteDiningPlace(placeId: number): Promise<void> {
      return request("DELETE", `/api/v1/dining/places/${placeId}`, undefined, true);
    },

    clearDiningPlace(placeId: number): Promise<void> {
      return request("POST", `/api/v1/dining/places/${placeId}/clear`, undefined, true);
    },

    bookDiningPlace(placeId: number, body: DiningBookingBody): Promise<DiningOrder> {
      return request("POST", `/api/v1/dining/places/${placeId}/booking`, body, true);
    },

    createDiningOrder(placeId: number, body: DiningOrderBody): Promise<DiningOrder> {
      return request("POST", `/api/v1/dining/places/${placeId}/order`, body, true);
    },

    getDiningOrders(): Promise<DiningOrder[]> {
      return request("GET", "/api/v1/dining/orders", undefined, true);
    },

    addDiningOrderItems(
      orderId: number,
      items: DiningItemInput[],
    ): Promise<DiningOrder> {
      return request("POST", `/api/v1/dining/orders/${orderId}/items`, { items }, true);
    },

    setDiningKitchenStatus(
      orderId: number,
      status: "preparing" | "done",
    ): Promise<DiningOrder> {
      return request(
        "PUT",
        `/api/v1/dining/orders/${orderId}/kitchen`,
        { status },
        true,
      );
    },

    confirmDiningPayment(
      orderId: number,
      body: DiningPaymentBody,
    ): Promise<DiningPaymentResult> {
      return request("POST", `/api/v1/dining/orders/${orderId}/payment`, body, true);
    },

    updateDiningCashierItems(
      orderId: number,
      items: DiningCashierLine[],
    ): Promise<DiningOrder> {
      return request(
        "PUT",
        `/api/v1/dining/orders/${orderId}/cashier-items`,
        { items },
        true,
      );
    },

    finalizeDiningOrder(orderId: number): Promise<DiningOrder> {
      return request(
        "POST",
        `/api/v1/dining/orders/${orderId}/finalize`,
        undefined,
        true,
      );
    },

    cancelDiningOrder(orderId: number, reason: string): Promise<DiningOrder> {
      return request(
        "POST",
        `/api/v1/dining/orders/${orderId}/cancel`,
        { reason },
        true,
      );
    },

    openDiningProblem(
      orderId: number,
      body: { reason: string; note: string },
    ): Promise<DiningOrder> {
      return request("POST", `/api/v1/dining/orders/${orderId}/problem`, body, true);
    },

    // --- Reklama joylash (K14) ---,

    resolveDiningProblem(orderId: number): Promise<DiningOrder> {
      return request(
        "POST",
        `/api/v1/dining/orders/${orderId}/problem/resolve`,
        undefined,
        true,
      );
    },
  };
}

export type DiningClient = ReturnType<typeof createDiningClient>;
