// Foydalanuvchi va biznes profillari, rasm biriktirish.
//
// `client.ts` dan ajratildi. Chaqiruv joylari o'zgarmadi: `ApiClient`
// bu obyektni `Object.assign` bilan o'ziga qo'shadi.

import { ApiTransport } from "./http";
import type {
  BusinessCredentials,
  BusinessCredentialsUpdate,
  BusinessOpeningRead,
  BusinessOpeningWrite,
  BusinessProfile,
  BusinessProfilePatch,
  ProfileImageAttachment,
  UserProfile,
  UserProfilePatch,
} from "./types";

export function createProfilesClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  return {
    getUserProfile(): Promise<UserProfile> {
      return request("GET", "/api/v1/user-profile", undefined, true);
    },

    updateUserProfile(body: UserProfilePatch): Promise<UserProfile> {
      return request("PUT", "/api/v1/user-profile", body, true);
    },

    getBusinessProfile(): Promise<BusinessProfile> {
      return request("GET", "/api/v1/business-profile", undefined, true);
    },

    updateBusinessProfile(body: BusinessProfilePatch): Promise<BusinessProfile> {
      return request("PUT", "/api/v1/business-profile", body, true);
    },

    attachUserAvatar(body: ProfileImageAttachment): Promise<UserProfile> {
      return request("PUT", "/api/v1/user-profile/avatar", body, true);
    },

    attachBusinessLogo(body: ProfileImageAttachment): Promise<BusinessProfile> {
      return request("PUT", "/api/v1/business-profile/logo", body, true);
    },

    attachBusinessPaymentQr(body: { object_key: string }): Promise<BusinessProfile> {
      return request("PUT", "/api/v1/business-profile/payment-qr", body, true);
    },

    getBusinessCredentials(): Promise<BusinessCredentials> {
      return request(
        "GET",
        "/api/v1/account-settings/business-credentials",
        undefined,
        true,
      );
    },

    updateBusinessCredentials(
      body: BusinessCredentialsUpdate,
    ): Promise<BusinessCredentials> {
      return request(
        "PUT",
        "/api/v1/account-settings/business-credentials",
        body,
        true,
      );
    },

    openBusiness(body: BusinessOpeningWrite): Promise<BusinessOpeningRead> {
      return request("POST", "/api/v1/business-opening", body, true);
    },
  };
}

export type ProfilesClient = ReturnType<typeof createProfilesClient>;
