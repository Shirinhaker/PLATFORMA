import type { ReactNode } from "react";

import { PublicHeader } from "../legacy/public/PublicHeader";
import "../legacy/public/legacy-public.css";

type AppShellProps = {
  children: ReactNode;
  authenticated: boolean;
  title?: string;
  isHome?: boolean;
  onHome?: () => void;
  onLocation?: () => void;
  onAccount?: () => void;
  onBack?: () => void;
  onCabinet?: () => void;
  onLogin?: () => void;
};

const noop = () => undefined;

export function AppShell({
  children,
  authenticated,
  title,
  isHome = true,
  onHome = noop,
  onLocation = noop,
  onAccount,
  onBack = noop,
  onCabinet,
  onLogin,
}: AppShellProps) {
  const accountAction = (
    onAccount
    ?? (authenticated ? onCabinet : onLogin)
    ?? noop
  );

  return (
    <div className="app-shell">
      <PublicHeader
        authenticated={authenticated}
        title={title}
        isHome={isHome}
        onHome={onHome}
        onLocation={onLocation}
        onAccount={accountAction}
        onBack={onBack}
      />
      {children}
    </div>
  );
}
