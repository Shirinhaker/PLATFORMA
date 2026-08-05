declare module "node:crypto" {
  // jsdom `crypto.subtle` ni bermaydi — testda Node'ning haqiqiy
  // realizatsiyasi qo'yiladi (`src/test/setup.ts`).
  export const webcrypto: Crypto;
}
