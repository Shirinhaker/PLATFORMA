import type { AuthContext } from "../auth/adapter";
import type {
  BusinessOnlineActionInput,
  BusinessOnlineMutationRead,
  BusinessOnlineRecord,
  BusinessOnlineResource,
  BusinessOnlineResourceRead,
} from "./business-online-types";
import type {
  AccountType,
  ApiErrorBody,
  Authenticated,
  BuildInfo,
  BusinessProfile,
  BusinessProfilePatch,
  CabinetSwitch,
  ChallengeResent,
  ChallengeStarted,
  ChallengeVerification,
  Me,
  OrderCreate,
  OrderCreateResponse,
  OrderChatRead,
  OrderMessageRead,
  OrderPaymentStatus,
  OrderProblemReason,
  OrderProblemSolution,
  OrderRead,
  OrderStatus,
  ProfileImageAttachment,
  PublicAdvertisement,
  PublicAdvertisementParams,
  PublicCatalogItem,
  PublicCatalogParams,
  PublicCatalogResponse,
  PublicDistrictOffersResponse,
  PublicFeatures,
  PublicFollowedProfile,
  PublicHomeMapParams,
  PublicHomeMapResponse,
  ListingCreate,
  ListingPatch,
  ListingRead,
  PublicProfileDetail,
  PublicSearchParams,
  PublicSearchResponse,
  PublicListingParams,
  RegistrationStart,
  ReverseGeocodeResult,
  SessionIdentity,
  UploadGrant,
  UploadGrantRequest,
  UserProfile,
  UserProfilePatch,
} from "./types";


type SessionResponse = Omit<SessionIdentity, "name"> & { name?: string };
type LoginStart = { login: string; password: string; cabinet_type?: AccountType };


export class ApiClientError extends Error {
  readonly code: string;
  readonly requestId: string;

  constructor(readonly status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiClientError";
    this.code = body.code;
    this.requestId = body.request_id;
  }
}


export class ApiClient {
  private csrfToken = "";

  constructor(
    private readonly baseUrl: string,
    private readonly fetcher: typeof fetch,
    private readonly auth: AuthContext,
  ) {}

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    authenticated = false,
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (this.auth.kind === "telegram") {
      headers["X-Telegram-Init-Data"] = this.auth.initData;
    }
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (authenticated && method !== "GET") {
      if (!this.csrfToken) {
        throw new ApiClientError(403, {
          code: "csrf_unavailable",
          message: "Sessiya xavfsizlik ma’lumoti topilmadi.",
          request_id: "",
        });
      }
      headers["X-CSRF-Token"] = this.csrfToken;
    }

    const response = await this.fetcher(
      `${this.baseUrl.replace(/\/+$/, "")}${path}`,
      {
        method,
        credentials: "include",
        headers,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      },
    );
    if (response.status === 204) return undefined as T;

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (!response.ok) {
      const fallback: ApiErrorBody = {
        code: "http_error",
        message: `API xatosi: ${response.status}`,
        request_id: "",
      };
      const error = payload && typeof payload === "object"
        ? { ...fallback, ...payload } as ApiErrorBody
        : fallback;
      throw new ApiClientError(response.status, error);
    }
    if (
      payload
      && typeof payload === "object"
      && "csrf_token" in payload
      && typeof payload.csrf_token === "string"
    ) {
      this.csrfToken = payload.csrf_token;
    }
    return payload as T;
  }

  getBuild(): Promise<BuildInfo> {
    return this.request("GET", "/api/v1/build");
  }

  searchPublic(params: PublicSearchParams = {}): Promise<PublicSearchResponse> {
    const query = new URLSearchParams();
    const textFilters = [
      ["q", params.q], ["result_type", params.result_type],
      ["direction", params.direction], ["activity_type", params.activity_type],
      ["region", params.region], ["district", params.district],
      ["mahalla", params.mahalla],
    ] as const;
    textFilters.forEach(([name, value]) => { if (value) query.set(name, value); });
    if (params.page !== undefined) query.set("page", String(params.page));
    if (params.page_size !== undefined) query.set("page_size", String(params.page_size));
    const suffix = query.size ? `?${query.toString()}` : "";
    return this.request("GET", `/api/v1/public/search${suffix}`);
  }

  getCatalogItems(params: PublicCatalogParams = {}): Promise<PublicCatalogResponse> {
    const query = new URLSearchParams();
    const textFilters = [
      ["kind", params.kind], ["q", params.q], ["direction", params.direction],
      ["activity_type", params.activity_type], ["region", params.region],
      ["district", params.district], ["mahalla", params.mahalla],
    ] as const;
    textFilters.forEach(([name, value]) => { if (value) query.set(name, value); });
    if (params.page !== undefined) query.set("page", String(params.page));
    if (params.page_size !== undefined) query.set("page_size", String(params.page_size));
    const suffix = query.size ? `?${query.toString()}` : "";
    return this.request("GET", `/api/v1/public/catalog/items${suffix}`);
  }

  getCatalogItem(publicId: string): Promise<PublicCatalogItem> {
    return this.request("GET", `/api/v1/public/catalog/items/${encodeURIComponent(publicId)}`);
  }

  getAdvertisements(params: PublicAdvertisementParams = {}): Promise<PublicAdvertisement[]> {
    const query = new URLSearchParams();
    for (const [name, value] of [
      ["placement", params.placement], ["region", params.region],
      ["district", params.district],
    ] as const) {
      if (value) query.set(name, value);
    }
    const suffix = query.size ? `?${query.toString()}` : "";
    return this.request("GET", `/api/v1/public/advertisements${suffix}`);
  }

  getListingCounts(): Promise<Record<string, number>> {
    return this.request("GET", "/api/v1/public/listings/counts");
  }

  getPublicListings(params: PublicListingParams = {}): Promise<ListingRead[]> {
    const query = new URLSearchParams();
    if (params.cat) query.set("cat", params.cat);
    if (params.q) query.set("q", params.q);
    const suffix = query.size ? `?${query.toString()}` : "";
    return this.request("GET", `/api/v1/public/listings${suffix}`);
  }

  getPublicListing(publicId: string): Promise<ListingRead> {
    return this.request(
      "GET",
      `/api/v1/public/listings/${encodeURIComponent(publicId)}`,
    );
  }

  getMyListings(): Promise<ListingRead[]> {
    return this.request("GET", "/api/v1/listings/mine", undefined, true);
  }

  createListing(body: ListingCreate): Promise<ListingRead> {
    return this.request("POST", "/api/v1/listings", body, true);
  }

  patchListing(publicId: string, body: ListingPatch): Promise<ListingRead> {
    return this.request(
      "PUT",
      `/api/v1/listings/${encodeURIComponent(publicId)}`,
      body,
      true,
    );
  }

  deleteListing(publicId: string): Promise<void> {
    return this.request(
      "DELETE",
      `/api/v1/listings/${encodeURIComponent(publicId)}`,
      undefined,
      true,
    );
  }

  toggleListingSave(publicId: string): Promise<{ saved: boolean }> {
    return this.request(
      "POST",
      `/api/v1/listings/${encodeURIComponent(publicId)}/save`,
      {},
      true,
    );
  }

  getSavedListings(): Promise<ListingRead[]> {
    return this.request("GET", "/api/v1/listings/saved", undefined, true);
  }

  getPublicFeatures(): Promise<PublicFeatures> {
    return this.request("GET", "/api/v1/public/features");
  }

  getHomeMap(params: PublicHomeMapParams): Promise<PublicHomeMapResponse> {
    const query = new URLSearchParams({ district: params.district });
    return this.request("GET", `/api/v1/public/home/map?${query.toString()}`);
  }

  getDistrictOffers(
    params: PublicHomeMapParams,
  ): Promise<PublicDistrictOffersResponse> {
    const query = new URLSearchParams({ district: params.district });
    return this.request(
      "GET",
      `/api/v1/public/home/district-offers?${query.toString()}`,
    );
  }

  getFollowedProfiles(): Promise<PublicFollowedProfile[]> {
    return this.request(
      "GET",
      "/api/v1/public/home/followed-profiles",
      undefined,
      true,
    );
  }

  getPublicProfile(
    kind: "user" | "business",
    publicId: string,
  ): Promise<PublicProfileDetail> {
    return this.request(
      "GET",
      `/api/v1/public/profiles/${kind}/${encodeURIComponent(publicId)}`,
    );
  }

  createOrder(body: OrderCreate): Promise<OrderCreateResponse> {
    return this.request("POST", "/api/v1/orders", body, true);
  }

  getMyOrders(): Promise<OrderRead[]> {
    return this.request("GET", "/api/v1/orders/my", undefined, true);
  }

  getOrderInbox(): Promise<OrderRead[]> {
    return this.request("GET", "/api/v1/orders/inbox", undefined, true);
  }

  markOrderSeen(orderId: number): Promise<OrderRead> {
    return this.request("PUT", `/api/v1/orders/${orderId}/seen`, {}, true);
  }

  changeOrderStatus(orderId: number, status: OrderStatus): Promise<OrderRead> {
    return this.request("PUT", `/api/v1/orders/${orderId}/status`, { status }, true);
  }

  submitOrderPayment(orderId: number): Promise<OrderRead> {
    return this.request("POST", `/api/v1/orders/${orderId}/payment/submit`, {}, true);
  }

  decideOrderPayment(orderId: number, status: OrderPaymentStatus): Promise<OrderRead> {
    return this.request("POST", `/api/v1/orders/${orderId}/payment`, { status }, true);
  }

  openOrderProblem(
    orderId: number,
    body: { reason: OrderProblemReason; note: string },
  ): Promise<OrderRead> {
    return this.request("POST", `/api/v1/orders/${orderId}/problem`, body, true);
  }

  chooseOrderProblemSolution(
    orderId: number,
    solution: OrderProblemSolution,
  ): Promise<OrderRead> {
    return this.request(
      "PUT",
      `/api/v1/orders/${orderId}/problem/solution`,
      { solution },
      true,
    );
  }

  handoffOrder(orderId: number): Promise<OrderRead> {
    return this.request("POST", `/api/v1/orders/${orderId}/handoff`, {}, true);
  }

  receiveOrder(orderId: number): Promise<OrderRead> {
    return this.request("POST", `/api/v1/orders/${orderId}/received`, {}, true);
  }

  getOrderChat(orderId: number): Promise<OrderChatRead> {
    return this.request("GET", `/api/v1/orders/${orderId}/chat`, undefined, true);
  }

  sendOrderChatMessage(
    orderId: number,
    body: { text: string; reply_to_id: number | null },
  ): Promise<OrderMessageRead> {
    return this.request("POST", `/api/v1/orders/${orderId}/chat`, body, true);
  }

  sendOrderChatImage(
    orderId: number,
    body: { object_key: string; file_name: string; text?: string; reply_to_id?: number | null },
  ): Promise<OrderMessageRead> {
    return this.request("POST", `/api/v1/orders/${orderId}/chat/image`, body, true);
  }

  editOrderChatMessage(
    orderId: number,
    messageId: number,
    text: string,
  ): Promise<OrderMessageRead> {
    return this.request(
      "PUT",
      `/api/v1/orders/${orderId}/chat/${messageId}`,
      { text },
      true,
    );
  }

  deleteOrderChatMessage(orderId: number, messageId: number): Promise<OrderMessageRead> {
    return this.request(
      "DELETE",
      `/api/v1/orders/${orderId}/chat/${messageId}`,
      undefined,
      true,
    );
  }

  recordAdvertisementViews(publicIds: string[]): Promise<void> {
    return this.request(
      "POST",
      "/api/v1/public/advertisements/views",
      { ids: publicIds },
    );
  }

  recordAdvertisementClick(publicId: string): Promise<void> {
    return this.request(
      "POST",
      `/api/v1/public/advertisements/${encodeURIComponent(publicId)}/click`,
    );
  }

  startRegistration(body: RegistrationStart): Promise<ChallengeStarted> {
    return this.request("POST", "/api/v1/auth/register/start", body);
  }

  verifyRegistration(body: ChallengeVerification): Promise<Authenticated> {
    return this.request("POST", "/api/v1/auth/register/verify", body);
  }

  startLogin(body: LoginStart): Promise<ChallengeStarted> {
    return this.request("POST", "/api/v1/auth/login/start", body);
  }

  verifyLogin(body: ChallengeVerification): Promise<Authenticated> {
    return this.request("POST", "/api/v1/auth/login/verify", body);
  }

  resendChallenge(requestId: number): Promise<ChallengeResent> {
    return this.request("POST", `/api/v1/auth/challenges/${requestId}/resend`);
  }

  async getSession(): Promise<SessionIdentity> {
    const session = await this.request<SessionResponse>("GET", "/api/v1/auth/session");
    if (typeof session.name === "string") return session as SessionIdentity;
    const me = await this.getMe();
    return { ...session, name: me.name };
  }

  async logout(): Promise<void> {
    await this.request<void>("POST", "/api/v1/auth/logout", undefined, true);
    this.csrfToken = "";
  }

  getMe(): Promise<Me> {
    return this.request("GET", "/api/v1/me", undefined, true);
  }

  getUserProfile(): Promise<UserProfile> {
    return this.request("GET", "/api/v1/user-profile", undefined, true);
  }

  updateUserProfile(body: UserProfilePatch): Promise<UserProfile> {
    return this.request("PUT", "/api/v1/user-profile", body, true);
  }

  getBusinessProfile(): Promise<BusinessProfile> {
    return this.request("GET", "/api/v1/business-profile", undefined, true);
  }

  updateBusinessProfile(body: BusinessProfilePatch): Promise<BusinessProfile> {
    return this.request("PUT", "/api/v1/business-profile", body, true);
  }

  reverseGeocode(
    latitude: number,
    longitude: number,
  ): Promise<ReverseGeocodeResult> {
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

  switchCabinet(targetType: AccountType): Promise<CabinetSwitch> {
    return this.request(
      "POST",
      "/api/v1/cabinet/switch",
      { target_type: targetType },
      true,
    );
  }

  createUploadGrant(body: UploadGrantRequest): Promise<UploadGrant> {
    return this.request("POST", "/api/v1/media/upload-grants", body, true);
  }

  async uploadGrantedFile(grant: UploadGrant, file: File): Promise<void> {
    const response = await this.fetcher(grant.upload_url, {
      method: grant.method,
      credentials: "omit",
      headers: grant.headers,
      body: file,
    });
    if (!response.ok) throw new Error("Rasm obyekt saqlash xizmatiga yuklanmadi.");
  }

  attachUserAvatar(body: ProfileImageAttachment): Promise<UserProfile> {
    return this.request("PUT", "/api/v1/user-profile/avatar", body, true);
  }

  attachBusinessLogo(body: ProfileImageAttachment): Promise<BusinessProfile> {
    return this.request("PUT", "/api/v1/business-profile/logo", body, true);
  }

  attachBusinessPaymentQr(body: { object_key: string }): Promise<BusinessProfile> {
    return this.request("PUT", "/api/v1/business-profile/payment-qr", body, true);
  }
}

export type { BuildInfo } from "./types";
