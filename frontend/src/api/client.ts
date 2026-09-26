import type { AuthContext } from "../auth/adapter";
import {
  createBusinessOperationsClient,
  type BusinessOperationsClient,
} from "./business-operations-client";
import { createDiningClient, type DiningClient } from "./dining-client";
import { createEducationClient, type EducationClient } from "./education-client";
import { ApiTransport } from "./http";
import { createListingsClient, type ListingsClient } from "./listings-client";
import { createAuthClient, type AuthClient } from "./auth-client";
import { createProfilesClient, type ProfilesClient } from "./profiles-client";
import { createPaymentsClient, type PaymentsClient } from "./payments-client";
import { createOrdersClient, type OrdersClient } from "./orders-client";
import { createQueuesClient, type QueuesClient } from "./queues-client";
import { createPublicClient, type PublicClient } from "./public-client";
import { createSocialClient, type SocialClient } from "./social-client";
import { createStaffClient, type StaffClient } from "./staff-client";
import type {
  BusinessOnlineActionInput,
  BusinessOnlineMutationRead,
  BusinessOnlineRecord,
  BusinessOnlineResource,
  BusinessOnlineResourceRead,
} from "./business-online-types";
import type {
  AccountType,
  Authenticated,
  BuildInfo,
  BusinessSubscriptionSummary,
  BusinessCredentials,
  BusinessCredentialsUpdate,
  BusinessOpeningRead,
  BusinessOpeningWrite,
  BusinessProfile,
  BusinessProfilePatch,
  CabinetSwitch,
  ChallengeResent,
  ChallengeStarted,
  ChallengeVerification,
  Me,
  PaymentCatalog,
  PaymentReceiptRef,
  PaymentRequestBody,
  PaymentRequestRecord,
  ProfileImageAttachment,
  RegistrationStart,
  ReverseGeocodeResult,
  SessionIdentity,
  AIChatHistory,
  AIChatAnswer,
  AIStatus,
  AIDocumentDraft,
  AIDocumentDraftRequest,
  AIDocumentQuestion,
  SpecialistOfferWrite,
  SpecialistProfile,
  SpecialistProfileWrite,
  UploadGrant,
  UploadGrantRequest,
  UserProfile,
  UserProfilePatch,
  TaxiDriver,
  TaxiDriverRides,
  TaxiDriverWrite,
  TaxiMyRides,
  TaxiPricing,
  TaxiRide,
  TaxiRideAccepted,
  TaxiRideCreate,
  TaxiRideMutation,
} from "./types";
import type {
  Advertisement,
  AdvertisementCreate,
  AdvertisementQuote,
  AdvertisementQuoteRequest,
  AdvertisementRates,
} from "./advertisement-types";

export { ApiClientError } from "./http";

type SessionResponse = Omit<SessionIdentity, "name"> & { name?: string };
type LoginStart = { login: string; password: string; cabinet_type?: AccountType };

export class ApiClient {
  private readonly transport: ApiTransport;

  constructor(baseUrl: string, fetcher: typeof fetch, auth: AuthContext) {
    this.transport = new ApiTransport(baseUrl, fetcher, auth);
    Object.assign(this, createAuthClient(this.transport));
    Object.assign(this, createProfilesClient(this.transport));
    Object.assign(this, createPaymentsClient(this.transport));
    Object.assign(this, createBusinessOperationsClient(this.transport));
    Object.assign(this, createDiningClient(this.transport));
    Object.assign(this, createEducationClient(this.transport));
    Object.assign(this, createListingsClient(this.transport));
    Object.assign(this, createOrdersClient(this.transport));
    Object.assign(this, createQueuesClient(this.transport));
    Object.assign(this, createPublicClient(this.transport));
    Object.assign(this, createSocialClient(this.transport));
    Object.assign(this, createStaffClient(this.transport));
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    authenticated = false,
  ): Promise<T> {
    return this.transport.request(method, path, body, authenticated);
  }

  getBuild(): Promise<BuildInfo> {
    return this.request("GET", "/api/v1/build");
  }

  getMySpecialist(): Promise<SpecialistProfile> {
    return this.request("GET", "/api/v1/specialists/me", undefined, true);
  }

  updateMySpecialist(body: SpecialistProfileWrite): Promise<SpecialistProfile> {
    return this.request("PUT", "/api/v1/specialists/me", body, true);
  }

  addSpecialistCredential(objectKey: string): Promise<{ ok: true; id: number }> {
    return this.request(
      "POST",
      "/api/v1/specialists/me/credentials",
      { object_key: objectKey },
      true,
    );
  }

  deleteSpecialistCredential(id: number): Promise<void> {
    return this.request(
      "DELETE",
      `/api/v1/specialists/me/credentials/${id}`,
      undefined,
      true,
    );
  }

  createSpecialistOffer(body: SpecialistOfferWrite): Promise<{ ok: true; id: number }> {
    return this.request("POST", "/api/v1/specialists/me/offers", body, true);
  }

  updateSpecialistOffer(id: number, body: SpecialistOfferWrite): Promise<{ ok: true }> {
    return this.request("PUT", `/api/v1/specialists/me/offers/${id}`, body, true);
  }

  deleteSpecialistOffer(id: number): Promise<void> {
    return this.request(
      "DELETE",
      `/api/v1/specialists/me/offers/${id}`,
      undefined,
      true,
    );
  }

  addSpecialistPortfolio(body: {
    media_type: "photo" | "video";
    object_key: string;
  }): Promise<{ ok: true; id: number }> {
    return this.request("POST", "/api/v1/specialists/me/portfolio", body, true);
  }

  deleteSpecialistPortfolio(id: number): Promise<void> {
    return this.request(
      "DELETE",
      `/api/v1/specialists/me/portfolio/${id}`,
      undefined,
      true,
    );
  }

  reverseGeocode(latitude: number, longitude: number): Promise<ReverseGeocodeResult> {
    const query = new URLSearchParams({
      lat: String(latitude),
      lng: String(longitude),
    });
    return this.request("GET", `/api/geocode?${query.toString()}`);
  }

  getBusinessOnlineResource(
    resource: BusinessOnlineResource,
  ): Promise<BusinessOnlineResourceRead> {
    return this.request(
      "GET",
      `/api/v1/business-online/${encodeURIComponent(resource)}`,
      undefined,
      true,
    );
  }

  createBusinessOnlineRecord(
    resource: BusinessOnlineResource,
    record: BusinessOnlineRecord,
  ): Promise<BusinessOnlineMutationRead> {
    return this.request(
      "POST",
      `/api/v1/business-online/${encodeURIComponent(resource)}`,
      { record },
      true,
    );
  }

  patchBusinessOnlineRecord(
    resource: BusinessOnlineResource,
    recordId: number | string,
    patch: BusinessOnlineRecord,
  ): Promise<BusinessOnlineMutationRead> {
    return this.request(
      "PUT",
      `/api/v1/business-online/${encodeURIComponent(resource)}/${encodeURIComponent(String(recordId))}`,
      { patch },
      true,
    );
  }

  deleteBusinessOnlineRecord(
    resource: BusinessOnlineResource,
    recordId: number | string,
  ): Promise<BusinessOnlineMutationRead> {
    return this.request(
      "DELETE",
      `/api/v1/business-online/${encodeURIComponent(resource)}/${encodeURIComponent(String(recordId))}`,
      undefined,
      true,
    );
  }

  applyBusinessOnlineAction(
    resource: BusinessOnlineResource,
    action: string,
    body: BusinessOnlineActionInput = {},
  ): Promise<BusinessOnlineMutationRead> {
    return this.request(
      "POST",
      `/api/v1/business-online/${encodeURIComponent(resource)}/actions/${encodeURIComponent(action)}`,
      { record_id: body.record_id, payload: body.payload ?? {} },
      true,
    );
  }

  createUploadGrant(body: UploadGrantRequest): Promise<UploadGrant> {
    return this.request("POST", "/api/v1/media/upload-grants", body, true);
  }

  async uploadGrantedFile(grant: UploadGrant, file: File): Promise<void> {
    await this.transport.uploadFile(
      grant.upload_url,
      grant.method,
      grant.headers,
      file,
    );
  }

  getAIChatHistory(limit = 30): Promise<AIChatHistory> {
    return this.request("GET", `/api/v1/ai-assistant/history?limit=${limit}`);
  }

  sendAIChatMessage(message: string): Promise<AIChatAnswer> {
    return this.request("POST", "/api/v1/ai-assistant/chat", { message }, true);
  }

  askAIDocument(body: AIDocumentQuestion): Promise<AIChatAnswer> {
    return this.request("POST", "/api/v1/ai-assistant/documents/question", body, true);
  }

  getAIStatus(): Promise<AIStatus> {
    return this.request("GET", "/api/v1/ai-assistant/status");
  }

  generateAIDocumentDraft(body: AIDocumentDraftRequest): Promise<AIDocumentDraft> {
    return this.request("POST", "/api/v1/ai-assistant/documents/draft", body, true);
  }

  getTaxiPricing(): Promise<TaxiPricing> {
    return this.request("GET", "/api/v1/taxi/pricing", undefined, true);
  }

  getTaxiDriver(): Promise<TaxiDriver> {
    return this.request("GET", "/api/v1/taxi/driver", undefined, true);
  }

  saveTaxiDriver(body: TaxiDriverWrite): Promise<TaxiDriver> {
    return this.request("POST", "/api/v1/taxi/driver", body, true);
  }

  setTaxiDriverAvailable(available: boolean): Promise<TaxiDriver> {
    return this.request("PUT", "/api/v1/taxi/driver/available", { available }, true);
  }

  createTaxiRide(body: TaxiRideCreate): Promise<TaxiRide> {
    return this.request("POST", "/api/v1/taxi/rides", body, true);
  }

  getMyTaxiRides(): Promise<TaxiMyRides> {
    return this.request("GET", "/api/v1/taxi/rides/my", undefined, true);
  }

  cancelTaxiRide(rideId: number): Promise<TaxiRideMutation> {
    return this.request("POST", `/api/v1/taxi/rides/${rideId}/cancel`, undefined, true);
  }

  getPendingTaxiRides(): Promise<TaxiDriverRides> {
    return this.request("GET", "/api/v1/taxi/rides/pending", undefined, true);
  }

  acceptTaxiRide(rideId: number): Promise<TaxiRideAccepted> {
    return this.request("POST", `/api/v1/taxi/rides/${rideId}/accept`, undefined, true);
  }

  setTaxiRideStatus(
    rideId: number,
    status: TaxiRide["status"],
  ): Promise<TaxiRideMutation> {
    return this.request(
      "POST",
      `/api/v1/taxi/rides/${rideId}/status`,
      { status },
      true,
    );
  }

  updateTaxiRideProgress(rideId: number, km: number): Promise<TaxiRide> {
    return this.request("POST", `/api/v1/taxi/rides/${rideId}/progress`, { km }, true);
  }

  getAdvertisementRates(): Promise<AdvertisementRates> {
    return this.request("GET", "/api/v1/advertisements/rates", undefined, true);
  }

  quoteAdvertisement(body: AdvertisementQuoteRequest): Promise<AdvertisementQuote> {
    return this.request("POST", "/api/v1/advertisements/price", body, true);
  }

  createAdvertisement(body: AdvertisementCreate): Promise<Advertisement> {
    return this.request("POST", "/api/v1/advertisements", body, true);
  }

  getMyAdvertisements(): Promise<Advertisement[]> {
    return this.request("GET", "/api/v1/advertisements/my", undefined, true);
  }

  deleteAdvertisement(advertisementId: number): Promise<void> {
    return this.request(
      "DELETE",
      `/api/v1/advertisements/${advertisementId}`,
      undefined,
      true,
    );
  }
}

export interface ApiClient
  extends
    AuthClient,
    ProfilesClient,
    PaymentsClient,
    BusinessOperationsClient,
    DiningClient,
    EducationClient,
    ListingsClient,
    OrdersClient,
    QueuesClient,
    PublicClient,
    SocialClient,
    StaffClient {}

export type { BuildInfo } from "./types";
