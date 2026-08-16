import type { ApiTransport } from "./http";
import type {
  BusinessDocument,
  BusinessDocumentList,
  BusinessDocumentWrite,
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
  DocumentCounterpartyList,
  DocumentCounterpartyWrite,
  DocumentDirection,
  ExpenseCategories,
  ExpenseCategoryCreate,
  ExpenseCreate,
  ExpenseDay,
  StatisticsPeriod,
  StatisticsReport,
  WarehouseItem,
  WarehouseList,
  WarehouseMove,
  WarehouseMoveCreate,
  WarehouseMoveResult,
  WarehouseProductionBatch,
  WarehouseRecipeIngredient,
} from "./types";

export function createBusinessOperationsClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  return {
    getCashRegister(day = ""): Promise<CashRegister> {
      const suffix = day ? `?day=${encodeURIComponent(day)}` : "";
      return request("GET", `/api/v1/cash-register${suffix}`, undefined, true);
    },

    getCashCatalog(): Promise<CashCatalogItem[]> {
      return request("GET", "/api/v1/cash-register/catalog", undefined, true);
    },

    createCashReceipt(body: CashReceiptCreate): Promise<CashReceiptCreated> {
      return request("POST", "/api/v1/cash-register/receipts", body, true);
    },

    deleteCashReceipt(receiptId: number): Promise<void> {
      return request(
        "DELETE",
        `/api/v1/cash-register/receipts/${receiptId}`,
        undefined,
        true,
      );
    },

    updateCashOrderPayment(
      receiptId: number,
      payType: CashPayType,
      debtorId: number | null = null,
    ): Promise<CashReceipt> {
      return request(
        "PUT",
        `/api/v1/cash-register/receipts/${receiptId}/payment`,
        { pay_type: payType, ...(debtorId ? { debtor_id: debtorId } : {}) },
        true,
      );
    },

    getDebtors(): Promise<Debtor[]> {
      return request("GET", "/api/v1/debt-ledger/debtors", undefined, true);
    },

    createDebtor(body: DebtorCreate): Promise<{ id: number }> {
      return request("POST", "/api/v1/debt-ledger/debtors", body, true);
    },

    getDebtor(debtorId: number): Promise<DebtorDetail> {
      return request("GET", `/api/v1/debt-ledger/debtors/${debtorId}`, undefined, true);
    },

    addDebtTransaction(
      debtorId: number,
      body: DebtTransactionCreate,
    ): Promise<DebtMutation> {
      return request(
        "POST",
        `/api/v1/debt-ledger/debtors/${debtorId}/transactions`,
        body,
        true,
      );
    },

    getExpenses(day = ""): Promise<ExpenseDay> {
      const suffix = day ? `?day=${encodeURIComponent(day)}` : "";
      return request("GET", `/api/v1/expenses${suffix}`, undefined, true);
    },

    getExpenseCategories(): Promise<ExpenseCategories> {
      return request("GET", "/api/v1/expenses/categories", undefined, true);
    },

    createExpenseCategory(
      body: ExpenseCategoryCreate,
    ): Promise<{ ok: true; exists: boolean }> {
      return request("POST", "/api/v1/expenses/categories", body, true);
    },

    createExpense(body: ExpenseCreate): Promise<{ id: number }> {
      return request("POST", "/api/v1/expenses", body, true);
    },

    deleteExpense(expenseId: number): Promise<void> {
      return request("DELETE", `/api/v1/expenses/${expenseId}`, undefined, true);
    },

    getDocumentCounterparties(): Promise<DocumentCounterpartyList> {
      return request("GET", "/api/v1/documents/counterparties", undefined, true);
    },

    createDocumentCounterparty(
      body: DocumentCounterpartyWrite,
    ): Promise<{ ok: true; id: number }> {
      return request("POST", "/api/v1/documents/counterparties", body, true);
    },

    updateDocumentCounterparty(
      counterpartyId: number,
      body: DocumentCounterpartyWrite,
    ): Promise<{ ok: true }> {
      return request(
        "PUT",
        `/api/v1/documents/counterparties/${counterpartyId}`,
        body,
        true,
      );
    },

    deleteDocumentCounterparty(counterpartyId: number): Promise<void> {
      return request(
        "DELETE",
        `/api/v1/documents/counterparties/${counterpartyId}`,
        undefined,
        true,
      );
    },

    getDocuments(direction?: DocumentDirection): Promise<BusinessDocumentList> {
      const suffix = direction ? `?direction=${encodeURIComponent(direction)}` : "";
      return request("GET", `/api/v1/documents${suffix}`, undefined, true);
    },

    getDocument(documentId: number): Promise<BusinessDocument> {
      return request("GET", `/api/v1/documents/${documentId}`, undefined, true);
    },

    createDocument(body: BusinessDocumentWrite): Promise<{ ok: true; id: number }> {
      return request("POST", "/api/v1/documents", body, true);
    },

    updateDocument(
      documentId: number,
      body: BusinessDocumentWrite,
    ): Promise<{ ok: true }> {
      return request("PUT", `/api/v1/documents/${documentId}`, body, true);
    },

    deleteDocument(documentId: number): Promise<void> {
      return request("DELETE", `/api/v1/documents/${documentId}`, undefined, true);
    },

    sendDocument(
      documentId: number,
      receiverInn: string,
    ): Promise<{ ok: true; receiver_name: string }> {
      return request(
        "POST",
        `/api/v1/documents/${documentId}/send`,
        { receiver_inn: receiverInn },
        true,
      );
    },

    respondDocument(
      documentId: number,
      action: "qabul" | "rad",
    ): Promise<{ ok: true; status: string }> {
      return request(
        "POST",
        `/api/v1/documents/${documentId}/respond`,
        { action },
        true,
      );
    },

    getWarehouseItems(): Promise<WarehouseList> {
      return request("GET", "/api/v1/warehouse/items", undefined, true);
    },

    configureWarehouseItem(
      catalogItemId: number,
      body: {
        track_stock: boolean;
        stock_type: "ready_food" | "raw_material";
        min_qty: number;
      },
    ): Promise<WarehouseItem> {
      return request("PUT", `/api/v1/warehouse/items/${catalogItemId}`, body, true);
    },

    createWarehouseMove(body: WarehouseMoveCreate): Promise<WarehouseMoveResult> {
      return request("POST", "/api/v1/warehouse/moves", body, true);
    },

    deleteWarehouseMove(moveId: number): Promise<void> {
      return request("DELETE", `/api/v1/warehouse/moves/${moveId}`, undefined, true);
    },

    getWarehouseMoves(inventoryItemId: number): Promise<WarehouseMove[]> {
      return request(
        "GET",
        `/api/v1/warehouse/items/${inventoryItemId}/moves`,
        undefined,
        true,
      );
    },

    getWarehouseRecipe(inventoryItemId: number): Promise<WarehouseRecipeIngredient[]> {
      return request(
        "GET",
        `/api/v1/warehouse/items/${inventoryItemId}/recipe`,
        undefined,
        true,
      );
    },

    getWarehouseProduction(limit = 50): Promise<WarehouseProductionBatch[]> {
      return request(
        "GET",
        `/api/v1/warehouse/production?limit=${limit}`,
        undefined,
        true,
      );
    },

    getStatistics(
      period: StatisticsPeriod = "oy",
      anchor = "",
    ): Promise<StatisticsReport> {
      const query = new URLSearchParams({ period });
      if (anchor) query.set("anchor", anchor);
      return request("GET", `/api/v1/statistics?${query.toString()}`, undefined, true);
    },

    getStatisticsNav(
      period: StatisticsPeriod,
      direction: -1 | 1,
      anchor = "",
    ): Promise<{ anchor: string }> {
      const query = new URLSearchParams({
        period,
        dir: String(direction),
      });
      if (anchor) query.set("anchor", anchor);
      return request(
        "GET",
        `/api/v1/statistics/nav?${query.toString()}`,
        undefined,
        true,
      );
    },
  };
}

export type BusinessOperationsClient = ReturnType<
  typeof createBusinessOperationsClient
>;
