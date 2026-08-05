import { webcrypto } from "node:crypto";

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";


// jsdom `crypto.subtle` ni bermaydi. Kvitansiya SHA-256 sini brauzerda
// hisoblaydigan kod shu API'ga tayanadi, shuning uchun testda Node'ning
// haqiqiy webcrypto realizatsiyasi qo'yiladi — soxta emas.
if (!globalThis.crypto?.subtle) {
  Object.defineProperty(globalThis, "crypto", {
    value: webcrypto,
    configurable: true,
  });
}

// jsdom `Blob.arrayBuffer()` ni ham bermaydi (brauzerlarda mavjud).
if (typeof Blob !== "undefined" && !Blob.prototype.arrayBuffer) {
  Blob.prototype.arrayBuffer = function arrayBuffer(this: Blob) {
    return new Promise<ArrayBuffer>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as ArrayBuffer);
      reader.onerror = () => reject(reader.error);
      reader.readAsArrayBuffer(this);
    });
  };
}

afterEach(cleanup);
