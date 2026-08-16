import type { AIAssistantApi } from "../ai-assistant/AIAssistant";
import type { DocumentsApi } from "../documents/Documents";
import type { EducationManagementApi } from "../education/EducationManagement";
import type { FollowListsApi } from "../follows/FollowLists";
import type { WarehouseApi } from "../inventory/Warehouse";
import type { MessagesApi } from "../messages/Messages";
import type { NotificationsApi } from "../notifications/Notifications";
import type { CashRegisterApi } from "./CashRegister";
import type { DebtLedgerApi } from "./DebtLedger";
import type { EducationStatisticsApi } from "./EducationStatistics";
import type { ExpensesApi } from "./Expenses";
import type { StaffManagementApi } from "./StaffManagement";
import type { StatisticsApi } from "./Statistics";
import type { BusinessProfileApi } from "./business-profile-api";

function hasMethods(api: BusinessProfileApi, methods: readonly string[]) {
  return methods.every(
    (method) => typeof api[method as keyof BusinessProfileApi] === "function",
  );
}

export function supportsFollowLists(
  api: BusinessProfileApi,
): api is BusinessProfileApi & FollowListsApi {
  return hasMethods(api, ["getFollowers", "getFollowing"]);
}

export function supportsAIAssistant(
  api: BusinessProfileApi,
): api is BusinessProfileApi & AIAssistantApi {
  return hasMethods(api, ["getAIChatHistory", "sendAIChatMessage"]);
}

export function supportsStaffManagement(
  api: BusinessProfileApi,
): api is BusinessProfileApi & StaffManagementApi {
  return hasMethods(api, [
    "getStaffSetup",
    "createStaffMember",
    "updateStaffMember",
    "fireStaffMember",
    "rehireStaffMember",
    "deleteStaffMember",
    "updateStaffAccess",
    "updateStaffSchedule",
    "createStaffProfession",
    "getStaffAttendance",
    "updateStaffAttendance",
  ]);
}

export function supportsCashRegister(
  api: BusinessProfileApi,
): api is BusinessProfileApi & CashRegisterApi {
  return hasMethods(api, [
    "getCashRegister",
    "getCashCatalog",
    "createCashReceipt",
    "deleteCashReceipt",
    "updateCashOrderPayment",
    "getDebtors",
    "createDebtor",
  ]);
}

export function supportsDebtLedger(
  api: BusinessProfileApi,
): api is BusinessProfileApi & DebtLedgerApi {
  return hasMethods(api, [
    "getDebtors",
    "createDebtor",
    "getDebtor",
    "addDebtTransaction",
  ]);
}

export function supportsExpenses(
  api: BusinessProfileApi,
): api is BusinessProfileApi & ExpensesApi {
  return hasMethods(api, [
    "getExpenses",
    "getExpenseCategories",
    "createExpenseCategory",
    "createExpense",
    "deleteExpense",
  ]);
}

export function supportsStatistics(
  api: BusinessProfileApi,
): api is BusinessProfileApi & StatisticsApi {
  return hasMethods(api, ["getStatistics", "getStatisticsNav"]);
}

export function supportsWarehouse(
  api: BusinessProfileApi,
): api is BusinessProfileApi & WarehouseApi {
  return hasMethods(api, [
    "getWarehouseItems",
    "createWarehouseMove",
    "deleteWarehouseMove",
    "getWarehouseMoves",
    "getWarehouseRecipe",
    "getWarehouseProduction",
  ]);
}

export function supportsDocuments(
  api: BusinessProfileApi,
): api is BusinessProfileApi & DocumentsApi {
  return hasMethods(api, [
    "getDocumentCounterparties",
    "createDocumentCounterparty",
    "updateDocumentCounterparty",
    "deleteDocumentCounterparty",
    "getDocuments",
    "getDocument",
    "createDocument",
    "updateDocument",
    "deleteDocument",
    "sendDocument",
    "respondDocument",
    "updateBusinessProfile",
  ]);
}

export function supportsEducationStatistics(
  api: BusinessProfileApi,
): api is BusinessProfileApi & EducationStatisticsApi {
  return typeof api.getEducationStatistics === "function";
}

export function supportsEducationManagement(
  api: BusinessProfileApi,
): api is BusinessProfileApi & EducationManagementApi {
  return hasMethods(api, [
    "getBusinessOnlineResource",
    "getEducationGroups",
    "createEducationGroup",
    "updateEducationGroup",
    "deleteEducationGroup",
    "getEducationStudents",
    "createEducationStudent",
    "updateEducationStudent",
    "deleteEducationStudent",
    "getEducationStudentCard",
    "transferEducationStudent",
    "getEducationAttendance",
    "saveEducationAttendance",
    "getEducationPaymentControl",
    "getEducationPayments",
    "createEducationPayment",
    "voidEducationPayment",
    "getEducationTeachers",
    "createEducationTeacher",
    "updateEducationTeacher",
    "deleteEducationTeacher",
    "getEducationPayroll",
    "createEducationPayroll",
    "deleteEducationPayroll",
  ]);
}

export function supportsMessages(
  api: BusinessProfileApi,
): api is BusinessProfileApi & MessagesApi {
  return hasMethods(api, [
    "getMessageConversations",
    "getMessageThread",
    "sendMessage",
    "sendMessageImage",
    "editMessage",
    "deleteMessage",
    "createUploadGrant",
    "uploadGrantedFile",
  ]);
}

export function supportsNotifications(
  api: BusinessProfileApi,
): api is BusinessProfileApi & NotificationsApi {
  return hasMethods(api, [
    "getNotifications",
    "getActionNotifications",
    "markNotificationRead",
    "markAllNotificationsRead",
    "getNotificationPreference",
    "saveNotificationPreference",
    "getNotificationFilters",
    "createNotificationFilter",
    "deleteNotificationFilter",
    "getPushStatus",
  ]);
}
