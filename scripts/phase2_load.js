import http from "k6/http";
import { check, fail, sleep } from "k6";


export const options = {
  stages: [
    { duration: "30s", target: 100 },
    { duration: "60s", target: 500 },
    { duration: "60s", target: 1000 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
  },
};


export function setup() {
  if (!__ENV.KOPRIK_API_BASE_URL) {
    fail("KOPRIK_API_BASE_URL required");
  }
  if (!__ENV.KOPRIK_LOAD_SESSION) {
    fail("KOPRIK_LOAD_SESSION required");
  }
  return {
    apiBaseUrl: __ENV.KOPRIK_API_BASE_URL.replace(/\/$/, ""),
    session: __ENV.KOPRIK_LOAD_SESSION,
  };
}


export default function (data) {
  const response = http.get(`${data.apiBaseUrl}/api/v1/me`, {
    headers: {
      Cookie: `koprik_session=${data.session}`,
    },
  });
  check(response, {
    "status 200": (result) => result.status === 200,
    "has account type": (result) =>
      ["user", "business"].includes(result.json("account_type")),
  });
  sleep(1);
}
