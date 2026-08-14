import { useState, type ReactNode } from "react";

import type { ApiClient } from "../api/client";
import type {
  BusinessQueueEntry,
  BusinessQueueProvider,
} from "../api/types";
import "./QueueBookingV1656.css";


export type QueueBookingApi = Pick<
  ApiClient,
  "getQueueOptions" | "getQueueSlots" | "createQueue"
>;

export type QueueBookingTarget = {
  businessPublicId: string;
  itemPublicId: string;
  serviceName: string;
  direction: string;
};

type Props = {
  api: QueueBookingApi;
  target: QueueBookingTarget;
  onClose(): void;
  onMessage(message: string): void;
  onBooked?(entry: BusinessQueueEntry): void;
};

type Stage = "date" | "provider" | "slot" | "loading";

const QUEUE_METHODS: ReadonlyArray<keyof QueueBookingApi> = [
  "getQueueOptions",
  "getQueueSlots",
  "createQueue",
];


export function supportsQueueBookingApi(api: object): api is QueueBookingApi {
  return QUEUE_METHODS.every((method) => (
    typeof (api as Partial<QueueBookingApi>)[method] === "function"
  ));
}


function localIsoDate() {
  const value = new Date();
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}


function providerLabel(direction: string) {
  return direction === "Tibbiy xizmatlar" ? "Shifokor" : "Xizmat ko'rsatuvchi";
}


function errorText(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}


function ModalFrame({
  title,
  children,
  close,
  submit,
}: {
  title: string;
  children: ReactNode;
  close(): void;
  submit(): void;
}) {
  return (
    <>
      <div className="app-modal-back on" onClick={close} />
      <div className="app-confirm on" role="dialog" aria-modal="true">
        <div className="acf-title">{title}</div>
        {children}
        <div className="acf-btns">
          <button className="acf-cancel" type="button" onClick={close}>
            Bekor qilish
          </button>
          <button className="acf-ok" type="button" onClick={submit}>
            Saqlash
          </button>
        </div>
      </div>
    </>
  );
}


function FieldLabel({ children }: { children: ReactNode }) {
  return <div className="queue-booking-v1656__label">{children}</div>;
}


export function QueueBookingV1656({
  api,
  target,
  onClose,
  onMessage,
  onBooked,
}: Props) {
  const [stage, setStage] = useState<Stage>("date");
  const [queueDate, setQueueDate] = useState(localIsoDate);
  const [providers, setProviders] = useState<BusinessQueueProvider[]>([]);
  const [providerId, setProviderId] = useState("");
  const [slots, setSlots] = useState<string[]>([]);
  const [slotTime, setSlotTime] = useState("");
  const label = providerLabel(target.direction);

  function finishWithMessage(message: string) {
    onMessage(message);
    onClose();
  }

  async function saveQueue(selectedProviderId: number, selectedSlot: string) {
    setStage("loading");
    try {
      const entry = await api.createQueue({
        business_public_id: target.businessPublicId,
        item_public_id: target.itemPublicId,
        provider_id: selectedProviderId,
        queue_date: queueDate,
        slot_time: selectedSlot,
        note: "",
      });
      onMessage(`Navbatingiz: ${entry.queue_code}`);
      onBooked?.(entry);
      onClose();
    } catch (reason) {
      finishWithMessage(errorText(reason, "Navbat saqlanmadi."));
    }
  }

  async function submitDate() {
    const selectedDate = queueDate.trim();
    if (!selectedDate) {
      onMessage("Sana (YYYY-MM-DD) kiritilishi shart.");
      return;
    }
    setStage("loading");
    try {
      const options = await api.getQueueOptions(
        target.businessPublicId,
        target.itemPublicId,
        selectedDate,
      );
      if (!options.providers.length) {
        finishWithMessage(`${label} hali biriktirilmagan.`);
        return;
      }
      setProviders(options.providers);
      setProviderId("");
      setStage("provider");
    } catch (reason) {
      finishWithMessage(errorText(reason, "Navbat ma'lumotlari yuklanmadi."));
    }
  }

  async function submitProvider() {
    const selectedId = Number(providerId);
    const provider = providers.find((row) => row.id === selectedId);
    if (!provider) {
      onMessage(`${label} tanlanishi shart.`);
      return;
    }
    if (provider.mode !== "slot") {
      await saveQueue(selectedId, "");
      return;
    }
    setStage("loading");
    try {
      const response = await api.getQueueSlots(
        target.businessPublicId,
        target.itemPublicId,
        selectedId,
        queueDate,
      );
      if (!response.slots.length) {
        finishWithMessage("Bu kunga bo'sh vaqt yo'q. Boshqa sana tanlang.");
        return;
      }
      setSlots(response.slots);
      setSlotTime("");
      setStage("slot");
    } catch (reason) {
      finishWithMessage(errorText(reason, "Bo'sh vaqtlar yuklanmadi."));
    }
  }

  async function submitSlot() {
    if (!slotTime) {
      onMessage("Bo'sh vaqtlar tanlanishi shart.");
      return;
    }
    await saveQueue(Number(providerId), slotTime);
  }

  let modal: ReactNode = null;
  if (stage === "date") {
    modal = (
      <ModalFrame
        title={`${target.serviceName} — navbat`}
        close={onClose}
        submit={() => { void submitDate(); }}
      >
        <FieldLabel>Sana (YYYY-MM-DD)</FieldLabel>
        <input
          aria-label="Sana (YYYY-MM-DD)"
          className="input"
          type="text"
          value={queueDate}
          onChange={(event) => setQueueDate(event.target.value)}
        />
      </ModalFrame>
    );
  } else if (stage === "provider") {
    modal = (
      <ModalFrame
        title={`${label}ni tanlang`}
        close={onClose}
        submit={() => { void submitProvider(); }}
      >
        <FieldLabel>{label}</FieldLabel>
        <select
          aria-label={label}
          className="input"
          value={providerId}
          onChange={(event) => setProviderId(event.target.value)}
        >
          <option value="">{label}ni tanlang</option>
          {providers.map((provider) => (
            <option value={provider.id} key={provider.id}>
              {provider.name}
              {provider.specialty ? ` — ${provider.specialty}` : ""}
              {provider.mode === "slot"
                ? " (vaqtli qabul)"
                : ` (navbat ${provider.queue_count} ta)`}
            </option>
          ))}
        </select>
      </ModalFrame>
    );
  } else if (stage === "slot") {
    modal = (
      <ModalFrame
        title="Qabul vaqtini tanlang"
        close={onClose}
        submit={() => { void submitSlot(); }}
      >
        <FieldLabel>Bo'sh vaqtlar</FieldLabel>
        <select
          aria-label="Bo'sh vaqtlar"
          className="input"
          value={slotTime}
          onChange={(event) => setSlotTime(event.target.value)}
        >
          <option value="">Vaqtni tanlang</option>
          {slots.map((slot) => <option value={slot} key={slot}>{slot}</option>)}
        </select>
      </ModalFrame>
    );
  }

  return <div className="queue-booking-v1656">{modal}</div>;
}
