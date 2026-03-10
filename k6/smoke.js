// k6/smoke.js
// Smoke test: health endpoint only. 5 VUs, 20s.
// Validates p95 < 200ms, error rate < 1%.
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const errorRate = new Rate("errors");

export const options = {
  vus: 5,
  duration: "20s",
  thresholds: {
    http_req_duration: ["p(95)<200"],
    errors: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  const res = http.get(`${BASE_URL}/api/v1/health`);
  const ok = check(res, {
    "status is 200": (r) => r.status === 200,
    "database connected": (r) => {
      try {
        return JSON.parse(r.body).database === "connected";
      } catch {
        return false;
      }
    },
  });
  errorRate.add(!ok);
  sleep(0.5);
}
