import type { SessionIdentity } from "../api/types";


export type AppSession =
  | { status: "loading" }
  | { status: "guest" }
  | { status: "user"; identity: SessionIdentity }
  | { status: "business"; identity: SessionIdentity };
