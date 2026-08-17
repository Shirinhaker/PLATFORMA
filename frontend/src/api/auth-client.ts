// Kirish, ro'yxatdan o'tish va seans.
//
// `client.ts` dan ajratildi. Chaqiruv joylari o'zgarmadi: `ApiClient`
// bu obyektni `Object.assign` bilan o'ziga qo'shadi.

import { ApiTransport } from "./http";
import type {
  AccountType,
  Authenticated,
  CabinetSwitch,
  ChallengeResent,
  ChallengeStarted,
  ChallengeVerification,
  Me,
  RegistrationStart,
  SessionIdentity,
} from "./types";

// `client.ts` da e'lon qilingan lokal tur taxalluslari — shu domenga tegishli.
type SessionResponse = Omit<SessionIdentity, "name"> & { name?: string };
type LoginStart = { login: string; password: string; cabinet_type?: AccountType };

export function createAuthClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  const client = {
    startLogin(body: LoginStart): Promise<ChallengeStarted> {
      return request("POST", "/api/v1/auth/login/start", body);
    },

    verifyLogin(body: ChallengeVerification): Promise<Authenticated> {
      return request("POST", "/api/v1/auth/login/verify", body);
    },

    startRegistration(body: RegistrationStart): Promise<ChallengeStarted> {
      return request("POST", "/api/v1/auth/register/start", body);
    },

    verifyRegistration(body: ChallengeVerification): Promise<Authenticated> {
      return request("POST", "/api/v1/auth/register/verify", body);
    },

    resendChallenge(requestId: number): Promise<ChallengeResent> {
      return request("POST", `/api/v1/auth/challenges/${requestId}/resend`);
    },

    async logout(): Promise<void> {
      await request<void>("POST", "/api/v1/auth/logout", undefined, true);
      transport.clearCsrfToken();
    },

    async getSession(): Promise<SessionIdentity> {
      const session = await request<SessionResponse>("GET", "/api/v1/auth/session");
      if (typeof session.name === "string") return session as SessionIdentity;
      const me = await client.getMe();
      return { ...session, name: me.name };
    },

    getMe(): Promise<Me> {
      return request("GET", "/api/v1/me", undefined, true);
    },

    loginStaff(body: {
      firm_login: string;
      login: string;
      password: string;
    }): Promise<SessionIdentity> {
      return request("POST", "/api/v1/staff-auth/login", body);
    },

    switchCabinet(targetType: AccountType): Promise<CabinetSwitch> {
      return request(
        "POST",
        "/api/v1/cabinet/switch",
        { target_type: targetType },
        true,
      );
    },
  };

  return client;
}

export type AuthClient = ReturnType<typeof createAuthClient>;
