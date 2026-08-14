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

  it("redirects a public-domain admin bookmark to the separate admin site", () => {
    expect(resolveAdminEntryRedirect({
      hostname: "koprik.uz",
      pathname: "/admin",
      search: "?from=bookmark",
      hash: "#payments",
    })).toBe("https://admin.koprik.uz/admin?from=bookmark#payments");
  });

  it("keeps the public root and the real admin path unchanged", () => {
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
