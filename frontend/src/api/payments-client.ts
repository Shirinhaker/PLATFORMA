// Tarif katalogi, to'lov arizalari va obuna.
//
// `client.ts` dan ajratildi. Chaqiruv joylari o'zgarmadi: `ApiClient`
// bu obyektni `Object.assign` bilan o'ziga qo'shadi.

import { ApiTransport } from "./http";
import type {
  BusinessSubscriptionSummary,
  PaymentCatalog,
  PaymentReceiptRef,
  PaymentRequestBody,
  PaymentRequestRecord,
} from "./types";

export function createPaymentsClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  return {
    getPaymentCatalog(): Promise<PaymentCatalog> {
      return request("GET", "/api/v1/payments/catalog", undefined, true);
    },

    createPaymentRequest(body: PaymentRequestBody): Promise<PaymentRequestRecord> {
      return request("POST", "/api/v1/payments/requests", body, true);
    },

    getMyPayments(): Promise<PaymentRequestRecord[]> {
      return request("GET", "/api/v1/payments/my", undefined, true);
    },

    resubmitPayment(
      paymentId: number,
      receipt: PaymentReceiptRef,
    ): Promise<PaymentRequestRecord> {
      return request(
        "POST",
        `/api/v1/payments/${paymentId}/resubmit`,
        { receipt },
        true,
      );
    },

    getBusinessSubscription(): Promise<BusinessSubscriptionSummary> {
      return request("GET", "/api/v1/payments/subscription", undefined, true);
    },
  };
}

export type PaymentsClient = ReturnType<typeof createPaymentsClient>;
