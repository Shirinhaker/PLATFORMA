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
  CashCatalogItem,
  CashPayType,
  CashReceipt,
  CashReceiptCreate,
  CashReceiptCreated,
  CashRegister,
  DebtMutation,
  DebtTransactionCreate,
  Debtor,
  DebtorCreate,
  DebtorDetail,
  BusinessQueueEntry,
  BusinessQueueOfflineCreate,
  BusinessQueueProvider,
  BusinessQueueProviderWrite,
  BusinessQueueSetup,
  CabinetSwitch,
  ChallengeResent,
  ChallengeStarted,
  ChallengeVerification,
  CourseEnrollmentCreate,
  CourseEnrollmentCreated,
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
  StaffAccessWrite,
  StaffAttendance,
  StaffMember,
  StaffMemberWrite,
  StaffSchedule,
  StaffSetup,
  UploadGrant,
  UploadGrantRequest,
  UserProfile,
  UserProfilePatch,
  QueueEntryStatus,
  QueueCreate,
  QueueOptions,
  QueueNotificationRead,
  QueueSlots,
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

  getQueueOptions(
    businessPublicId: string,
    itemPublicId: string,
    queueDate: string,
  ): Promise<QueueOptions> {
    const query = new URLSearchParams({
      business_public_id: businessPublicId,
      item_public_id: itemPublicId,
      queue_date: queueDate,
    });
    return this.request("GET", `/api/v1/queues/options?${query.toString()}`);
  }

  getQueueSlots(
    businessPublicId: string,
    itemPublicId: string,
    providerId: number,
    queueDate: string,
  ): Promise<QueueSlots> {
    const query = new URLSearchParams({
      business_public_id: businessPublicId,
      item_public_id: itemPublicId,
      provider_id: String(providerId),
      queue_date: queueDate,
    });
    return this.request("GET", `/api/v1/queues/slots?${query.toString()}`);
  }

  createQueue(body: QueueCreate): Promise<BusinessQueueEntry> {
    return this.request("POST", "/api/v1/queues", body, true);
  }

  createCourseEnrollment(
    body: CourseEnrollmentCreate,
  ): Promise<CourseEnrollmentCreated> {
    return this.request(
      "POST",
      "/api/v1/education/enrollments",
      body,
      true,
    );
  }

  getMyQueues(): Promise<BusinessQueueEntry[]> {
    return this.request("GET", "/api/v1/queues/mine", undefined, true);
  }

  cancelMyQueue(queueId: number): Promise<BusinessQueueEntry> {
    return this.request(
      "POST",
      `/api/v1/queues/${queueId}/cancel`,
      undefined,
      true,
    );
  }

  markQueueNotificationRead(notificationId: number): Promise<QueueNotificationRead> {
    return this.request(
      "POST",
      `/api/v1/queues/notifications/${notificationId}/read`,
      undefined,
      true,
    );
  }

  getBusinessQueueSetup(): Promise<BusinessQueueSetup> {
    return this.request(
      "GET",
      "/api/v1/queues/business/setup",
      undefined,
      true,
    );
  }

  getBusinessQueueProviders(): Promise<BusinessQueueProvider[]> {
    return this.request(
      "GET",
      "/api/v1/queues/business/providers",
      undefined,
      true,
    );
  }

  createBusinessQueueProvider(
    body: BusinessQueueProviderWrite,
  ): Promise<BusinessQueueProvider> {
    return this.request(
      "POST",
      "/api/v1/queues/business/providers",
      body,
      true,
    );
  }

  updateBusinessQueueProvider(
    providerId: number,
    body: BusinessQueueProviderWrite,
  ): Promise<BusinessQueueProvider> {
    return this.request(
      "PUT",
      `/api/v1/queues/business/providers/${providerId}`,
      body,
      true,
    );
  }

  getBusinessQueueEntries(queueDate: string): Promise<BusinessQueueEntry[]> {
    const query = new URLSearchParams({ queue_date: queueDate });
    return this.request(
      "GET",
      `/api/v1/queues/business/entries?${query.toString()}`,
      undefined,
      true,
    );
  }

  createBusinessOfflineQueue(
    body: BusinessQueueOfflineCreate,
  ): Promise<BusinessQueueEntry> {
    return this.request(
      "POST",
      "/api/v1/queues/business/entries",
      body,
      true,
    );
  }

  changeBusinessQueueStatus(
    queueId: number,
    status: QueueEntryStatus,
  ): Promise<BusinessQueueEntry> {
    return this.request(
      "PUT",
      `/api/v1/queues/business/entries/${queueId}/status`,
      { status },
      true,
    );
  }

  swapBusinessQueues(
    queueId: number,
    otherQueueId: number,
  ): Promise<BusinessQueueEntry> {
    return this.request(
      "POST",
      `/api/v1/queues/business/entries/${queueId}/swap`,
      { other_queue_id: otherQueueId },
      true,
    );
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

  decideOrderPayment(
    orderId: number,
    status: OrderPaymentStatus,
    debtorId: number | null = null,
  ): Promise<OrderRead> {
    return this.request(
      "POST",
      `/api/v1/orders/${orderId}/payment`,
      { status, ...(debtorId ? { debtor_id: debtorId } : {}) },
      true,
    );
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

  loginStaff(body: {
    firm_login: string;
    login: string;
    password: string;
  }): Promise<SessionIdentity> {
    return this.request("POST", "/api/v1/staff-auth/login", body);
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

  getCashRegister(day = ""): Promise<CashRegister> {
    const suffix = day ? `?day=${encodeURIComponent(day)}` : "";
    return this.request("GET", `/api/v1/cash-register${suffix}`, undefined, true);
  }

  getCashCatalog(): Promise<CashCatalogItem[]> {
    return this.request("GET", "/api/v1/cash-register/catalog", undefined, true);
  }

  createCashReceipt(body: CashReceiptCreate): Promise<CashReceiptCreated> {
    return this.request("POST", "/api/v1/cash-register/receipts", body, true);
  }

  deleteCashReceipt(receiptId: number): Promise<void> {
    return this.request(
      "DELETE",
      `/api/v1/cash-register/receipts/${receiptId}`,
      undefined,
      true,
    );
  }

  updateCashOrderPayment(
    receiptId: number,
    payType: CashPayType,
    debtorId: number | null = null,
  ): Promise<CashReceipt> {
    return this.request(
      "PUT",
      `/api/v1/cash-register/receipts/${receiptId}/payment`,
      { pay_type: payType, ...(debtorId ? { debtor_id: debtorId } : {}) },
      true,
    );
  }

  getDebtors(): Promise<Debtor[]> {
    return this.request("GET", "/api/v1/debt-ledger/debtors", undefined, true);
  }

  createDebtor(body: DebtorCreate): Promise<{ id: number }> {
    return this.request("POST", "/api/v1/debt-ledger/debtors", body, true);
  }

  getDebtor(debtorId: number): Promise<DebtorDetail> {
    return this.request(
      "GET",
      `/api/v1/debt-ledger/debtors/${debtorId}`,
      undefined,
      true,
    );
  }

  addDebtTransaction(
    debtorId: number,
    body: DebtTransactionCreate,
  ): Promise<DebtMutation> {
    return this.request(
      "POST",
      `/api/v1/debt-ledger/debtors/${debtorId}/transactions`,
      body,
      true,
    );
  }

  getStaffSetup(): Promise<StaffSetup> {
    return this.request("GET", "/api/v1/staff", undefined, true);
  }

  createStaffMember(body: StaffMemberWrite): Promise<StaffMember> {
    return this.request("POST", "/api/v1/staff", body, true);
  }

  updateStaffMember(staffId: number, body: Partial<StaffMemberWrite>): Promise<StaffMember> {
    return this.request("PUT", `/api/v1/staff/${staffId}`, body, true);
  }

  fireStaffMember(staffId: number): Promise<StaffMember> {
    return this.request("POST", `/api/v1/staff/${staffId}/fire`, undefined, true);
  }

  rehireStaffMember(staffId: number): Promise<StaffMember> {
    return this.request("POST", `/api/v1/staff/${staffId}/rehire`, undefined, true);
  }

  deleteStaffMember(staffId: number): Promise<void> {
    return this.request("DELETE", `/api/v1/staff/${staffId}`, undefined, true);
  }

  updateStaffAccess(staffId: number, body: StaffAccessWrite): Promise<StaffMember> {
    return this.request("PUT", `/api/v1/staff/${staffId}/access`, body, true);
  }

  updateStaffSchedule(staffId: number, schedule: StaffSchedule): Promise<StaffMember> {
    return this.request(
      "PUT",
      `/api/v1/staff/${staffId}/schedule`,
      { schedule },
      true,
    );
  }

  createStaffProfession(name: string): Promise<{ professions: string[] }> {
    return this.request("POST", "/api/v1/staff/professions", { name }, true);
  }

  getStaffAttendance(day: string): Promise<StaffAttendance> {
    const query = new URLSearchParams({ day });
    return this.request("GET", `/api/v1/staff/attendance?${query.toString()}`, undefined, true);
  }

  updateStaffAttendance(
    staffId: number,
    body: { date: string; status: string; time_in: string; time_out: string },
  ): Promise<StaffAttendance> {
    return this.request("PUT", `/api/v1/staff/${staffId}/attendance`, body, true);
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
