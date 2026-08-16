// `BusinessOnlineScreen.tsx` dan ajratildi.
import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  PaymentRequestModal,
  type PaymentRequestApi,
  type PaymentTarget,
} from "../PaymentRequestModal";

import type { ApiClient } from "../../api/client";
import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import type {
  BusinessProfile,
  NotificationRead,
  PaymentCatalog,
} from "../../api/types";
import { OwnerListings, type OwnerListingsApi } from "../../listings/OwnerListings";
import { BusinessDiningView } from "../BusinessDiningView";
import {
  BusinessAdvertisements,
  supportsAdvertisementApi,
} from "../../advertisements/BusinessAdvertisements";
import { BusinessDining, supportsDiningApi } from "../../dining/BusinessDining";
import {
  BusinessKitchen,
  supportsDiningKitchenApi,
} from "../../dining/BusinessKitchen";
import { OrdersCabinet, type OrdersApi } from "../../orders/OrdersCabinet";
import { BusinessEducationEnrollmentsView } from "../BusinessEducationEnrollmentsView";
import {
  BusinessMedicalProvidersView,
  BusinessMedicalQueueView,
} from "../BusinessMedicalView";
import { BusinessQueue, supportsBusinessQueueApi } from "../../queues/BusinessQueue";
import { CrudEditorView, ItemsEditorView } from "../BusinessOnlineEditingViews";
import {
  isServiceOrder,
  MessagesView,
  NotificationsView,
  type OrderFilter,
  OrdersView,
  PaymentsView,
  PeopleView,
  recordId,
  recordText,
  ReviewsView,
  type SharedActions,
  SubscriptionsView,
} from "../BusinessOnlineViews";
import { OwnerStories, type OwnerStoriesApi } from "../../stories/OwnerStories";
import { ReceivedReviews, type ReceivedReviewsApi } from "../../reviews/Reviews";
import {
  Notifications,
  type NotificationsApi,
} from "../../notifications/Notifications";
import "../BusinessOnlineScreen.css";
import "../BusinessExistingOnline.css";
import { RenderContext, supportsOwnerListings } from "./shared";

export function renderContent(context: RenderContext): ReactNode {
  const { view, items, groups, profile, shared } = context;

  switch (view) {
    case "subscriptions":
      return (
        <SubscriptionsView
          rows={items}
          duration={context.duration}
          setDuration={context.setDuration}
          busy={shared.busy}
          openPayment={context.openPayment}
        />
      );
    case "payments":
      return (
        <PaymentsView
          rows={items}
          loading={context.loading}
          refresh={() => void context.refresh("subscription_payments")}
          resubmit={async (id, file) => {
            await shared.action("subscription_payments", "resubmit", id, {
              receipt_name: file.name,
              receipt_type: file.type,
              receipt_size: file.size,
            });
          }}
        />
      );
    case "items":
      return (
        <ItemsEditorView
          {...shared}
          rows={items}
          groups={groups}
          query={context.query}
          setQuery={context.setQuery}
          kind={context.kind}
          setKind={context.setKind}
          direction={profile.direction}
          uploadItemImage={context.uploadItemImage}
        />
      );
    case "dining-kitchen":
      if (supportsDiningKitchenApi(context.api)) {
        return (
          <BusinessKitchen
            api={context.api}
            // Bo'limning o'zi `kitchen` vakolati bilan ochiladi
            // (`MENU_PERMISSIONS`), server ham qayta tekshiradi.
            permissions={null}
            onBackHandlerChange={context.setSubscreenBack}
          />
        );
      }
      return null;
    case "dining-places":
      if (supportsDiningApi(context.api)) {
        return (
          <BusinessDining
            api={context.api}
            menuItems={context.resources.items ?? []}
            groups={context.resources.item_groups ?? []}
            onBackHandlerChange={context.setSubscreenBack}
          />
        );
      }
      return (
        <BusinessDiningView
          places={context.resources.dining_places ?? []}
          menuItems={context.resources.items ?? []}
          groups={context.resources.item_groups ?? []}
          busy={shared.busy}
          createPlace={(record) => context.create("dining_places", record)}
          patchPlace={(id, patch) => context.patch("dining_places", id, patch)}
          removePlace={(id) => context.remove("dining_places", id)}
          action={context.action}
          refresh={context.refresh}
          onBackHandlerChange={context.setSubscreenBack}
        />
      );
    case "medical-providers":
      if (supportsBusinessQueueApi(context.api)) {
        return (
          <BusinessQueue
            api={context.api}
            direction={profile.direction}
            view="medical-providers"
            onBackHandlerChange={context.setSubscreenBack}
          />
        );
      }
      return (
        <BusinessMedicalProvidersView
          direction={profile.direction}
          doctors={context.resources.medical_doctors ?? []}
          staff={context.resources.medical_staff ?? []}
          items={context.resources.items ?? []}
          busy={shared.busy}
          loading={context.loading}
          createDoctor={(record) => context.create("medical_doctors", record)}
          patchDoctor={(id, patch) => context.patch("medical_doctors", id, patch)}
          onBackHandlerChange={context.setSubscreenBack}
        />
      );
    case "medical-queue":
      if (supportsBusinessQueueApi(context.api)) {
        return (
          <BusinessQueue
            api={context.api}
            direction={profile.direction}
            view="medical-queue"
            onBackHandlerChange={context.setSubscreenBack}
          />
        );
      }
      return (
        <BusinessMedicalQueueView
          direction={profile.direction}
          rows={context.resources.medical_queue ?? []}
          doctors={context.resources.medical_doctors ?? []}
          staff={context.resources.medical_staff ?? []}
          items={context.resources.items ?? []}
          busy={shared.busy}
          loading={context.loading}
          createDoctor={(record) => context.create("medical_doctors", record)}
          patchDoctor={(id, patch) => context.patch("medical_doctors", id, patch)}
          createOffline={async (input) =>
            context.action("medical_queue", "offline_add", undefined, {
              patient_name: input.patientName,
              phone: input.phone,
              item_id: Number(input.itemId),
              staff_id: Number(input.providerId),
              queue_date: input.queueDate,
            })
          }
          changeStatus={async (id, status) =>
            Boolean(await context.action("medical_queue", "set_status", id, { status }))
          }
          swapQueues={async (first, second) =>
            Boolean(
              await context.action("medical_queue", "swap", Number(first), {
                other_queue_id: Number(second),
              }),
            )
          }
          loadDate={async () => context.refresh("medical_queue")}
          onBackHandlerChange={context.setSubscreenBack}
        />
      );
    case "education-enrollments":
      return (
        <BusinessEducationEnrollmentsView
          rows={context.resources.education_enrollments ?? []}
          groups={context.resources.education_groups ?? []}
          busy={shared.busy}
          loading={context.loading}
          action={context.action}
          refresh={context.refresh}
        />
      );
    case "listings":
      if (supportsOwnerListings(context.api)) {
        return (
          <OwnerListings
            actor="business"
            api={context.api}
            embedded
            onBack={() => undefined}
            onOpenAdvertisements={() => context.onViewChange?.("advertisements")}
          />
        );
      }
      return (
        <CrudEditorView
          {...shared}
          resource="listings"
          rows={items}
          addLabel="+ E’lon"
          empty="Hozircha e’lon yo‘q."
          fields={["title", "description", "price", "category"]}
          onPromotionChange={context.onViewChange}
        />
      );
    case "orders":
    case "service-orders":
      return (
        <OrdersView
          rows={items.filter(
            (row) => isServiceOrder(row) === (view === "service-orders"),
          )}
          filter={context.orderFilter}
          setFilter={context.setOrderFilter}
          busy={shared.busy}
          setStatus={(id, status) =>
            shared.action("orders", "set_status", id, { status })
          }
          action={(id, name, payload) => shared.action("orders", name, id, payload)}
        />
      );
    case "messages":
      return (
        <MessagesView
          rows={items}
          value={context.messageText}
          setValue={context.setMessageText}
          busy={shared.busy}
          send={async (peer, value, replyToId) => {
            if (context.hasActionApi) {
              await shared.action("messages", "send", undefined, {
                text: value,
                receiver_id: Number(peer.id),
                receiver_kind: peer.kind,
                ...(replyToId === undefined ? {} : { reply_to_id: replyToId }),
              });
            } else {
              await shared.create("messages", {
                text: value,
                sender_kind: "business",
                receiver_id: Number(peer.id),
                receiver_kind: peer.kind,
                ...(replyToId === undefined ? {} : { reply_to_id: replyToId }),
              });
            }
            context.setMessageText("");
          }}
          edit={async (id, text) => {
            await shared.patch("messages", id, {
              text,
              edited_at: Math.floor(Date.now() / 1000),
            });
          }}
          remove={async (id) => {
            await shared.action("messages", "delete", id);
          }}
        />
      );
    case "reviews":
      return (
        <ReviewsView
          rows={items}
          ratingSum={profile.rating_sum}
          ratingCount={profile.rating_count}
          replyId={context.replyId}
          reply={context.replyText}
          setReplyId={context.setReplyId}
          setReply={context.setReplyText}
          busy={shared.busy}
          save={async (id, reply) => {
            await shared.action("business_reviews", "reply", id, {
              reply,
            });
            context.setReplyId(null);
            context.setReplyText("");
          }}
        />
      );
    case "advertisements":
      if (supportsAdvertisementApi(context.api)) {
        return (
          <BusinessAdvertisements
            api={context.api}
            openPayment={context.openPaymentTarget}
            onOpenListings={() => context.onViewChange?.("listings")}
          />
        );
      }
      return (
        <CrudEditorView
          {...shared}
          resource="advertisements"
          rows={items}
          addLabel="+ Reklama"
          empty="Hozircha reklama yo‘q."
          fields={[
            "title",
            "caption",
            "placement",
            "region",
            "district",
            "start_at",
            "end_at",
          ]}
          quoteAdvertisement={
            context.hasActionApi
              ? (request) =>
                  context.action(
                    "advertisements",
                    "calculate_price",
                    undefined,
                    request,
                  )
              : undefined
          }
          onPromotionChange={context.onViewChange}
        />
      );
    case "stories":
      return (
        <CrudEditorView
          {...shared}
          resource="stories"
          rows={items}
          addLabel="+ Istoriya"
          empty="Hozircha istoriya yo‘q."
          fields={["caption", "media_type", "media_url"]}
          extraAction={(row, index) => (
            <button
              type="button"
              disabled={shared.busy}
              onClick={() =>
                void shared.action("stories", "archive", recordId(row, index))
              }
            >
              Arxivlash
            </button>
          )}
        />
      );
    case "notifications":
      return (
        <NotificationsView
          rows={items}
          filters={context.resources.notify_filters ?? []}
          pushPreference={(context.resources.push_preferences ?? [])[0]}
          busy={shared.busy}
          markAll={() => shared.action("notifications", "mark_all_read")}
          markOne={(id) => shared.action("notifications", "mark_read", id)}
          createFilter={(record) => shared.create("notify_filters", record)}
          removeFilter={(id) => shared.remove("notify_filters", id)}
          savePushPreference={async (enabled) => {
            await context.action("notifications", "set_push_preferences", undefined, {
              enabled,
              orders_enabled: enabled,
            });
          }}
          onOpenOrder={context.onOpenOrder}
        />
      );
    case "followers":
      return <PeopleView kind="followers" rows={items} busy={shared.busy} />;
    case "following":
      return <PeopleView kind="following" rows={items} busy={shared.busy} />;
    default:
      return <div className="business-online__empty">Bo‘lim topilmadi.</div>;
  }
}
