import { useEffect, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type { BusinessQueueEntry } from "../api/types";
import "./MyQueuesV1656.css";


export type MyQueuesApi = Pick<ApiClient, "getMyQueues" | "cancelMyQueue">;

type Props = {
  api: MyQueuesApi;
  focusQueueId?: number | null;
  onFocusHandled?(queueId: number): void;
};

const ACTIVE_STATUSES = new Set(["waiting", "called", "in_service"]);
const CANCELLABLE_STATUSES = new Set(["waiting", "called"]);


function statusText(status: string) {
  return ({
    waiting: "Kutilmoqda",
    called: "Chaqirildi",
    in_service: "Qabulda",
    done: "Yakunlandi",
    no_show: "Kelmadi",
    cancelled: "Bekor qilindi",
    skipped: "O‘tkazib yuborildi",
  } as Record<string, string>)[status] ?? status ?? "—";
}


function errorText(reason: unknown) {
  return reason instanceof Error ? reason.message : "Navbatlar yuklanmadi.";
}


export function MyQueuesV1656({
  api,
  focusQueueId = null,
  onFocusHandled,
}: Props) {
  const [rows, setRows] = useState<BusinessQueueEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [cancelTarget, setCancelTarget] = useState<BusinessQueueEntry | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [highlightedId, setHighlightedId] = useState(() => Number(focusQueueId || 0));
  const cards = useRef(new Map<number, HTMLDivElement>());

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api.getMyQueues()
      .then((value) => {
        if (active) setRows(value);
      })
      .catch((reason) => {
        if (active) setError(errorText(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);

  useEffect(() => {
    const queueId = Number(focusQueueId || 0);
    if (!queueId || loading) return;
    setHighlightedId(queueId);
    const card = cards.current.get(queueId);
    if (card && typeof card.scrollIntoView === "function") {
      card.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    onFocusHandled?.(queueId);
  }, [focusQueueId, loading, onFocusHandled, rows]);

  async function cancelQueue() {
    if (!cancelTarget) return;
    const queueId = cancelTarget.id;
    setBusyId(queueId);
    setError("");
    setNotice("");
    try {
      const updated = await api.cancelMyQueue(queueId);
      setRows((current) => current.map((row) => (
        row.id === updated.id ? updated : row
      )));
      setCancelTarget(null);
      setNotice("Navbat bekor qilindi.");
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="my-queues-v1656" aria-label="Mijoz navbatlari">
      <div className="my-queues-v1656__heading">
        <h2>📋 Navbatlar</h2>
        <span>{rows.length} ta</span>
      </div>
      {error ? <p className="my-queues-v1656__message" role="alert">{error}</p> : null}
      {notice ? <p className="my-queues-v1656__message" role="status">{notice}</p> : null}
      {loading ? (
        <div className="idesc">Yuklanmoqda...</div>
      ) : rows.length ? (
        <div className="my-queues-v1656__list">
          {rows.map((queue) => {
            const active = ACTIVE_STATUSES.has(queue.status);
            const medical = queue.business_direction === "Tibbiy xizmatlar";
            const focused = queue.id === highlightedId;
            return (
              <div
                className={`panel-card${focused ? " medical-queue-focus" : ""}`}
                data-testid={`medical-queue-${queue.id}`}
                key={queue.id}
                ref={(node) => {
                  if (node) cards.current.set(queue.id, node);
                  else cards.current.delete(queue.id);
                }}
              >
                <div className="my-queues-v1656__top">
                  <div>
                    <span className="order-no-pill">NAVBAT {queue.queue_code}</span>
                    <div className="iname">{queue.service_name || "Xizmat"}</div>
                    <div className="idesc">🏢 {queue.business_name || "Biznes"}</div>
                    <div className="idesc">
                      {medical ? "🩺" : "🧑‍💼"} {queue.provider_name || (
                        medical ? "Shifokor" : "Xizmat ko'rsatuvchi"
                      )}
                    </div>
                  </div>
                  <span className={`tx-amt${active ? " st-ok" : ""}`}>
                    {statusText(queue.status)}
                  </span>
                </div>
                <div className="my-queues-v1656__details">
                  <div className="idesc">📅 Sana: <b>{queue.queue_date || "—"}</b></div>
                  {queue.slot_time ? (
                    <div className="idesc">🕐 Qabul vaqti: <b>{queue.slot_time}</b></div>
                  ) : active ? (
                    <>
                      <div className="idesc">
                        👥 Oldingizda: <b>{queue.ahead_count || 0} ta navbat</b>
                      </div>
                      {queue.wait_minutes > 0 ? (
                        <div className="idesc">
                          ⏳ Taxminiy kutish: <b>~{queue.wait_minutes} daqiqa</b>
                        </div>
                      ) : null}
                    </>
                  ) : null}
                  {queue.note ? <div className="idesc">Izoh: {queue.note}</div> : null}
                  {CANCELLABLE_STATUSES.has(queue.status) ? (
                    <button
                      className="mini-btn"
                      disabled={busyId === queue.id}
                      type="button"
                      onClick={() => setCancelTarget(queue)}
                    >
                      Navbatni bekor qilish
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="idesc my-queues-v1656__empty">
          Hozircha xizmat navbati olinmagan.
        </div>
      )}
      {cancelTarget ? (
        <div className="my-queues-v1656__backdrop">
          <section
            aria-label="Navbatni bekor qilish"
            aria-modal="true"
            className="my-queues-v1656__confirm"
            role="dialog"
          >
            <b>Navbatingizni bekor qilasizmi?</b>
            <div>
              <button
                className="mini-btn"
                disabled={busyId !== null}
                type="button"
                onClick={() => setCancelTarget(null)}
              >
                Bekor qilish
              </button>
              <button
                className="mini-btn danger"
                disabled={busyId !== null}
                type="button"
                onClick={() => { void cancelQueue(); }}
              >
                Ha, bekor qilaman
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
