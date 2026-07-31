import { useEffect, useMemo, useState } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import "./BusinessEducationEnrollmentsV1656View.css";


type Props = {
  rows: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  busy: boolean;
  loading: boolean;
  action: (
    resource: BusinessOnlineResource,
    name: string,
    id?: number | string,
    payload?: BusinessOnlineRecord,
  ) => Promise<BusinessOnlineRecord | null>;
  refresh: (...resources: BusinessOnlineResource[]) => Promise<void>;
};

type Filter = "new" | "accepted" | "rejected";
type Toast = { text: string; role: "alert" | "status" } | null;

const STATUS_LABELS: Record<Filter, string> = {
  new: "Yangi",
  accepted: "Qabul qilindi",
  rejected: "Rad etildi",
};

function text(value: unknown) {
  return String(value ?? "");
}

function number(value: unknown) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function recordId(row: BusinessOnlineRecord) {
  return (row.id ?? "") as number | string;
}


export function BusinessEducationEnrollmentsV1656View({
  rows,
  groups,
  busy,
  loading,
  action,
  refresh,
}: Props) {
  const [filter, setFilter] = useState<Filter>("new");
  const [selectedGroups, setSelectedGroups] = useState<Record<string, string>>({});
  const [rejecting, setRejecting] = useState<BusinessOnlineRecord | null>(null);
  const [toast, setToast] = useState<Toast>(null);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const filtered = useMemo(
    () => rows.filter((row) => text(row.status) === filter),
    [filter, rows],
  );

  async function reload() {
    await refresh("education_groups", "education_enrollments");
  }

  async function accept(row: BusinessOnlineRecord) {
    const id = recordId(row);
    const groupId = number(selectedGroups[String(id)]);
    if (!groupId) {
      setToast({ text: "Guruhni tanlang.", role: "alert" });
      return;
    }
    const saved = await action(
      "education_enrollments",
      "accept",
      id,
      { group_id: groupId },
    );
    if (!saved) return;
    await reload();
    setToast({
      text: "O'quvchi guruhga qabul qilindi.",
      role: "status",
    });
  }

  async function reject() {
    if (!rejecting) return;
    const id = recordId(rejecting);
    const saved = await action(
      "education_enrollments",
      "reject",
      id,
      {},
    );
    if (!saved) return;
    setRejecting(null);
    await reload();
    setToast({ text: "Ariza rad etildi.", role: "status" });
  }

  return (
    <div className="business-education-enrollments-v1656">
      <div className="form-wrap">
        <div className="panel-card">
          <b>Kursga yozilish arizalari</b>
          <div className="idesc">
            Arizani qabul qilishda o'quvchi biriktiriladigan guruhni tanlang.
          </div>
        </div>
        <div className="ad-tabs">
          <button
            type="button"
            className={`ad-tab${filter === "new" ? " on" : ""}`}
            onClick={() => setFilter("new")}
          >
            Yangi
          </button>
          <button
            type="button"
            className={`ad-tab${filter === "accepted" ? " on" : ""}`}
            onClick={() => setFilter("accepted")}
          >
            Qabul qilingan
          </button>
          <button
            type="button"
            className={`ad-tab${filter === "rejected" ? " on" : ""}`}
            onClick={() => setFilter("rejected")}
          >
            Rad etilgan
          </button>
        </div>
        <div>
          {loading ? <div className="idesc">Yuklanmoqda...</div> : filtered.map((row) => {
            const id = recordId(row);
            const status = text(row.status) as Filter;
            const compatibleGroups = groups.filter((group) => (
              !number(group.course_item_id)
              || number(group.course_item_id) === number(row.course_item_id)
            ));
            return (
              <div className="panel-card" key={String(id)}>
                <div style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 10,
                }}>
                  <div>
                    <b>{text(row.customer_name) || "Mijoz"}</b>
                    <div className="idesc">
                      📚 {text(row.course_name) || "Kurs"} · 📞 {text(row.phone) || "—"}
                    </div>
                  </div>
                  <span className="sort-chip">{STATUS_LABELS[status] ?? status}</span>
                </div>
                {row.note ? (
                  <div className="idesc" style={{ marginTop: 8 }}>
                    Izoh: {text(row.note)}
                  </div>
                ) : null}
                {status === "new" ? (
                  <>
                    <select
                      className="input"
                      style={{ marginTop: 10 }}
                      value={selectedGroups[String(id)] ?? ""}
                      onChange={(event) => setSelectedGroups((current) => ({
                        ...current,
                        [String(id)]: event.target.value,
                      }))}
                    >
                      <option value="">Guruhni tanlang</option>
                      {compatibleGroups.map((group) => (
                        <option key={String(group.id)} value={text(group.id)}>
                          {text(group.name)}
                        </option>
                      ))}
                    </select>
                    <div style={{ display: "flex", gap: 7, marginTop: 8 }}>
                      <button
                        type="button"
                        className="btn btn-primary"
                        style={{ flex: 1, height: 40 }}
                        onClick={() => void accept(row)}
                        disabled={busy}
                      >
                        Qabul qilish
                      </button>
                      <button
                        type="button"
                        className="btn btn-outline"
                        style={{ flex: 1, height: 40, color: "#dc2626" }}
                        onClick={() => setRejecting(row)}
                        disabled={busy}
                      >
                        Rad etish
                      </button>
                    </div>
                  </>
                ) : row.group_name ? (
                  <div className="idesc" style={{ marginTop: 8 }}>
                    Guruh: {text(row.group_name)}
                  </div>
                ) : null}
              </div>
            );
          })}
          {!loading && !filtered.length ? (
            <div className="empty">
              <h3>Arizalar yo'q</h3>
              <p>Bu bo'limda hozircha ariza mavjud emas.</p>
            </div>
          ) : null}
        </div>
      </div>

      {toast ? (
        <div className="app-toast on" role={toast.role}>{toast.text}</div>
      ) : null}

      {rejecting ? (
        <>
          <div className="app-modal-back on" onClick={() => setRejecting(null)} />
          <div className="app-confirm on" role="dialog" aria-modal="true">
            <div className="acf-text">Bu ariza rad etilsinmi?</div>
            <div className="acf-btns">
              <button
                type="button"
                className="acf-cancel"
                onClick={() => setRejecting(null)}
              >
                Bekor qilish
              </button>
              <button
                type="button"
                className="acf-ok danger"
                onClick={() => void reject()}
                disabled={busy}
              >
                Rad etish
              </button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
