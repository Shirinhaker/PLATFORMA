import { useEffect, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type { NotificationRead } from "../api/types";

type Props = {
  api: Pick<ApiClient, "getActionNotifications" | "markNotificationRead">;
  onOpenNotification?: (notification: NotificationRead) => void | Promise<void>;
};

export function ActionNotifications({ api, onOpenNotification }: Props) {
  const [current, setCurrent] = useState<NotificationRead | null>(null);
  const dismissed = useRef(new Set<number>());

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const result = await api.getActionNotifications();
        if (!active) return;
        const next =
          result.items.find((item) => !dismissed.current.has(item.id)) ?? null;
        setCurrent(next);
        if (next && next.id !== current?.id) {
          try {
            navigator.vibrate?.(120);
          } catch {
            /* Qurilma vibratsiyani qo‘llamasligi mumkin. */
          }
        }
      } catch {
        if (active) setCurrent(null);
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [api, current?.id]);

  if (!current) return null;
  return (
    <div className="action-notification-v1656" role="status" aria-live="polite">
      <button
        type="button"
        className="action-notification-v1656__open"
        onClick={async () => {
          await api.markNotificationRead(current.id);
          setCurrent(null);
          await onOpenNotification?.(current);
        }}
      >
        <strong>🔔 {current.title}</strong>
        <span>{current.body || "Amalni bajarish uchun bosing."}</span>
      </button>
      <button
        type="button"
        className="action-notification-v1656__close"
        aria-label="Yopish"
        onClick={() => {
          dismissed.current.add(current.id);
          setCurrent(null);
        }}
      >
        ×
      </button>
    </div>
  );
}
