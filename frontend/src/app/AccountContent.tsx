import type { SessionIdentity } from "../api/types";
import { AuthFlow } from "../auth/AuthFlow";
import type { AppSession } from "../auth/types";
import { BusinessProfile } from "../profiles/BusinessProfile";
import { UserProfile } from "../profiles/UserProfile";
import { SessionStatus } from "./SessionStatus";
import { type AppApi, supportsAuthFlow, supportsProfiles } from "./app-api";

type AccountContentProps = {
  api: AppApi;
  session: AppSession;
  authReason: string;
  onAuthenticated(identity: SessionIdentity): void;
  onLogout(): void;
  onSwitched(identity: SessionIdentity): void;
  onOpenDriverCabinet(): void;
  onOpenPublicListing(publicId: string): void;
  onOpenPublicProfile(kind: "user" | "business", publicId: string): void;
};

function Cabinet({ kind, name }: { kind: "user" | "business"; name: string }) {
  const title = kind === "user" ? "Oddiy kabinet" : "Biznes kabinet";
  return (
    <main className="session-panel">
      <p className="session-panel__eyebrow">Koprik</p>
      <h1>{title}</h1>
      <p>{name}</p>
    </main>
  );
}

export function AccountContent({
  api,
  session,
  authReason,
  onAuthenticated,
  onLogout,
  onSwitched,
  onOpenDriverCabinet,
  onOpenPublicListing,
  onOpenPublicProfile,
}: AccountContentProps) {
  if (session.status === "guest") {
    return supportsAuthFlow(api) ? (
      <AuthFlow api={api} onAuthenticated={onAuthenticated} reason={authReason} />
    ) : (
      <main className="session-panel">
        <h1>Koprik’ga kirish</h1>
      </main>
    );
  }
  if (session.status === "loading") {
    return <SessionStatus state="loading" />;
  }
  if (!supportsProfiles(api)) {
    return <Cabinet kind={session.status} name={session.identity.name} />;
  }

  return session.status === "user" ? (
    <UserProfile
      api={api}
      identity={session.identity}
      onLogout={onLogout}
      onOpenDriverCabinet={onOpenDriverCabinet}
      onOpenPublicListing={onOpenPublicListing}
      onOpenPublicProfile={onOpenPublicProfile}
      onSwitched={onSwitched}
    />
  ) : (
    <BusinessProfile
      api={api}
      identity={session.identity}
      onLogout={onLogout}
      onOpenPublicListing={onOpenPublicListing}
      onOpenPublicProfile={onOpenPublicProfile}
      onSwitched={onSwitched}
    />
  );
}
