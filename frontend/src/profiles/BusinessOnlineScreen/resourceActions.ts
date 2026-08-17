import type { Dispatch, SetStateAction } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { recordId, recordText } from "../BusinessOnlineViews";
import { nextLocalId, type OnlineApi, type ResourceState } from "./shared";

type ResourceActionsOptions = {
  api: OnlineApi;
  resources: ResourceState;
  items: BusinessOnlineRecord[];
  setResources: Dispatch<SetStateAction<ResourceState>>;
  setBusy: Dispatch<SetStateAction<boolean>>;
  setError: Dispatch<SetStateAction<string>>;
  setNotice: Dispatch<SetStateAction<string>>;
  setForm: Dispatch<SetStateAction<string | null>>;
  setDraft: Dispatch<SetStateAction<BusinessOnlineRecord>>;
};

export function createBusinessOnlineResourceActions({
  api,
  resources,
  items,
  setResources,
  setBusy,
  setError,
  setNotice,
  setForm,
  setDraft,
}: ResourceActionsOptions) {
  function setResource(resource: BusinessOnlineResource, rows: BusinessOnlineRecord[]) {
    setResources((current) => ({ ...current, [resource]: rows }));
  }

  async function create(
    resource: BusinessOnlineResource,
    record: BusinessOnlineRecord,
  ): Promise<boolean> {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (api.createBusinessOnlineRecord) {
        const result = await api.createBusinessOnlineRecord(resource, record);
        setResource(resource, result.items);
      } else {
        const current = resources[resource] ?? [];
        setResource(resource, [
          ...current,
          {
            ...record,
            id: nextLocalId(current),
            created_at: Math.floor(Date.now() / 1000),
          },
        ]);
      }
      setForm(null);
      setDraft({});
      if (
        !resource.startsWith("dining_") &&
        !resource.startsWith("medical_") &&
        !resource.startsWith("education_")
      ) {
        setNotice("Saqlandi");
      }
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yozuv saqlanmadi.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function patch(
    resource: BusinessOnlineResource,
    id: number | string,
    value: BusinessOnlineRecord,
  ): Promise<boolean> {
    setBusy(true);
    setError("");
    try {
      if (api.patchBusinessOnlineRecord) {
        const result = await api.patchBusinessOnlineRecord(resource, id, value);
        setResource(resource, result.items);
      } else {
        setResource(
          resource,
          (resources[resource] ?? []).map((row, index) =>
            String(recordId(row, index)) === String(id) ? { ...row, ...value } : row,
          ),
        );
      }
      if (
        !resource.startsWith("dining_") &&
        !resource.startsWith("medical_") &&
        !resource.startsWith("education_")
      ) {
        setNotice("Yangilandi");
      }
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yozuv yangilanmadi.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function remove(
    resource: BusinessOnlineResource,
    id: number | string,
  ): Promise<boolean> {
    setBusy(true);
    setError("");
    try {
      if (api.deleteBusinessOnlineRecord) {
        const result = await api.deleteBusinessOnlineRecord(resource, id);
        setResource(resource, result.items);
      } else {
        setResource(
          resource,
          (resources[resource] ?? []).filter(
            (row, index) => String(recordId(row, index)) !== String(id),
          ),
        );
      }
      if (
        !resource.startsWith("dining_") &&
        !resource.startsWith("medical_") &&
        !resource.startsWith("education_")
      ) {
        setNotice("O‘chirildi");
      }
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yozuv o‘chirilmadi.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function action(
    resource: BusinessOnlineResource,
    name: string,
    recordIdValue?: number | string,
    payload: BusinessOnlineRecord = {},
  ): Promise<BusinessOnlineRecord | null> {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (api.applyBusinessOnlineAction) {
        const result = await api.applyBusinessOnlineAction(resource, name, {
          record_id: recordIdValue,
          payload,
        });
        if (resource === "advertisements" && name === "calculate_price") {
          return result.item;
        }
        setResource(resource, result.items);
        if (
          resource === "notifications" &&
          name === "set_push_preferences" &&
          result.item
        ) {
          setResource("push_preferences", [result.item]);
        }
        if (
          !resource.startsWith("dining_") &&
          !resource.startsWith("medical_") &&
          !resource.startsWith("education_")
        ) {
          setNotice(
            resource === "notifications" && name === "set_push_preferences"
              ? payload.enabled
                ? "Push notification yoqildi ✅"
                : "Push notification o'chirildi"
              : "Amal bajarildi",
          );
        }
        return result.item;
      } else if (resource === "notifications" && name === "mark_all_read") {
        setResource(
          resource,
          items.map((row) => ({ ...row, is_read: 1 })),
        );
      } else if (resource === "notifications" && name === "set_push_preferences") {
        const preference = {
          id: 1,
          enabled: payload.enabled ? 1 : 0,
          orders_enabled: payload.orders_enabled ? 1 : 0,
        };
        setResource("push_preferences", [preference]);
        if (
          !resource.startsWith("dining_") &&
          !resource.startsWith("medical_") &&
          !resource.startsWith("education_")
        ) {
          setNotice(
            payload.enabled
              ? "Push notification yoqildi ✅"
              : "Push notification o'chirildi",
          );
        }
        return preference;
      } else if (
        resource === "subscription_payments" &&
        name === "resubmit" &&
        recordIdValue !== undefined
      ) {
        setResource(
          resource,
          items.map((row, index) =>
            String(recordId(row, index)) === String(recordIdValue)
              ? { ...row, status: "pending", reason: "" }
              : row,
          ),
        );
      } else if (
        resource === "orders" &&
        name === "report_problem" &&
        recordIdValue !== undefined
      ) {
        setResource(
          resource,
          items.map((row, index) =>
            String(recordId(row, index)) === String(recordIdValue)
              ? {
                  ...row,
                  problem_open: 1,
                  problem_reason: payload.reason,
                  problem_note: payload.note,
                }
              : row,
          ),
        );
      } else if (
        resource === "messages" &&
        name === "delete" &&
        recordIdValue !== undefined
      ) {
        setResource(
          resource,
          items.map((row, index) =>
            String(recordId(row, index)) === String(recordIdValue)
              ? {
                  ...row,
                  is_deleted: 1,
                  deleted_at: Math.floor(Date.now() / 1000),
                }
              : row,
          ),
        );
      } else if (
        resource === "orders" &&
        name === "handoff" &&
        recordIdValue !== undefined
      ) {
        setResource(
          resource,
          items.map((row, index) =>
            String(recordId(row, index)) === String(recordIdValue)
              ? {
                  ...row,
                  status:
                    recordText(row, "order_type") === "pickup" ||
                    ["ready", "tayyor"].includes(recordText(row, "status"))
                      ? "pickup_waiting_customer"
                      : "in_delivery",
                }
              : row,
          ),
        );
      } else if (
        resource === "following" &&
        name === "unfollow" &&
        recordIdValue !== undefined
      ) {
        setResource(
          resource,
          items.filter(
            (row, index) => String(recordId(row, index)) !== String(recordIdValue),
          ),
        );
      } else if (
        resource === "business_reviews" &&
        name === "reply" &&
        recordIdValue !== undefined
      ) {
        setResource(
          resource,
          items.map((row, index) =>
            String(recordId(row, index)) === String(recordIdValue)
              ? { ...row, business_reply: payload.reply }
              : row,
          ),
        );
      } else if (name === "set_status" && recordIdValue !== undefined) {
        setResource(
          resource,
          items.map((row, index) =>
            String(recordId(row, index)) === String(recordIdValue)
              ? { ...row, status: payload.status }
              : row,
          ),
        );
      } else if (
        resource === "stories" &&
        name === "archive" &&
        recordIdValue !== undefined
      ) {
        setResource(
          resource,
          items.map((row, index) =>
            String(recordId(row, index)) === String(recordIdValue)
              ? { ...row, status: "archived" }
              : row,
          ),
        );
      }
      if (
        !resource.startsWith("dining_") &&
        !resource.startsWith("medical_") &&
        !resource.startsWith("education_")
      ) {
        setNotice(
          resource === "notifications" && name === "set_push_preferences"
            ? payload.enabled
              ? "Push notification yoqildi ✅"
              : "Push notification o'chirildi"
            : "Amal bajarildi",
        );
      }
      return {};
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Amal bajarilmadi.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  return { create, patch, remove, action };
}
