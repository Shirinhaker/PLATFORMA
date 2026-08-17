import { useEffect, useState } from "react";

import type { BusinessOnlineRecord } from "../api/business-online-types";
import { queueUiLabels } from "./business-profile-config";
import { BusinessMedicalProvidersView } from "./BusinessMedicalProvidersView";
import {
  AppToast,
  compareName,
  isQueueEnabled,
  localIsoDate,
  ModalField,
  ModalFrame,
  providerChoiceId,
  providerItemIds,
  recordId,
  STATUS_LABELS,
  text,
  type QueueModal,
  type QueueProps,
  type Toast,
} from "./BusinessMedicalShared";

export function BusinessMedicalQueueView({
  direction,
  rows,
  doctors,
  staff,
  items,
  busy,
  loading = false,
  createDoctor,
  patchDoctor,
  createOffline,
  changeStatus,
  swapQueues,
  loadDate,
  onBackHandlerChange,
}: QueueProps) {
  const labels = queueUiLabels(direction);
  const [date, setDate] = useState(localIsoDate);
  const [modal, setModal] = useState<QueueModal>(null);
  const [toast, setToast] = useState<Toast>(null);
  const [providersOpen, setProvidersOpen] = useState(false);
  const queueItems = items
    .filter(
      (item) => text(item.kind) === "service" && isQueueEnabled(item.queue_enabled),
    )
    .sort(compareName);
  const staffById = new Map(staff.map((row) => [text(row.id), row]));
  const visibleRows = rows.filter((row) => text(row.queue_date) === date);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  useEffect(() => {
    if (!providersOpen) onBackHandlerChange(null);
  }, [onBackHandlerChange, providersOpen]);

  function providersForItem(itemId: string) {
    return doctors.filter(
      (doctor) =>
        doctor.status === "active" &&
        providerItemIds(doctor).includes(itemId) &&
        staffById.has(text(doctor.staff_id)),
    );
  }

  function openOffline() {
    const providerCount = queueItems.reduce(
      (total, item) => total + providersForItem(text(item.id)).length,
      0,
    );
    if (queueItems.length === 0 || providerCount === 0) {
      setToast({
        text: `Avval navbat yoqilgan xizmatga ${labels.provider.toLowerCase()} biriktiring.`,
        role: "alert",
      });
      return;
    }
    setModal({ kind: "offline", patient: "", phone: "", itemId: "", staffId: "" });
  }

  async function setStatus(row: BusinessOnlineRecord, status: string) {
    if (await changeStatus(recordId(row), status)) await loadDate(date);
  }

  async function saveOffline(current: Extract<QueueModal, { kind: "offline" }>) {
    if (!current.patient.trim()) {
      setToast({
        text: `${labels.customer} ism-familiyasi kiritilishi shart.`,
        role: "alert",
      });
      return;
    }
    if (!current.itemId) {
      setToast({ text: "Xizmat tanlanishi shart.", role: "alert" });
      return;
    }
    if (!current.staffId) {
      setToast({ text: `${labels.provider} tanlanishi shart.`, role: "alert" });
      return;
    }
    const saved = await createOffline({
      patientName: current.patient.trim(),
      phone: current.phone.trim(),
      itemId: current.itemId,
      providerId: current.staffId,
      queueDate: date,
    });
    if (!saved) return;
    setModal(null);
    setToast({ text: `Navbat: ${text(saved.queue_code)}`, role: "status" });
    await loadDate(date);
  }

  async function saveSwap(current: Extract<QueueModal, { kind: "swap" }>) {
    if (!current.first) {
      setToast({ text: "Birinchi navbat ID kiritilishi shart.", role: "alert" });
      return;
    }
    if (!current.second) {
      setToast({ text: "Ikkinchi navbat ID kiritilishi shart.", role: "alert" });
      return;
    }
    if (!(await swapQueues(current.first, current.second))) return;
    setModal(null);
    setToast({ text: "Navbatlar almashtirildi.", role: "status" });
    await loadDate(date);
  }

  if (providersOpen) {
    return (
      <BusinessMedicalProvidersView
        direction={direction}
        doctors={doctors}
        staff={staff}
        items={items}
        busy={busy}
        createDoctor={createDoctor}
        patchDoctor={patchDoctor}
        onBackHandlerChange={onBackHandlerChange}
        onListBack={() => setProvidersOpen(false)}
      />
    );
  }

  return (
    <section className="business-medical-v1656">
      <div className="form-wrap">
        <div className="panel-card">
          <b>🏥 Yagona navbat</b>
          <div className="idesc">
            Onlayn va oflayn {labels.customer.toLowerCase()}lar bitta ketma-ketlikda.
          </div>
        </div>
        <input
          aria-label="Navbat sanasi"
          className="input"
          type="date"
          style={{ marginBottom: 10 }}
          value={date}
          onChange={(event) => {
            const nextDate = event.target.value;
            setDate(nextDate);
            void loadDate(nextDate);
          }}
        />
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <button
            type="button"
            className="btn btn-primary"
            style={{ flex: 1 }}
            onClick={openOffline}
          >
            + Oflayn navbat
          </button>
          <button
            type="button"
            className="btn btn-outline"
            style={{ flex: 1 }}
            onClick={() => setProvidersOpen(true)}
          >
            {labels.providers}
          </button>
        </div>
        <button
          type="button"
          className="btn btn-outline btn-block"
          style={{ marginBottom: 10 }}
          onClick={() => setModal({ kind: "swap", first: "", second: "" })}
        >
          ↔ Navbatlarni almashtirish
        </button>
        <div>
          {loading ? (
            <div className="idesc">Yuklanmoqda...</div>
          ) : visibleRows.length > 0 ? (
            visibleRows.map((row) => (
              <div className="panel-card" key={text(row.id)}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <div>
                    <b>
                      {text(row.queue_code)} · {text(row.patient_name)}
                    </b>
                    <div className="idesc">
                      {text(row.service_name)} ·{" "}
                      {text(row.provider_name ?? row.doctor_name)} ·{" "}
                      {row.source === "online" ? "Onlayn" : "Oflayn"}
                      {row.slot_time ? ` · 🕐 ${text(row.slot_time)}` : ""}
                    </div>
                  </div>
                  <span className="sort-chip">{STATUS_LABELS[text(row.status)]}</span>
                </div>
                <div
                  style={{ display: "flex", gap: 5, marginTop: 9, flexWrap: "wrap" }}
                >
                  <button
                    type="button"
                    className="mini-btn"
                    onClick={() => void setStatus(row, "called")}
                  >
                    Chaqirish
                  </button>
                  <button
                    type="button"
                    className="mini-btn"
                    onClick={() => void setStatus(row, "in_service")}
                  >
                    Qabul
                  </button>
                  <button
                    type="button"
                    className="mini-btn"
                    onClick={() => void setStatus(row, "done")}
                  >
                    Yakunlash
                  </button>
                  <button
                    type="button"
                    className="mini-btn"
                    onClick={() => void setStatus(row, "no_show")}
                  >
                    Kelmadi
                  </button>
                  <button
                    type="button"
                    className="mini-btn"
                    style={{ borderColor: "#DC2626", color: "#DC2626" }}
                    onClick={() => setModal({ kind: "cancel", queue: row })}
                  >
                    Bekor qilish
                  </button>
                </div>
              </div>
            ))
          ) : (
            <div className="empty">
              <h3>Navbat yo‘q</h3>
              <p>Onlayn yoki oflayn navbat qo‘shing.</p>
            </div>
          )}
        </div>
      </div>
      <AppToast toast={toast} />
      {modal?.kind === "cancel" ? (
        <ModalFrame
          close={() => setModal(null)}
          save={() => {
            const row = modal.queue;
            setModal(null);
            void setStatus(row, "cancelled");
          }}
          okText="Bekor qilish"
          danger
          busy={busy}
        >
          <div className="acf-text">
            Bu navbat bekor qilinsinmi? Foydalanuvchiga xabar yuboriladi.
          </div>
        </ModalFrame>
      ) : null}
      {modal?.kind === "offline" ? (
        <ModalFrame
          title="Oflayn navbat"
          close={() => setModal(null)}
          save={() => void saveOffline(modal)}
          busy={busy}
        >
          <ModalField
            id="medical-offline-patient"
            label={`${labels.customer} ism-familiyasi`}
            value={modal.patient}
            onChange={(value) => setModal({ ...modal, patient: value })}
          />
          <ModalField
            id="medical-offline-phone"
            label="Telefon"
            value={modal.phone}
            onChange={(value) => setModal({ ...modal, phone: value })}
          />
          <div
            style={{
              textAlign: "left",
              margin: "10px 2px 4px",
              fontSize: 13,
              color: "var(--koprik-soft, #6b7280)",
            }}
          >
            Xizmat
          </div>
          <select
            aria-label="Xizmat"
            className="input"
            id="medical-offline-item"
            value={modal.itemId}
            onChange={(event) =>
              setModal({ ...modal, itemId: event.target.value, staffId: "" })
            }
          >
            <option value="">Xizmatni tanlang</option>
            {queueItems.map((item) => (
              <option key={text(item.id)} value={text(item.id)}>
                {text(item.name)}
              </option>
            ))}
          </select>
          <div
            style={{
              textAlign: "left",
              margin: "10px 2px 4px",
              fontSize: 13,
              color: "var(--koprik-soft, #6b7280)",
            }}
          >
            {labels.provider}
          </div>
          <select
            aria-label={labels.provider}
            className="input"
            id="medical-offline-staff"
            value={modal.staffId}
            onChange={(event) => setModal({ ...modal, staffId: event.target.value })}
          >
            <option value="">{labels.provider}ni tanlang</option>
            {providersForItem(modal.itemId).map((doctor) => {
              const employee = staffById.get(text(doctor.staff_id)) ?? doctor;
              const choiceId = providerChoiceId(doctor);
              return (
                <option key={choiceId} value={choiceId}>
                  {text(employee.name)}
                  {employee.profession ? ` — ${text(employee.profession)}` : ""}
                </option>
              );
            })}
          </select>
        </ModalFrame>
      ) : null}
      {modal?.kind === "swap" ? (
        <ModalFrame
          title="Navbatlarni almashtirish"
          close={() => setModal(null)}
          save={() => void saveSwap(modal)}
          busy={busy}
        >
          <ModalField
            id="medical-swap-first"
            label="Birinchi navbat ID"
            value={modal.first}
            onChange={(value) => setModal({ ...modal, first: value })}
            numeric
          />
          <ModalField
            id="medical-swap-second"
            label="Ikkinchi navbat ID"
            value={modal.second}
            onChange={(value) => setModal({ ...modal, second: value })}
            numeric
          />
        </ModalFrame>
      ) : null}
    </section>
  );
}
