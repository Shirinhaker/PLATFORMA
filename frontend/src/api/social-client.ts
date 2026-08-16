import type { ApiTransport } from "./http";
import type {
  AccountType,
  ActionNotificationListRead,
  ManagedStoryRead,
  MessageConversationRead,
  MessageCreate,
  MessageImageCreate,
  MessageRead,
  MessageThreadRead,
  NotificationFilterRead,
  NotificationFilterWrite,
  NotificationListRead,
  NotificationPreference,
  PushDeviceWrite,
  PushStatusRead,
  ReviewListRead,
  ReviewMutationRead,
  ReviewRead,
  ReviewTargetKind,
  ReviewWrite,
  StoryCreate,
  StoryCreated,
  StoryGroup,
  StoryRead,
  StoryViewer,
  StoryViewResult,
} from "./types";

export function createSocialClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  return {
    getStoryFeed(params: { lat?: number; lng?: number } = {}): Promise<StoryGroup[]> {
      const query = new URLSearchParams();
      if (params.lat !== undefined) query.set("lat", String(params.lat));
      if (params.lng !== undefined) query.set("lng", String(params.lng));
      const suffix = query.size ? `?${query.toString()}` : "";
      return request("GET", `/api/v1/stories/feed${suffix}`);
    },

    getMyStories(
      state: "active" | "archived" | "all" = "all",
    ): Promise<ManagedStoryRead[]> {
      return request("GET", `/api/v1/stories/mine?state=${state}`, undefined, true);
    },

    getOwnerStories(kind: "user" | "business", publicId: string): Promise<StoryRead[]> {
      return request(
        "GET",
        `/api/v1/stories/owner/${kind}/${encodeURIComponent(publicId)}`,
      );
    },

    createStory(body: StoryCreate): Promise<StoryCreated> {
      return request("POST", "/api/v1/stories", body, true);
    },

    recordStoryView(storyId: number): Promise<StoryViewResult> {
      return request("POST", `/api/v1/stories/${storyId}/view`, {}, true);
    },

    getStoryViewers(storyId: number): Promise<StoryViewer[]> {
      return request("GET", `/api/v1/stories/${storyId}/viewers`, undefined, true);
    },

    deleteStory(storyId: number): Promise<void> {
      return request("DELETE", `/api/v1/stories/${storyId}`, undefined, true);
    },

    reportStory(storyId: number, reason: string): Promise<{ ok: true }> {
      return request("POST", `/api/v1/stories/${storyId}/reports`, { reason }, true);
    },

    getMessageConversations(): Promise<MessageConversationRead[]> {
      return request("GET", "/api/v1/messages/conversations", undefined, true);
    },

    getMessageThread(kind: AccountType, publicId: string): Promise<MessageThreadRead> {
      return request(
        "GET",
        `/api/v1/messages/with/${kind}/${encodeURIComponent(publicId)}`,
        undefined,
        true,
      );
    },

    sendMessage(body: MessageCreate): Promise<MessageRead> {
      return request("POST", "/api/v1/messages/send", body, true);
    },

    sendMessageImage(body: MessageImageCreate): Promise<MessageRead> {
      return request("POST", "/api/v1/messages/image", body, true);
    },

    editMessage(messageId: number, text: string): Promise<MessageRead> {
      return request("PUT", `/api/v1/messages/${messageId}`, { text }, true);
    },

    deleteMessage(messageId: number): Promise<MessageRead> {
      return request("DELETE", `/api/v1/messages/${messageId}`, undefined, true);
    },

    getMessageUnreadCount(): Promise<{ count: number }> {
      return request("GET", "/api/v1/messages/unread-count", undefined, true);
    },

    getReviews(
      targetKind: ReviewTargetKind,
      targetPublicId: string,
    ): Promise<ReviewListRead> {
      return request(
        "GET",
        `/api/v1/reviews/${targetKind}/${encodeURIComponent(targetPublicId)}`,
      );
    },

    saveReview(body: ReviewWrite): Promise<ReviewMutationRead> {
      return request("POST", "/api/v1/reviews", body, true);
    },

    deleteReview(
      targetKind: ReviewTargetKind,
      targetPublicId: string,
    ): Promise<ReviewMutationRead> {
      return request(
        "DELETE",
        `/api/v1/reviews/${targetKind}/${encodeURIComponent(targetPublicId)}`,
        undefined,
        true,
      );
    },

    getReceivedReviews(): Promise<ReviewListRead> {
      return request("GET", "/api/v1/reviews/received", undefined, true);
    },

    replyToReview(reviewId: number, reply: string): Promise<ReviewRead> {
      return request("PUT", `/api/v1/reviews/${reviewId}/reply`, { reply }, true);
    },

    getNotifications(): Promise<NotificationListRead> {
      return request("GET", "/api/v1/notifications", undefined, true);
    },

    getActionNotifications(): Promise<ActionNotificationListRead> {
      return request("GET", "/api/v1/notifications/actions", undefined, true);
    },

    markNotificationRead(
      notificationId: number,
    ): Promise<{ ok: true; read_at: number }> {
      return request("PUT", `/api/v1/notifications/${notificationId}/read`, {}, true);
    },

    markAllNotificationsRead(): Promise<{ ok: true; read_at: number }> {
      return request("PUT", "/api/v1/notifications/read-all", {}, true);
    },

    getNotificationPreference(): Promise<NotificationPreference> {
      return request("GET", "/api/v1/notifications/preferences", undefined, true);
    },

    saveNotificationPreference(
      body: NotificationPreference,
    ): Promise<NotificationPreference> {
      return request("PUT", "/api/v1/notifications/preferences", body, true);
    },

    getNotificationFilters(): Promise<NotificationFilterRead[]> {
      return request("GET", "/api/v1/notifications/filters", undefined, true);
    },

    createNotificationFilter(
      body: NotificationFilterWrite,
    ): Promise<NotificationFilterRead> {
      return request("POST", "/api/v1/notifications/filters", body, true);
    },

    deleteNotificationFilter(filterId: number): Promise<{ ok: true }> {
      return request(
        "DELETE",
        `/api/v1/notifications/filters/${filterId}`,
        undefined,
        true,
      );
    },

    getPushStatus(): Promise<PushStatusRead> {
      return request("GET", "/api/v1/notifications/push-status", undefined, true);
    },

    registerPushDevice(
      body: PushDeviceWrite,
    ): Promise<{ ok: true; device_id: number }> {
      return request("POST", "/api/v1/notifications/devices", body, true);
    },

    unregisterPushDevice(token: string): Promise<{ ok: true }> {
      return request("DELETE", "/api/v1/notifications/devices", { token }, true);
    },

    recordAdvertisementViews(publicIds: string[]): Promise<void> {
      return request("POST", "/api/v1/public/advertisements/views", {
        ids: publicIds,
      });
    },

    recordAdvertisementClick(publicId: string): Promise<void> {
      return request(
        "POST",
        `/api/v1/public/advertisements/${encodeURIComponent(publicId)}/click`,
      );
    },
  };
}

export type SocialClient = ReturnType<typeof createSocialClient>;
