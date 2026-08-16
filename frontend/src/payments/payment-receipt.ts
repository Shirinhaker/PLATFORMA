import type { ApiClient } from "../api/client";
import type { PaymentReceiptRef } from "../api/types";

export type PaymentReceiptUploadApi = Pick<
  ApiClient,
  "createUploadGrant" | "uploadGrantedFile"
>;

async function fileDigest(file: File) {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export async function uploadPaymentReceipt(
  api: PaymentReceiptUploadApi,
  file: File,
): Promise<PaymentReceiptRef> {
  const grant = await api.createUploadGrant({
    purpose: "payment_receipt",
    filename: file.name,
    content_type: file.type,
    size_bytes: file.size,
  });
  await api.uploadGrantedFile(grant, file);
  return {
    object_key: grant.object_key,
    filename: file.name,
    mime: file.type,
    sha256: await fileDigest(file),
  };
}
