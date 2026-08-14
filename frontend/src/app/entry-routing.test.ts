import { describe, expect, it } from "vitest";

import { resolveAdminEntryRedirect } from "./entry-routing";


describe("production entry routing", () => {
  it("redirects the admin production domain root to the admin application", () => {
    expect(resolveAdminEntryRedirect({
      hostname: "admin.koprik.uz",
      pathname: "/",
      search: "?from=bookmark",
      hash: "#payments",
    })).toBe("/admin?from=bookmark#payments");
  });

  it("keeps the public domain and explicit admin path unchanged", () => {
    expect(resolveAdminEntryRedirect({
      hostname: "koprik.uz",
      pathname: "/",
      search: "",
      hash: "",
    })).toBeNull();
    expect(resolveAdminEntryRedirect({
      hostname: "admin.koprik.uz",
      pathname: "/admin",
      search: "",
      hash: "",
    })).toBeNull();
  });
});
