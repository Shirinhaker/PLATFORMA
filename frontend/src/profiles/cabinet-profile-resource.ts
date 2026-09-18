import { useEffect, useSyncExternalStore, type SetStateAction } from "react";
import type { SessionIdentity } from "../api/types";

type Snapshot<T> = { profile: T | null; error: unknown };

export function createProfileResource<T>(fetchProfile: () => Promise<T>) {
  let snapshot: Snapshot<T> = { profile: null, error: null };
  let pending: Promise<T> | null = null;
  let revision = 0;
  const listeners = new Set<() => void>();
  function publish(next: Snapshot<T>) {
    snapshot = next;
    listeners.forEach((listener) => listener());
  }
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    setProfile(value: SetStateAction<T | null>) {
      // Kechikkan javob yangi saqlangan profilni almashtirmasligi kerak.
      revision += 1;
      const profile =
        typeof value === "function"
          ? (value as (current: T | null) => T | null)(snapshot.profile)
          : value;
      publish({ profile, error: null });
    },
    load(): Promise<T> {
      if (pending) return pending;
      const startedAt = revision;
      pending = Promise.resolve()
        .then(fetchProfile)
        .then(
          (profile) => {
            if (revision === startedAt) publish({ profile, error: null });
            return profile;
          },
          (error: unknown) => {
            if (revision === startedAt) {
              const denied =
                error &&
                typeof error === "object" &&
                "status" in error &&
                (error.status === 401 || error.status === 403);
              publish({ profile: denied ? null : snapshot.profile, error });
            }
            throw error;
          },
        )
        .finally(() => {
          pending = null;
        });
      return pending;
    },
  };
}

// Kirish va kabinet almashishda yangi identity obyekti yaratiladi.
// WeakMap eski sessiyalarni ajratadi va ularning xotiradan tozalanishiga imkon beradi.
const resources = new WeakMap<object, WeakMap<SessionIdentity, Map<string, unknown>>>();
export function cabinetProfileResource<T>(
  api: object,
  identity: SessionIdentity,
  kind: "user" | "business",
  fetchProfile: () => Promise<T>,
): ReturnType<typeof createProfileResource<T>> {
  let sessions = resources.get(api);
  if (!sessions) resources.set(api, (sessions = new WeakMap()));
  let profiles = sessions.get(identity);
  if (!profiles) sessions.set(identity, (profiles = new Map()));
  if (!profiles.has(kind)) profiles.set(kind, createProfileResource(fetchProfile));
  return profiles.get(kind) as ReturnType<typeof createProfileResource<T>>;
}

export function useCabinetProfile<T>(
  api: object,
  identity: SessionIdentity,
  kind: "user" | "business",
  fetchProfile: () => Promise<T>,
) {
  const resource = cabinetProfileResource(api, identity, kind, fetchProfile);
  const snapshot = useSyncExternalStore(resource.subscribe, resource.getSnapshot);
  useEffect(() => {
    void resource.load().catch(() => undefined);
  }, [resource]);
  return {
    profile: snapshot.profile,
    loadError: snapshot.error,
    loading: !snapshot.profile && !snapshot.error,
    setProfile: resource.setProfile,
  };
}
