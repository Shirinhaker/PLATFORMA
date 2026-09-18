import { useEffect, useState } from "react";
import type { AppSession } from "../auth/types";
import type { AppApi } from "./app-api";
import { cabinetProfileResource } from "../profiles/cabinet-profile-resource";

export function useOrderCustomerProfile(api: AppApi, session: AppSession) {
  const [orderCustomer, setOrderCustomer] = useState({ phone: "", address: "" });
  useEffect(() => {
    let active = true;
    if (session.status === "user" && typeof api.getUserProfile === "function") {
      cabinetProfileResource(api, session.identity, "user", () => api.getUserProfile!())
        .load()
        .then((profile) => {
          if (!active) return;
          setOrderCustomer({
            phone: profile.phone || "",
            address: [profile.region, profile.district, profile.mahalla]
              .filter(Boolean)
              .join(", "),
          });
        })
        .catch(() => undefined);
    } else if (
      session.status === "business" &&
      typeof api.getBusinessProfile === "function"
    ) {
      cabinetProfileResource(api, session.identity, "business", () =>
        api.getBusinessProfile!(),
      )
        .load()
        .then((profile) => {
          if (active)
            setOrderCustomer({
              phone: profile.phone || "",
              address: profile.address || "",
            });
        })
        .catch(() => undefined);
    } else if (session.status === "guest") {
      setOrderCustomer({ phone: "", address: "" });
    }
    return () => {
      active = false;
    };
  }, [api, session]);

  return orderCustomer;
}
