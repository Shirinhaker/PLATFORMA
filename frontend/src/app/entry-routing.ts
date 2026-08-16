export type EntryLocation = Pick<Location, "hostname" | "pathname" | "search" | "hash">;

export function resolveAdminEntryRedirect(location: EntryLocation): string | null {
  if (
    location.hostname.toLowerCase() !== "admin.koprik.uz" ||
    location.pathname !== "/"
  ) {
    return null;
  }

  return `/admin${location.search}${location.hash}`;
}
