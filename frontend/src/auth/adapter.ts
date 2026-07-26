export type AuthContext =
  | { kind: "telegram"; initData: string }
  | { kind: "web" };

type TelegramWindow = Window & {
  Telegram?: { WebApp?: { initData?: string } };
};

export function resolveAuthContext(
  source: TelegramWindow = window as TelegramWindow,
): AuthContext {
  const initData = source.Telegram?.WebApp?.initData?.trim() ?? "";
  return initData
    ? { kind: "telegram", initData }
    : { kind: "web" };
}
