import type { ApiClient } from "../api/client";
import type {
  BusinessProfile,
  DocumentCounterpartyWrite,
  DocumentDirection,
} from "../api/types";

export type DocumentsApi = Pick<
  ApiClient,
  | "getDocumentCounterparties"
  | "createDocumentCounterparty"
  | "updateDocumentCounterparty"
  | "deleteDocumentCounterparty"
  | "getDocuments"
  | "getDocument"
  | "createDocument"
  | "updateDocument"
  | "deleteDocument"
  | "sendDocument"
  | "respondDocument"
  | "updateBusinessProfile"
>;

export type DocumentsProps = {
  api: DocumentsApi;
  profile: BusinessProfile;
  initialView: "profile" | "center";
  canManageCounterparties: boolean;
  onProfile: (profile: BusinessProfile) => void;
  onBack: () => void;
};

export type DocumentsView =
  | "profile"
  | "center"
  | "counterparties"
  | "counterparty-form"
  | "compose"
  | "list"
  | "document";

export const EMPTY_COUNTERPARTY: DocumentCounterpartyWrite = {
  name: "",
  ctype: "Yetkazib beruvchi",
  director: "",
  phone: "",
  address: "",
  inn: "",
  account: "",
  bank: "",
  mfo: "",
  note: "",
};

export const DIRECTION_TEXT: Record<DocumentDirection, string> = {
  ichki: "Ichki",
  chiquvchi: "Chiquvchi",
  kiruvchi: "Kiruvchi",
};

const STATUS_CLASS: Record<string, string> = {
  yuborilgan: "sent",
  kutilmoqda: "waiting",
  "qabul qilindi": "accepted",
  "rad etildi": "rejected",
};

export function errorText(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

export function today() {
  const date = new Date();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function preview(body: string) {
  return body.replace(/\s+/g, " ").trim().slice(0, 60);
}

export async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const area = document.createElement("textarea");
  area.value = value;
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}

export function StatusBadge({ status }: { status: string }) {
  if (!status) return null;
  return (
    <span className={`documents-v1656__status ${STATUS_CLASS[status] ?? ""}`}>
      {status}
    </span>
  );
}

export function ScreenHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <header className="documents-v1656__header">
      <button type="button" className="documents-v1656__back" onClick={onBack}>
        <span className="documents-v1656__sr-only">Orqaga</span>←
      </button>
      <h1>{title}</h1>
    </header>
  );
}

export function DocumentsFeedback({
  error,
  notice,
}: {
  error: string;
  notice: string;
}) {
  return (
    <>
      {error ? (
        <p className="documents-v1656__error" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="documents-v1656__notice" role="status">
          {notice}
        </p>
      ) : null}
    </>
  );
}
