import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { cabinetProfileResource, useCabinetProfile } from "./cabinet-profile-resource";
const identity = {
  account_id: 5,
  account_type: "user" as const,
  name: "Ali",
  login: "ali",
  csrf_token: "test",
  expires_at: "2099-01-01",
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((yes) => {
    resolve = yes;
  });
  return { promise, resolve };
}
describe("cabinet profile reuse", () => {
  it("shares the homepage request and shows cached data before refresh finishes", async () => {
    const api = {};
    const first = deferred<{ name: string }>();
    const next = deferred<{ name: string }>();
    const fetch = vi
      .fn()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(next.promise);
    const resource = cabinetProfileResource(api, identity, "user", fetch);
    const preload = resource.load();
    const cabinet = renderHook(() => useCabinetProfile(api, identity, "user", fetch));
    await act(async () => {
      first.resolve({ name: "Ali" });
      await preload;
    });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(cabinet.result.current.profile).toEqual({ name: "Ali" });
    cabinet.unmount();
    const reopened = renderHook(() => useCabinetProfile(api, identity, "user", fetch));
    expect(reopened.result.current.profile).toEqual({ name: "Ali" });
    expect(reopened.result.current.loading).toBe(false);
    await act(async () => {
      next.resolve({ name: "Updated" });
      await resource.load();
    });
    expect(reopened.result.current.profile).toEqual({ name: "Updated" });
  });
  it("isolates new sessions, cabinet roles and API clients from late responses", async () => {
    const api = {};
    const late = deferred<{ name: string }>();
    const fetch = vi.fn(() => late.promise);
    const old = cabinetProfileResource(api, identity, "user", fetch);
    const pending = old.load();
    const session = cabinetProfileResource(api, { ...identity }, "user", fetch);
    const business = cabinetProfileResource(api, identity, "business", fetch);
    const otherApi = cabinetProfileResource({}, identity, "user", fetch);
    late.resolve({ name: "Old account" });
    await pending;
    for (const resource of [session, business, otherApi])
      expect(resource.getSnapshot().profile).toBeNull();
  });
  it("preserves saved edits when an earlier refresh arrives late", async () => {
    const late = deferred<{ name: string }>();
    const resource = cabinetProfileResource({}, identity, "user", () => late.promise);
    const pending = resource.load();
    resource.setProfile({ name: "Saved" });
    late.resolve({ name: "Before edit" });
    await pending;
    expect(resource.getSnapshot().profile).toEqual({ name: "Saved" });
  });
  it("retains cached content on temporary failure and retries successfully", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ name: "Fresh" });
    const resource = cabinetProfileResource({}, identity, "user", fetch);
    resource.setProfile({ name: "Cached" });
    await expect(resource.load()).rejects.toThrow("offline");
    expect(resource.getSnapshot().profile).toEqual({ name: "Cached" });
    await resource.load();
    expect(resource.getSnapshot()).toEqual({ profile: { name: "Fresh" }, error: null });
  });
  it.each([401, 403])(
    "clears cached data when access is denied (%s)",
    async (status) => {
      const error = Object.assign(new Error("Access denied"), { status });
      const resource = cabinetProfileResource<{ name: string }>(
        {},
        identity,
        "user",
        async () => {
          throw error;
        },
      );
      resource.setProfile({ name: "Cached" });
      await expect(resource.load()).rejects.toBe(error);
      expect(resource.getSnapshot().profile).toBeNull();
    },
  );
});
