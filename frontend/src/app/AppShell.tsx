import type { ReactNode } from "react";

import { PublicHeader } from "../legacy/public/PublicHeader";
import "../legacy/public/legacy-public.css";

type AppShellProps = {
  children: ReactNode;
  authenticated: boolean;
  title?: string;
  isHome?: boolean;
  searchResultsActive?: boolean;
  publicFeatures?: { listings: boolean; taxi: boolean };
  theme?: "light" | "dark";
  cartCount?: number;
  onHome?: () => void;
  onLocation?: () => void;
  onAccount?: () => void;
  onBack?: () => void;
  onListings?: () => void;
  onCart?: () => void;
  onTaxi?: () => void;
  onToggleTheme?: () => void;
  onCabinet?: () => void;
  onLogin?: () => void;
};

const noop = () => undefined;

export function AppShell({
  children,
  authenticated,
  title,
  isHome = true,
  searchResultsActive = false,
  publicFeatures = { listings: false, taxi: false },
  theme = "light",
  cartCount = 0,
  onHome = noop,
  onLocation = noop,
  onAccount,
  onBack = noop,
  onListings,
  onCart,
  onTaxi,
  onToggleTheme = noop,
  onCabinet,
  onLogin,
}: AppShellProps) {
  const accountAction = (
    onAccount
    ?? (authenticated ? onCabinet : onLogin)
    ?? noop
  );

  return (
    <div className={`app-shell${isHome ? " home-active" : ""}${searchResultsActive ? " search-results-active" : ""}`}>
      <PublicHeader
        authenticated={authenticated}
        cartCount={cartCount}
        features={publicFeatures}
        theme={theme}
        title={title}
        isHome={isHome}
        onHome={onHome}
        onLocation={onLocation}
        onAccount={accountAction}
        onBack={onBack}
        onListings={onListings}
        onCart={onCart}
        onTaxi={onTaxi}
        onToggleTheme={onToggleTheme}
      />
      {children}
    </div>
  );
}
