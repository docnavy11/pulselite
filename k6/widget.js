// k6/widget.js
// Widget config load test: public endpoint, no auth.
// 20 VUs, 30s. Thresholds: p95 < 1000ms (local dev Docker), errors < 1%.
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const errorRate = new Rate("errors");

export const options = {
  vus: 20,
  duration: "30s",
  thresholds: {
    http_req_duration: ["p(95)<1000"],
    errors: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const CHATBOT_ID = __ENV.CHATBOT_ID || "a8dfa0e8-b077-4bcc-9d2a-00bdf3e4f108";

export default function () {
  const res = http.get(
    `${BASE_URL}/api/v1/widget/${CHATBOT_ID}/config`
  );
  const ok = check(res, {
    "widget config 200": (r) => r.status === 200,
    "has display_name": (r) => {
      try {
        const body = JSON.parse(r.body);
        return typeof body.display_name === "string" && body.display_name.length > 0;
      } catch {
        return false;
      }
    },
  });
  errorRate.add(!ok);
  sleep(1);
}
