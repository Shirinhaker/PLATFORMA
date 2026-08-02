import { useCallback, useEffect, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type { BusinessOnlineRecord } from "../api/business-online-types";
import type {
  BusinessQueueEntry,
  BusinessQueueProvider,
  BusinessQueueProviderWrite,
  BusinessQueueSetup,
  QueueEntryStatus,
  QueueProviderMode,
  QueueProviderStatus,
} from "../api/types";
import {
  BusinessMedicalProvidersV1656View,
  BusinessMedicalQueueV1656View,
} from "../profiles/BusinessMedicalV1656View";


export type BusinessQueueApi = Pick<
  ApiClient,
  | "getBusinessQueueSetup"
  | "getBusinessQueueProviders"
  | "createBusinessQueueProvider"
  | "updateBusinessQueueProvider"
  | "getBusinessQueueEntries"
  | "createBusinessOfflineQueue"
  | "changeBusinessQueueStatus"
  | "swapBusinessQueues"
>;

type Props = {
  api: BusinessQueueApi;
  direction: string;
  view: "medical-providers" | "medical-queue";
  onBackHandlerChange: (
    handler: (() => void) | null,
    title?: string,
  ) => void;
};

const QUEUE_METHODS: ReadonlyArray<keyof BusinessQueueApi> = [
  "getBusinessQueueSetup",
  "getBusinessQueueProviders",
  "createBusinessQueueProvider",
  "updateBusinessQueueProvider",
  "getBusinessQueueEntries",
  "createBusinessOfflineQueue",
  "changeBusinessQueueStatus",
  "swapBusinessQueues",
];

export function supportsBusinessQueueApi(
  api: object,
): api is BusinessQueueApi {
  return QUEUE_METHODS.every((method) => (
    typeof (api as Partial<BusinessQueueApi>)[method] === "function"
  ));
}

function localIsoDate() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function setupRecords(setup: BusinessQueueSetup) {
  return {
    items: setup.services.map((service): BusinessOnlineRecord => ({
      id: service.public_id,
      public_id: service.public_id,
      name: service.name,
      price: service.price_text,
      kind: "service",
      queue_enabled: true,
    })),
    staff: setup.staff.map((employee): BusinessOnlineRecord => ({
      ...employee,
      status: "active",
    })),
  };
}

function providerRecord(provider: BusinessQueueProvider): BusinessOnlineRecord {
  return {
    ...provider,
    provider_id: provider.id,
    item_ids: provider.item_public_ids,
  };
}

function entryRecord(entry: BusinessQueueEntry): BusinessOnlineRecord {
  return {
    ...entry,
    doctor_name: entry.provider_name,
  };
}

function providerWrite(record: BusinessOnlineRecord): BusinessQueueProviderWrite {
  return {
    staff_id: Number(record.staff_id ?? 0),
    item_public_ids: Array.isArray(record.item_public_ids)
      ? record.item_public_ids.map(String)
      : Array.isArray(record.item_ids)
        ? record.item_ids.map(String)
        : [],
    specialty: String(record.specialty ?? ""),
    experience_years: Number(record.experience_years ?? 0),
    qualification: String(record.qualification ?? ""),
    work_days: String(record.work_days ?? "1,2,3,4,5,6"),
    work_start: String(record.work_start ?? "08:00"),
    work_end: String(record.work_end ?? "17:00"),
    avg_minutes: Number(record.avg_minutes ?? 20),
    room: String(record.room ?? ""),
    bio: String(record.bio ?? ""),
    status: String(record.status ?? "active") as QueueProviderStatus,
    mode: String(record.mode ?? "live") as QueueProviderMode,
  };
}

export function BusinessQueueV1656({
  api,
  direction,
  view,
  onBackHandlerChange,
}: Props) {
  const [setup, setSetup] = useState<BusinessQueueSetup>({
    services: [],
    staff: [],
  });
  const [providers, setProviders] = useState<BusinessQueueProvider[]>([]);
  const [entries, setEntries] = useState<BusinessQueueEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [error, setError] = useState("");
  const entriesRequest = useRef(0);

  const loadDate = useCallback(async (date: string) => {
    const requestId = ++entriesRequest.current;
    setEntriesLoading(true);
    setError("");
    try {
      const nextEntries = await api.getBusinessQueueEntries(date);
      if (requestId === entriesRequest.current) setEntries(nextEntries);
    } catch (reason) {
      if (requestId === entriesRequest.current) {
        setError(reason instanceof Error ? reason.message : "Navbat yuklanmadi.");
      }
    } finally {
      if (requestId === entriesRequest.current) setEntriesLoading(false);
    }
  }, [api]);

  useEffect(() => {
    if (!error) return;
    const timeout = window.setTimeout(() => setError(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [error]);

  useEffect(() => {
    let active = true;
    const entriesRequestId = view === "medical-queue"
      ? ++entriesRequest.current
      : entriesRequest.current;
    async function load() {
      setInitialLoading(true);
      setError("");
      try {
        const [nextSetup, nextProviders, nextEntries] = await Promise.all([
          api.getBusinessQueueSetup(),
          api.getBusinessQueueProviders(),
          view === "medical-queue"
            ? api.getBusinessQueueEntries(localIsoDate())
            : Promise.resolve([]),
        ]);
        if (!active) return;
        setSetup(nextSetup);
        setProviders(nextProviders);
        if (entriesRequestId === entriesRequest.current) {
          setEntries(nextEntries);
        }
      } catch (reason) {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Navbat bo‘limi yuklanmadi.");
        }
      } finally {
        if (active) setInitialLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [api, view]);

  const records = setupRecords(setup);
  const doctorRecords = providers.map(providerRecord);

  async function createDoctor(record: BusinessOnlineRecord) {
    setBusy(true);
    setError("");
    try {
      const saved = await api.createBusinessQueueProvider(providerWrite(record));
      setProviders((current) => [...current, saved]);
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yozuv saqlanmadi.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function patchDoctor(
    id: number | string,
    record: BusinessOnlineRecord,
  ) {
    setBusy(true);
    setError("");
    try {
      const saved = await api.updateBusinessQueueProvider(
        Number(id),
        providerWrite(record),
      );
      setProviders((current) => current.map((provider) => (
        provider.id === saved.id ? saved : provider
      )));
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yozuv yangilanmadi.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  const content = view === "medical-providers" ? (
    <BusinessMedicalProvidersV1656View
      direction={direction}
      doctors={doctorRecords}
      staff={records.staff}
      items={records.items}
      busy={busy}
      loading={initialLoading}
      createDoctor={createDoctor}
      patchDoctor={patchDoctor}
      onBackHandlerChange={onBackHandlerChange}
    />
  ) : (
    <BusinessMedicalQueueV1656View
      direction={direction}
      rows={entries.map(entryRecord)}
      doctors={doctorRecords}
      staff={records.staff}
      items={records.items}
      busy={busy}
      loading={initialLoading || entriesLoading}
      createDoctor={createDoctor}
      patchDoctor={patchDoctor}
      createOffline={async (input) => {
        setBusy(true);
        setError("");
        try {
          return entryRecord(await api.createBusinessOfflineQueue({
            item_public_id: input.itemId,
            provider_id: Number(input.providerId),
            queue_date: input.queueDate,
            patient_name: input.patientName,
            phone: input.phone,
            note: "",
            slot_time: "",
          }));
        } catch (reason) {
          setError(reason instanceof Error ? reason.message : "Navbat saqlanmadi.");
          return null;
        } finally {
          setBusy(false);
        }
      }}
      changeStatus={async (id, status) => {
        setBusy(true);
        setError("");
        try {
          const saved = await api.changeBusinessQueueStatus(
            Number(id),
            status as QueueEntryStatus,
          );
          setEntries((current) => current.map((entry) => (
            entry.id === saved.id ? saved : entry
          )));
          return true;
        } catch (reason) {
          setError(reason instanceof Error ? reason.message : "Amal bajarilmadi.");
          return false;
        } finally {
          setBusy(false);
        }
      }}
      swapQueues={async (first, second) => {
        setBusy(true);
        setError("");
        try {
          await api.swapBusinessQueues(Number(first), Number(second));
          return true;
        } catch (reason) {
          setError(reason instanceof Error ? reason.message : "Amal bajarilmadi.");
          return false;
        } finally {
          setBusy(false);
        }
      }}
      loadDate={loadDate}
      onBackHandlerChange={onBackHandlerChange}
    />
  );

  return (
    <>
      {error ? (
        <div className="business-medical-v1656">
          <div className="app-toast on" role="alert">{error}</div>
        </div>
      ) : null}
      {content}
    </>
  );
}
