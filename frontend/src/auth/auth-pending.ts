import type {
  AccountType,
  ChallengeResent,
  ChallengeStarted,
  RegistrationStart,
} from "../api/types";


export const TELEGRAM_AUTH_PENDING_KEY = "koprik_telegram_auth_pending_v1";

type PendingBase = {
  request_id: number;
  deep_link: string;
  code_sent?: boolean;
  resend_at: number;
  expires_at: number;
};

export type PendingAuth =
  | (PendingBase & { kind: "login" })
  | (PendingBase & {
      kind: "register";
      role: AccountType;
      payload: RegistrationStart;
    });


function storage() {
  return typeof window === "undefined" ? null : window.sessionStorage;
}


function isAccountType(value: unknown): value is AccountType {
  return value === "user" || value === "business";
}


function isRegistrationStart(value: unknown): value is RegistrationStart {
  if (!value || typeof value !== "object") return false;
  const payload = value as Partial<RegistrationStart>;
  return isAccountType(payload.account_type) && typeof payload.name === "string";
}


export function clearPendingAuth() {
  try {
    storage()?.removeItem(TELEGRAM_AUTH_PENDING_KEY);
  } catch {
    // Authentication still works when browser storage is unavailable.
  }
}


export function readPendingAuth(): PendingAuth | null {
  try {
    const raw = storage()?.getItem(TELEGRAM_AUTH_PENDING_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<PendingAuth>;
    const commonIsValid = (
      (value.kind === "login" || value.kind === "register")
      && Number.isInteger(value.request_id)
      && Number(value.request_id) > 0
      && typeof value.deep_link === "string"
      && Number(value.expires_at) > Date.now()
      && Number.isFinite(Number(value.resend_at))
    );
    if (!commonIsValid) {
      clearPendingAuth();
      return null;
    }
    if (
      value.kind === "register"
      && (!isAccountType(value.role) || !isRegistrationStart(value.payload))
    ) {
      clearPendingAuth();
      return null;
    }
    return value as PendingAuth;
  } catch {
    clearPendingAuth();
    return null;
  }
}


export function savePendingAuth(
  kind: "login" | "register",
  challenge: ChallengeStarted,
  registration?: RegistrationStart,
) {
  const common: PendingBase = {
    request_id: challenge.request_id,
    deep_link: challenge.deep_link,
    code_sent: challenge.code_sent,
    resend_at: Date.now() + challenge.resend_after * 1000,
    expires_at: Date.now() + challenge.expires_in * 1000,
  };
  const pending: PendingAuth = kind === "register" && registration
    ? {
        ...common,
        kind,
        role: registration.account_type,
        payload: registration,
      }
    : { ...common, kind: "login" };
  try {
    storage()?.setItem(TELEGRAM_AUTH_PENDING_KEY, JSON.stringify(pending));
  } catch {
    // Authentication still works when browser storage is unavailable.
  }
}


export function refreshPendingAuth(result: ChallengeResent) {
  const pending = readPendingAuth();
  if (!pending || pending.request_id !== result.request_id) return;
  try {
    storage()?.setItem(TELEGRAM_AUTH_PENDING_KEY, JSON.stringify({
      ...pending,
      resend_at: Date.now() + result.resend_after * 1000,
      expires_at: Date.now() + result.expires_in * 1000,
    }));
  } catch {
    // Authentication still works when browser storage is unavailable.
  }
}


export function pendingResendSeconds(pending: PendingAuth) {
  return Math.max(0, Math.ceil((pending.resend_at - Date.now()) / 1000));
}


export function openTelegramLink(deepLink: string) {
  if (!deepLink || typeof window === "undefined") return;
  try {
    const opened = window.open(deepLink, "_blank");
    if (opened) opened.opener = null;
  } catch {
    // The visible Telegram button remains available when a popup is blocked.
  }
}
