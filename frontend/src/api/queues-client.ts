import type { ApiTransport } from "./http";
import type {
  BusinessQueueEntry,
  BusinessQueueOfflineCreate,
  BusinessQueueProvider,
  BusinessQueueProviderWrite,
  BusinessQueueSetup,
  QueueCreate,
  QueueEntryStatus,
  QueueNotificationRead,
  QueueOptions,
  QueueSlots,
} from "./types";

export function createQueuesClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  return {
    getQueueOptions(
      businessPublicId: string,
      itemPublicId: string,
      queueDate: string,
    ): Promise<QueueOptions> {
      const query = new URLSearchParams({
        business_public_id: businessPublicId,
        item_public_id: itemPublicId,
        queue_date: queueDate,
      });
      return request("GET", `/api/v1/queues/options?${query.toString()}`);
    },

    getQueueSlots(
      businessPublicId: string,
      itemPublicId: string,
      providerId: number,
      queueDate: string,
    ): Promise<QueueSlots> {
      const query = new URLSearchParams({
        business_public_id: businessPublicId,
        item_public_id: itemPublicId,
        provider_id: String(providerId),
        queue_date: queueDate,
      });
      return request("GET", `/api/v1/queues/slots?${query.toString()}`);
    },

    createQueue(body: QueueCreate): Promise<BusinessQueueEntry> {
      return request("POST", "/api/v1/queues", body, true);
    },

    getMyQueues(): Promise<BusinessQueueEntry[]> {
      return request("GET", "/api/v1/queues/mine", undefined, true);
    },

    cancelMyQueue(queueId: number): Promise<BusinessQueueEntry> {
      return request("POST", `/api/v1/queues/${queueId}/cancel`, undefined, true);
    },

    markQueueNotificationRead(notificationId: number): Promise<QueueNotificationRead> {
      return request(
        "POST",
        `/api/v1/queues/notifications/${notificationId}/read`,
        undefined,
        true,
      );
    },

    getBusinessQueueSetup(): Promise<BusinessQueueSetup> {
      return request("GET", "/api/v1/queues/business/setup", undefined, true);
    },

    getBusinessQueueProviders(): Promise<BusinessQueueProvider[]> {
      return request("GET", "/api/v1/queues/business/providers", undefined, true);
    },

    createBusinessQueueProvider(
      body: BusinessQueueProviderWrite,
    ): Promise<BusinessQueueProvider> {
      return request("POST", "/api/v1/queues/business/providers", body, true);
    },

    updateBusinessQueueProvider(
      providerId: number,
      body: BusinessQueueProviderWrite,
    ): Promise<BusinessQueueProvider> {
      return request(
        "PUT",
        `/api/v1/queues/business/providers/${providerId}`,
        body,
        true,
      );
    },

    getBusinessQueueEntries(queueDate: string): Promise<BusinessQueueEntry[]> {
      const query = new URLSearchParams({ queue_date: queueDate });
      return request(
        "GET",
        `/api/v1/queues/business/entries?${query.toString()}`,
        undefined,
        true,
      );
    },

    createBusinessOfflineQueue(
      body: BusinessQueueOfflineCreate,
    ): Promise<BusinessQueueEntry> {
      return request("POST", "/api/v1/queues/business/entries", body, true);
    },

    changeBusinessQueueStatus(
      queueId: number,
      status: QueueEntryStatus,
    ): Promise<BusinessQueueEntry> {
      return request(
        "PUT",
        `/api/v1/queues/business/entries/${queueId}/status`,
        { status },
        true,
      );
    },

    swapBusinessQueues(
      queueId: number,
      otherQueueId: number,
    ): Promise<BusinessQueueEntry> {
      return request(
        "POST",
        `/api/v1/queues/business/entries/${queueId}/swap`,
        { other_queue_id: otherQueueId },
        true,
      );
    },
  };
}

export type QueuesClient = ReturnType<typeof createQueuesClient>;
