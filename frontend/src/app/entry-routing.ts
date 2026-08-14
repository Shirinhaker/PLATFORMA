export type EntryLocation = Pick<
  Location,
  "hostname" | "pathname" | "search" | "hash"
>;


export function resolveAdminEntryRedirect(
  location: EntryLocation,
): string | null {
  const hostname = location.hostname.toLowerCase();
  if (
    (hostname === "koprik.uz" || hostname === "www.koprik.uz")
    && (location.pathname === "/admin" || location.pathname.startsWith("/admin/"))
  ) {
    return `https://admin.koprik.uz/admin${location.search}${location.hash}`;
  }
  if (
    hostname !== "admin.koprik.uz"
    || location.pathname !== "/"
  ) {
    return null;
  }

  return `/admin${location.search}${location.hash}`;
}
