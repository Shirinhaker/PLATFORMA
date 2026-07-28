import type { ReactNode } from "react";


type AppShellProps = {
  children: ReactNode;
  authenticated: boolean;
  onCabinet?: () => void;
  onLogin?: () => void;
};


export function AppShell({
  children,
  authenticated,
  onCabinet,
  onLogin,
}: AppShellProps) {
  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <span className="app-shell__brand">Koprik</span>
        <nav aria-label="Akkaunt menyusi">
          {authenticated ? (
            <button type="button" onClick={onCabinet}>Kabinet</button>
          ) : (
            <button type="button" onClick={onLogin}>Kirish</button>
          )}
        </nav>
      </header>
      {children}
    </div>
  );
}
