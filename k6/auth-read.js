// k6/auth-read.js
// Authenticated read scenario: list chatbots + dashboard.
// 10 VUs, 30s. Thresholds: p95 < 500ms, errors < 1%.
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const errorRate = new Rate("errors");

export const options = {
  vus: 10,
  duration: "30s",
  thresholds: {
    http_req_duration: ["p(95)<500"],
    errors: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const EMAIL = __ENV.EMAIL || "test@pulse.dev";
const PASSWORD = __ENV.PASSWORD || "test";
const WS_ID = __ENV.WS_ID || "350863e7-3dc8-430e-bc23-fd41d4499d7b";

// setup() runs once before VUs start. Return value is passed to default() as `data`.
export function setup() {
  const res = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" } }
  );
  if (res.status !== 200) {
    throw new Error(`Login failed: ${res.status} ${res.body}`);
  }
  const body = JSON.parse(res.body);
  return { token: body.tokens.access_token };
}

export default function (data) {
  const headers = {
    Authorization: `Bearer ${data.token}`,
    "Content-Type": "application/json",
  };

  // Request 1: list chatbots
  const chatbotsRes = http.get(
    `${BASE_URL}/api/v1/workspaces/${WS_ID}/chatbots`,
    { headers }
  );
  const chatbotsOk = check(chatbotsRes, {
    "chatbots 200": (r) => r.status === 200,
    "chatbots is array": (r) => {
      try {
        return Array.isArray(JSON.parse(r.body));
      } catch {
        return false;
      }
    },
  });
  errorRate.add(!chatbotsOk);

  sleep(0.3);

  // Request 2: dashboard
  const dashRes = http.get(
    `${BASE_URL}/api/v1/workspaces/${WS_ID}/dashboard`,
    { headers }
  );
  const dashOk = check(dashRes, {
    "dashboard 200": (r) => r.status === 200,
  });
  errorRate.add(!dashOk);

  sleep(0.5);
}
