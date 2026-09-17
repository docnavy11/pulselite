const express = require("express");
const crypto = require("crypto");
const { WebSocketServer } = require("ws");
const http = require("http");
const path = require("path");

const PORT = parseInt(process.env.PORT || "3055", 10);
const app = express();
const server = http.createServer(app);

// WebSocket for live UI updates
const wss = new WebSocketServer({ server });
function broadcast(data) {
  const msg = JSON.stringify(data);
  wss.clients.forEach((c) => {
    if (c.readyState === 1) c.send(msg);
  });
}

// ── State ──────────────────────────────────────────────────────────────────
const logs = [];          // { id, timestamp, category, method, path, headers, body, response }
const MAX_LOGS = 500;
const mockConfigs = {
  slack: { status: 200, response: { ok: true } },
  stripe_customers: { status: 200, response: { data: [{ id: "cus_mock123", email: "test@example.com", name: "Mock Customer" }] } },
  stripe_subscriptions: { status: 200, response: { data: [{ id: "sub_mock123", status: "active", plan: { nickname: "Pro" } }] } },
  salesforce_token: { status: 200, response: { access_token: "mock_sf_token", instance_url: "http://localhost:" + PORT } },
  salesforce_case: { status: 201, response: { id: "500MOCK123", success: true } },
  linear: { status: 200, response: { data: { issueCreate: { success: true, issue: { id: "MOCK-1", identifier: "MOCK-1", url: "https://linear.app/mock/issue/MOCK-1" } } } } },
  hubspot: { status: 201, response: { id: "mock_hs_123", properties: {} } },
  generic: { status: 200, response: { received: true } },
};

function addLog(entry) {
  entry.id = crypto.randomUUID();
  entry.timestamp = new Date().toISOString();
  logs.unshift(entry);
  if (logs.length > MAX_LOGS) logs.length = MAX_LOGS;
  broadcast({ type: "log", data: entry });
}

// ── Middleware ──────────────────────────────────────────────────────────────
app.use(express.json({ limit: "5mb" }));
app.use(express.urlencoded({ extended: true }));
app.use(express.text({ type: "text/*" }));
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Headers", "*");
  res.header("Access-Control-Allow-Methods", "*");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

// ── Dashboard ──────────────────────────────────────────────────────────────
app.use("/static", express.static(path.join(__dirname, "public")));
app.get("/", (req, res) => res.sendFile(path.join(__dirname, "public", "index.html")));

// ── API: logs & config ─────────────────────────────────────────────────────
app.get("/api/logs", (req, res) => res.json(logs));
app.post("/api/logs/clear", (req, res) => { logs.length = 0; broadcast({ type: "clear" }); res.json({ ok: true }); });
app.get("/api/config", (req, res) => res.json(mockConfigs));
app.post("/api/config/:service", (req, res) => {
  const { service } = req.params;
  if (!mockConfigs[service]) return res.status(404).json({ error: "unknown service" });
  if (req.body.status !== undefined) mockConfigs[service].status = req.body.status;
  if (req.body.response !== undefined) mockConfigs[service].response = req.body.response;
  broadcast({ type: "config", data: mockConfigs });
  res.json(mockConfigs[service]);
});

// ── Webhook receiver (Pulse Lite sends here) ───────────────────────────────
app.all("/webhook", (req, res) => {
  const sig = req.headers["x-pulse-signature"] || null;
  const cfg = mockConfigs.generic;
  addLog({
    category: "webhook",
    method: req.method,
    path: req.originalUrl,
    headers: { "x-pulse-signature": sig, "content-type": req.headers["content-type"] },
    body: req.body,
    response: { status: cfg.status, body: cfg.response },
    signatureValid: sig ? "check-manually" : "no-signature",
  });
  res.status(cfg.status).json(cfg.response);
});

// Catch-all webhook path for custom URLs
app.all("/webhook/:path(*)", (req, res) => {
  const cfg = mockConfigs.generic;
  addLog({
    category: "webhook",
    method: req.method,
    path: req.originalUrl,
    headers: Object.fromEntries(
      Object.entries(req.headers).filter(([k]) => !["host", "connection", "accept-encoding"].includes(k))
    ),
    body: req.body,
    response: { status: cfg.status, body: cfg.response },
  });
  res.status(cfg.status).json(cfg.response);
});

// ── Slack mock ─────────────────────────────────────────────────────────────
app.post("/slack/webhook", (req, res) => {
  const cfg = mockConfigs.slack;
  addLog({
    category: "slack",
    method: "POST",
    path: "/slack/webhook",
    headers: { "content-type": req.headers["content-type"] },
    body: req.body,
    response: { status: cfg.status, body: cfg.response },
  });
  res.status(cfg.status).json(cfg.response);
});
// Slack services/T.../B.../... pattern
app.post("/services/:team/:bot/:token", (req, res) => {
  const cfg = mockConfigs.slack;
  addLog({
    category: "slack",
    method: "POST",
    path: req.originalUrl,
    headers: { "content-type": req.headers["content-type"] },
    body: req.body,
    response: { status: cfg.status, body: cfg.response },
  });
  res.status(cfg.status).json(cfg.response);
});

// ── Stripe mock ────────────────────────────────────────────────────────────
app.get("/v1/customers", (req, res) => {
  const cfg = mockConfigs.stripe_customers;
  addLog({
    category: "stripe",
    method: "GET",
    path: "/v1/customers",
    headers: { authorization: req.headers.authorization ? "Bearer sk-...redacted" : null },
    body: { query: req.query },
    response: { status: cfg.status, body: cfg.response },
  });
  res.status(cfg.status).json(cfg.response);
});
app.get("/v1/subscriptions", (req, res) => {
  const cfg = mockConfigs.stripe_subscriptions;
  addLog({
    category: "stripe",
    method: "GET",
    path: "/v1/subscriptions",
    headers: {},
    body: { query: req.query },
    response: { status: cfg.status, body: cfg.response },
  });
  res.status(cfg.status).json(cfg.response);
});

// ── Salesforce mock ────────────────────────────────────────────────────────
app.post("/services/oauth2/token", (req, res) => {
  const cfg = mockConfigs.salesforce_token;
  addLog({
    category: "salesforce",
    method: "POST",
    path: "/services/oauth2/token",
    headers: {},
    body: req.body,
    response: { status: cfg.status, body: cfg.response },
  });
  res.status(cfg.status).json(cfg.response);
});
app.post("/services/data/:version/sobjects/Case", (req, res) => {
  const cfg = mockConfigs.salesforce_case;
  addLog({
    category: "salesforce",
    method: "POST",
    path: req.originalUrl,
    headers: { authorization: req.headers.authorization ? "Bearer ...redacted" : null },
    body: req.body,
    response: { status: cfg.status, body: cfg.response },
  });
  res.status(cfg.status).json(cfg.response);
});
app.post("/services/data/:version/query", (req, res) => {
  addLog({ category: "salesforce", method: "POST", path: req.originalUrl, headers: {}, body: req.body, response: { status: 200, body: { records: [] } } });
  res.json({ records: [] });
});

// ── Linear GraphQL mock ───────────────────────────────────────────────────
app.post("/graphql", (req, res) => {
  const cfg = mockConfigs.linear;
  addLog({
    category: "linear",
    method: "POST",
    path: "/graphql",
    headers: { authorization: req.headers.authorization ? "...redacted" : null },
    body: req.body,
    response: { status: cfg.status, body: cfg.response },
  });
  res.status(cfg.status).json(cfg.response);
});

// ── HubSpot mock ──────────────────────────────────────────────────────────
app.post("/crm/v3/objects/contacts", (req, res) => {
  const cfg = mockConfigs.hubspot;
  addLog({
    category: "hubspot",
    method: "POST",
    path: "/crm/v3/objects/contacts",
    headers: {},
    body: req.body,
    response: { status: cfg.status, body: cfg.response },
  });
  res.status(cfg.status).json(cfg.response);
});

// ── Calendly / Cal.com mock (just receives and logs) ──────────────────────
app.all("/calendly/*", (req, res) => {
  addLog({ category: "calendly", method: req.method, path: req.originalUrl, headers: {}, body: req.body, response: { status: 200 } });
  res.json({ ok: true });
});
app.all("/calcom/*", (req, res) => {
  addLog({ category: "calcom", method: req.method, path: req.originalUrl, headers: {}, body: req.body, response: { status: 200 } });
  res.json({ ok: true });
});

// ── Catch-all for unknown routes ──────────────────────────────────────────
app.all("*", (req, res) => {
  if (req.path.startsWith("/static") || req.path === "/") return;
  addLog({
    category: "unknown",
    method: req.method,
    path: req.originalUrl,
    headers: Object.fromEntries(
      Object.entries(req.headers).filter(([k]) => !["host", "connection", "accept-encoding", "accept"].includes(k))
    ),
    body: req.body || null,
    response: { status: 200 },
  });
  res.json({ received: true, path: req.originalUrl, method: req.method });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`\n  🧪 Pulse Lite Test Server running on http://localhost:${PORT}\n`);
  console.log("  Endpoints:");
  console.log("    Dashboard:    http://localhost:" + PORT + "/");
  console.log("    Webhook:      http://localhost:" + PORT + "/webhook");
  console.log("    Slack:        http://localhost:" + PORT + "/slack/webhook");
  console.log("    Stripe:       http://localhost:" + PORT + "/v1/customers");
  console.log("    Salesforce:   http://localhost:" + PORT + "/services/oauth2/token");
  console.log("    Linear:       http://localhost:" + PORT + "/graphql");
  console.log("    HubSpot:      http://localhost:" + PORT + "/crm/v3/objects/contacts\n");
});
