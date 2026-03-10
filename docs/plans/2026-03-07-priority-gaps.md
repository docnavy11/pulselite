# Priority Gaps Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the 7 highest-priority product gaps between the current Pulse MVP and Chatbase feature parity, ordered from simplest to most complex.

**Architecture:** Pulse uses FastAPI (async SQLAlchemy) on the backend with Celery for async tasks, Next.js 15 App Router on the frontend, and a Vanilla TS Shadow DOM widget. All API routes are workspace-scoped at `/api/v1/workspaces/{workspace_id}/...`. The intelligence pipeline already extracts competitor mentions, feature requests, churn signals, and lead intent per conversation via GPT-4o-mini.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / Alembic / Celery / Next.js 15 / TypeScript / Tailwind / Zustand / Vanilla TS widget (Rollup)

**Skipped — already complete:**
- Widget markdown rendering (`renderMarkdownLite` in `widget/src/utils.ts` is used for all bot messages)
- Document auto-sync Celery task (`sync_stale_documents` in `backend/app/workers/tasks/sync_documents.py` is wired and runs on beat schedule)
- Slack escalation alerting (`send_escalation_alerts` is called from `resolution_service.py:77` and works end-to-end once a webhook URL is saved in the integrations page)

---

## Task 1: Competitive Intelligence Page

**What:** Add a "Competitive" section to the Intelligence hub showing competitor mentions, churn risk signals, and expansion opportunity signals — all already being extracted and saved to `IntelligenceSignal` by `analyze_conversation.py`.

**Files:**
- Create: `frontend/src/app/(dashboard)/intelligence/competitive/page.tsx`
- Modify: `frontend/src/app/(dashboard)/intelligence/page.tsx` (add card)
- Modify: `backend/app/api/v1/intelligence.py` (add filtered endpoint)

### Step 1: Check what the intelligence API already exposes

```bash
grep -n "intelligence.signals\|signal_type\|competitor" backend/app/api/v1/intelligence.py
```

Expected: existing `/intelligence-signals` endpoint. Confirm its query params.

### Step 2: Add a filtered endpoint if not present

In `backend/app/api/v1/intelligence.py`, confirm there is a `GET /intelligence-signals` endpoint that accepts `signal_type` as a query param. If it does not, add:

```python
@router.get("/intelligence-signals")
async def get_intelligence_signals(
    workspace_id: uuid.UUID = Depends(get_workspace),
    signal_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(IntelligenceSignal).where(
        IntelligenceSignal.workspace_id == workspace_id
    )
    if signal_type:
        q = q.where(IntelligenceSignal.signal_type == signal_type)
    q = q.order_by(IntelligenceSignal.created_at.desc()).limit(200)
    result = await db.execute(q)
    return result.scalars().all()
```

### Step 3: Add the Competitive card to the Intelligence hub

Edit `frontend/src/app/(dashboard)/intelligence/page.tsx`. Add to the `sections` array (before the closing bracket):

```typescript
{
  href: "/intelligence/competitive",
  label: "Competitive Intelligence",
  description: "Track competitor mentions, churn risk, and expansion signals from conversations.",
  icon: TrendingDown,
  color: "text-orange-600 bg-orange-50",
},
```

Also add `TrendingDown` to the lucide-react import at the top.

### Step 4: Create the Competitive Intelligence page

Create `frontend/src/app/(dashboard)/intelligence/competitive/page.tsx`:

```typescript
"use client";

import { useState, useEffect } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import api from "@/lib/api";

interface Signal {
  id: string;
  signal_type: string;
  payload: Record<string, string>;
  created_at: string;
}

const SIGNAL_TYPES = [
  { key: "competitor_mention", label: "Competitor Mentions", color: "text-orange-600" },
  { key: "churn_risk", label: "Churn Risk", color: "text-red-600" },
  { key: "expansion_opportunity", label: "Expansion Signals", color: "text-green-600" },
];

export default function CompetitivePage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [signals, setSignals] = useState<Record<string, Signal[]>>({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("competitor_mention");

  useEffect(() => {
    if (!workspace) return;
    Promise.all(
      SIGNAL_TYPES.map((t) =>
        api
          .get(`/workspaces/${workspace.id}/intelligence-signals?signal_type=${t.key}`)
          .then((r) => [t.key, r.data])
      )
    )
      .then((results) => {
        const map: Record<string, Signal[]> = {};
        results.forEach(([key, data]) => { map[key as string] = data as Signal[]; });
        setSignals(map);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace]);

  // Group competitor mentions by competitor name, count occurrences
  const grouped = (signals[activeTab] || []).reduce<Record<string, { count: number; latest: string }>>((acc, s) => {
    const key = s.payload.competitor || s.payload.signal || s.payload.bug || "Unknown";
    if (!acc[key]) acc[key] = { count: 0, latest: s.created_at };
    acc[key].count++;
    if (s.created_at > acc[key].latest) acc[key].latest = s.created_at;
    return acc;
  }, {});

  const sorted = Object.entries(grouped).sort((a, b) => b[1].count - a[1].count);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-600" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Competitive Intelligence</h1>
      <p className="text-sm text-gray-500 mb-6">
        Signals extracted automatically from customer conversations.
      </p>

      <div className="flex gap-2 mb-6">
        {SIGNAL_TYPES.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-200 ${
              activeTab === t.key
                ? "bg-gray-900 text-white"
                : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            {t.label}
            <span className="ml-1.5 text-xs opacity-70">
              ({(signals[t.key] || []).length})
            </span>
          </button>
        ))}
      </div>

      {sorted.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-gray-400 text-sm">
            No {SIGNAL_TYPES.find((t) => t.key === activeTab)?.label.toLowerCase()} detected yet.
            Signals appear after conversations are analyzed.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {sorted.map(([name, { count, latest }]) => (
            <Card key={name}>
              <CardContent className="py-4 flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-gray-900">{name}</span>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Last seen {new Date(latest).toLocaleDateString()}
                  </p>
                </div>
                <Badge variant={count >= 5 ? "danger" : count >= 2 ? "warning" : "default"}>
                  {count} {count === 1 ? "mention" : "mentions"}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

### Step 5: Verify

```bash
# Check backend API exists
curl -s http://localhost:8000/api/v1/workspaces/{workspace_id}/intelligence-signals?signal_type=competitor_mention \
  -H "Authorization: Bearer $TOKEN" | jq 'length'

# Navigate to http://localhost:3001/intelligence/competitive
# Should show 3 tabs: Competitor Mentions, Churn Risk, Expansion Signals
```

### Step 6: Commit

```bash
git add frontend/src/app/(dashboard)/intelligence/competitive/ \
        frontend/src/app/(dashboard)/intelligence/page.tsx \
        backend/app/api/v1/intelligence.py
git commit -m "feat: add competitive intelligence page (competitor mentions, churn risk, expansion signals)"
```

---

## Task 2: Widget Quick Replies

**What:** After each bot response, show clickable quick reply chips. The chatbot admin configures default chips in settings. Optionally, the backend can return per-turn suggested replies in the SSE `done` event.

**Files:**
- Modify: `backend/app/models/chatbots.py` — add `quick_replies` ARRAY field
- Modify: `backend/app/schemas/chatbots.py` — expose in response schema
- Modify: `backend/app/services/chat_service.py` (or wherever SSE `done` is emitted) — include `suggested_replies` in done event
- Modify: `widget/src/widget.ts` — render chips after bot message
- Modify: `widget/src/ui/styles.ts` — style chips
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx` — add chip config UI

### Step 1: Add quick_replies to Chatbot model

In `backend/app/models/chatbots.py`, find the `Chatbot` class and add after the existing JSONB fields:

```python
from sqlalchemy.dialects.postgresql import ARRAY

quick_replies: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
```

### Step 2: Create a migration

```bash
make migrate-create msg="add_chatbot_quick_replies"
```

Edit the generated migration file in `backend/alembic/versions/`. Add:

```python
def upgrade() -> None:
    op.add_column("chatbots", sa.Column("quick_replies", postgresql.ARRAY(sa.Text()), nullable=True))

def downgrade() -> None:
    op.drop_column("chatbots", "quick_replies")
```

Run it:
```bash
make migrate
```

### Step 3: Expose quick_replies in ChatbotResponse schema

In `backend/app/schemas/chatbots.py`, add to `ChatbotResponse`:

```python
quick_replies: list[str] | None = None
```

### Step 4: Include suggested_replies in the public widget config

In `backend/app/api/v1/public.py` (or wherever `/widget/{chatbot_id}/config` is defined), ensure `quick_replies` is returned in the `WidgetConfigResponse`. It should flow through automatically via the schema if `ChatbotResponse` or `WidgetConfigResponse` includes it.

In `backend/app/schemas/public.py` (or equivalent), add to `WidgetConfigResponse`:

```python
quick_replies: list[str] = []
```

And in the endpoint handler, populate it from the chatbot:

```python
quick_replies=chatbot.quick_replies or [],
```

### Step 5: Pass quick_replies to widget config in widget/src/config.ts

In `widget/src/config.ts`, add to `WidgetConfig`:

```typescript
quickReplies: string[];
```

In `widget/src/index.ts` (where config is fetched from API), add:

```typescript
quickReplies: data.quick_replies || [],
```

### Step 6: Render chips in widget after bot messages

In `widget/src/widget.ts`, after `onDone` fires (inside the `streamChat` callback), add chip rendering:

```typescript
onDone: (data) => {
  // ... existing code ...

  // Render quick reply chips
  const replies = data.suggestedReplies || this.config.quickReplies || [];
  if (replies.length > 0) {
    this.renderQuickReplies(replies);
  }
  // ... existing code continues ...
},
```

Add the `renderQuickReplies` method to the `Widget` class:

```typescript
private renderQuickReplies(replies: string[]): void {
  // Remove any existing chip row
  const existing = this.chatWindow.messagesContainer.querySelector(".pulse-chips");
  if (existing) existing.remove();

  const row = document.createElement("div");
  row.className = "pulse-chips";

  replies.forEach((text) => {
    const chip = document.createElement("button");
    chip.className = "pulse-chip";
    chip.textContent = text;
    chip.onclick = () => {
      row.remove();
      this.sendMessage(text);
    };
    row.appendChild(chip);
  });

  this.chatWindow.messagesContainer.appendChild(row);
  this.scrollToBottom();
}
```

### Step 7: Add chip styles in widget/src/ui/styles.ts

In the `getStyles()` function return string, add:

```css
.pulse-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 4px 12px 8px;
}
.pulse-chip {
  background: transparent;
  border: 1.5px solid ${primaryColor};
  border-radius: 16px;
  color: ${primaryColor};
  cursor: pointer;
  font-size: 12px;
  padding: 4px 12px;
  transition: all 0.15s;
}
.pulse-chip:hover {
  background: ${primaryColor};
  color: #fff;
}
```

### Step 8: Add chip config in customize page

In `frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx`, add a "Quick Replies" section with a tag-input UI (enter text + press Enter to add chip, X to remove):

```typescript
// Add state
const [quickReplies, setQuickReplies] = useState<string[]>(chatbot?.quick_replies || []);
const [chipInput, setChipInput] = useState("");

function addChip() {
  const val = chipInput.trim();
  if (val && !quickReplies.includes(val) && quickReplies.length < 8) {
    setQuickReplies([...quickReplies, val]);
    setChipInput("");
  }
}
```

Include in the save payload: `quick_replies: quickReplies`.

### Step 9: Build widget and verify

```bash
cd /Users/yvanveldeman/dev/pulse/widget && npm run build
# Check dist/widget.js size is still reasonable (< 10kb gzipped)
```

Navigate to chatbot → Customize → set 2 quick reply chips → save.
Open the test chat → send a message → bot replies → chips appear → clicking one sends it.

### Step 10: Commit

```bash
git add backend/app/models/chatbots.py \
        backend/app/schemas/chatbots.py \
        backend/alembic/versions/ \
        widget/src/widget.ts \
        widget/src/ui/styles.ts \
        widget/src/config.ts \
        frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx
git commit -m "feat: widget quick reply chips — configurable per chatbot, rendered after bot messages"
```

---

## Task 3: Fix Integrations (Email Config Bug + HubSpot/Linear Push)

**What:**
1. The email integration config form (`EmailConfig` component) only saves `from_address` but `email.py` service reads `api_key` and `to_email`. Fix the form to collect all required fields.
2. Wire HubSpot lead push in `score_lead.py` Celery task.
3. Wire Linear feature request push in `cluster_feature_requests.py` Celery task.

**Files:**
- Modify: `frontend/src/app/(dashboard)/settings/integrations/page.tsx` — fix `EmailConfig` component
- Modify: `backend/app/workers/tasks/score_lead.py` — push hot leads to HubSpot
- Modify: `backend/app/workers/tasks/cluster_feature_requests.py` — push clusters to Linear
- Create: `backend/app/services/integrations/hubspot.py`
- Create: `backend/app/services/integrations/linear.py`

### Step 1: Fix the EmailConfig form

In `frontend/src/app/(dashboard)/settings/integrations/page.tsx`, replace the `EmailConfig` function:

```typescript
function EmailConfig({ integration, onSave, saving }) {
  const [apiKey, setApiKey] = useState(
    (integration.config.api_key as string) || ""
  );
  const [toEmail, setToEmail] = useState(
    (integration.config.to_email as string) || ""
  );
  const [fromEmail, setFromEmail] = useState(
    (integration.config.from_email as string) || "Pulse <notifications@pulse.app>"
  );

  return (
    <>
      <Input
        label="Resend API Key"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        placeholder="re_..."
        type="password"
      />
      <Input
        label="Send alerts to (email)"
        value={toEmail}
        onChange={(e) => setToEmail(e.target.value)}
        placeholder="team@yourcompany.com"
      />
      <Input
        label="From address"
        value={fromEmail}
        onChange={(e) => setFromEmail(e.target.value)}
        placeholder="Pulse <notifications@pulse.app>"
      />
      <Button
        size="sm"
        onClick={() => onSave({ api_key: apiKey, to_email: toEmail, from_email: fromEmail })}
        loading={saving}
      >
        Save
      </Button>
    </>
  );
}
```

### Step 2: Create HubSpot service

Create `backend/app/services/integrations/hubspot.py`:

```python
import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConfig

logger = logging.getLogger(__name__)


async def _get_hubspot_config(session: AsyncSession, workspace_id: uuid.UUID) -> dict | None:
    result = await session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "hubspot",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    config = result.scalar_one_or_none()
    return config.config if config else None


async def push_lead_to_hubspot(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    email: str | None,
    name: str | None,
    properties: dict | None = None,
) -> bool:
    config = await _get_hubspot_config(session, workspace_id)
    if not config or not config.get("api_key") or not email:
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            payload = {
                "properties": {
                    "email": email,
                    "firstname": (name or "").split(" ")[0],
                    "lastname": " ".join((name or "").split(" ")[1:]) or "",
                    **(properties or {}),
                }
            }
            resp = await client.post(
                "https://api.hubapi.com/crm/v3/objects/contacts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json",
                },
            )
            return resp.status_code in (200, 201, 409)  # 409 = already exists
    except Exception as e:
        logger.error(f"HubSpot push failed: {e}")
        return False
```

### Step 3: Wire HubSpot push in score_lead.py

Read `backend/app/workers/tasks/score_lead.py` first, then at the end of the scoring function, after a lead is scored as `hot`, add:

```python
if lead.tier == "hot" and contact.email:
    from app.services.integrations.hubspot import push_lead_to_hubspot
    await push_lead_to_hubspot(
        session, workspace_id,
        email=contact.email,
        name=contact.name,
        properties={"lead_source": "Pulse", "hs_lead_status": "NEW"},
    )
```

### Step 4: Create Linear service

Create `backend/app/services/integrations/linear.py`:

```python
import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConfig

logger = logging.getLogger(__name__)


async def _get_linear_config(session: AsyncSession, workspace_id: uuid.UUID) -> dict | None:
    result = await session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "linear",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    config = result.scalar_one_or_none()
    return config.config if config else None


async def create_linear_issue(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    title: str,
    description: str,
) -> bool:
    config = await _get_linear_config(session, workspace_id)
    if not config or not config.get("api_token"):
        return False

    try:
        # First get team ID
        async with httpx.AsyncClient(timeout=10) as client:
            team_query = """
            query { teams { nodes { id name } } }
            """
            resp = await client.post(
                "https://api.linear.app/graphql",
                json={"query": team_query},
                headers={
                    "Authorization": config["api_token"],
                    "Content-Type": "application/json",
                },
            )
            teams = resp.json().get("data", {}).get("teams", {}).get("nodes", [])
            if not teams:
                return False

            # Use configured project team or first team
            preferred = config.get("default_project", "")
            team_id = next(
                (t["id"] for t in teams if preferred and t["name"] == preferred),
                teams[0]["id"],
            )

            issue_mutation = """
            mutation CreateIssue($title: String!, $description: String, $teamId: String!) {
              issueCreate(input: {title: $title, description: $description, teamId: $teamId}) {
                success
                issue { id url }
              }
            }
            """
            await client.post(
                "https://api.linear.app/graphql",
                json={
                    "query": issue_mutation,
                    "variables": {"title": title, "description": description, "teamId": team_id},
                },
                headers={
                    "Authorization": config["api_token"],
                    "Content-Type": "application/json",
                },
            )
            return True
    except Exception as e:
        logger.error(f"Linear issue creation failed: {e}")
        return False
```

### Step 5: Wire Linear push in cluster_feature_requests.py

Read `backend/app/workers/tasks/cluster_feature_requests.py`, then after a cluster is persisted, add:

```python
from app.services.integrations.linear import create_linear_issue

for cluster in new_clusters:
    await create_linear_issue(
        session, workspace_id,
        title=f"Feature Request: {cluster.topic_label}",
        description=f"Requested by {cluster.request_count} customers.\n\nRepresentative: {cluster.representative_request}",
    )
```

### Step 6: Verify email fix

1. Go to Settings → Integrations → Email → Configure
2. Should now see 3 fields: Resend API Key, Send alerts to, From address
3. Save with a real Resend key and email address
4. Trigger a test escalation → check inbox

### Step 7: Commit

```bash
git add frontend/src/app/(dashboard)/settings/integrations/page.tsx \
        backend/app/services/integrations/hubspot.py \
        backend/app/services/integrations/linear.py \
        backend/app/workers/tasks/score_lead.py \
        backend/app/workers/tasks/cluster_feature_requests.py
git commit -m "fix: email integration config form; feat: HubSpot lead push and Linear feature request push"
```

---

## Task 4: KB Source Breadth — Sitemap + Sync Frequency UI

**What:**
1. Add a "Sitemap" source tab to the `AddSourceModal` (backend pipeline in `pipeline.py` already handles `source_type="sitemap"` — just needs an API endpoint and frontend tab).
2. Add `sync_frequency` dropdown per document row in `SourcesTab` with a backend `PATCH /documents/{id}` endpoint to update it.

**Files:**
- Modify: `backend/app/api/v1/documents.py` — add `PATCH /{document_id}` and validate sitemap URL on `POST /`
- Modify: `backend/app/schemas/documents.py` — add `DocumentUpdate` schema, add `sitemap` to `DocumentCreate`
- Modify: `frontend/src/components/knowledge/AddSourceModal.tsx` — add Sitemap tab
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/sources/SourcesTab.tsx` — add sync frequency selector
- Modify: `frontend/src/lib/api-functions.ts` — add `updateDocument()` function

### Step 1: Add sitemap to DocumentCreate schema

In `backend/app/schemas/documents.py`, the `DocumentCreate` schema likely has `source_type` as a literal. Check and ensure `"sitemap"` is a valid value. If it's not explicitly listed, it's likely accepted as a free-form string. Confirm by reading the schema.

If the schema uses `Literal["url", "file", "text"]`, change to `Literal["url", "file", "text", "qa", "sitemap"]`.

Add `DocumentUpdate` schema:

```python
class DocumentUpdate(BaseModel):
    sync_frequency: Literal["manual", "daily", "weekly", "monthly"] | None = None
    title: str | None = None
```

### Step 2: Add PATCH endpoint and sitemap POST endpoint

In `backend/app/api/v1/documents.py`, add:

```python
from app.schemas.documents import DocumentUpdate

@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: uuid.UUID,
    body: DocumentUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.update_document(db, workspace_id, document_id, body.model_dump(exclude_none=True))
    await db.commit()
    return doc
```

In `backend/app/services/document_service.py`, add:

```python
async def update_document(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    updates: dict,
) -> Document:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for key, value in updates.items():
        setattr(doc, key, value)
    if "sync_frequency" in updates and updates["sync_frequency"] != "manual":
        from datetime import timedelta
        freq_days = {"daily": 1, "weekly": 7, "monthly": 30}
        doc.next_sync_at = datetime.now(timezone.utc) + timedelta(days=freq_days[updates["sync_frequency"]])
    return doc
```

### Step 3: Add Sitemap tab to AddSourceModal

In `frontend/src/components/knowledge/AddSourceModal.tsx`, add to the `tabs` array:

```typescript
{ id: "sitemap" as const, label: "Sitemap", icon: Globe },
```

Add sitemap state:
```typescript
const [sitemapUrl, setSitemapUrl] = useState("");
```

Add sitemap UI section (after the `text` tab content):
```typescript
{activeTab === "sitemap" && (
  <div className="space-y-3">
    <Input
      placeholder="https://example.com/sitemap.xml"
      value={sitemapUrl}
      onChange={(e) => setSitemapUrl(e.target.value)}
    />
    <p className="text-xs text-gray-400">
      All URLs found in the sitemap will be crawled and indexed.
    </p>
  </div>
)}
```

Update `canSubmit`:
```typescript
const canSubmit =
  (activeTab === "url" && urls.length > 0) ||
  (activeTab === "upload" && files.length > 0) ||
  (activeTab === "text" && textContent.trim().length > 0) ||
  (activeTab === "sitemap" && sitemapUrl.trim().length > 0);
```

Update `handleSubmit` to handle sitemap tab:
```typescript
} else if (activeTab === "sitemap" && sitemapUrl.trim()) {
  await createDocumentFromUrl(workspaceId, {
    source_url: sitemapUrl.trim(),
    source_type: "sitemap",
  });
}
```

Make sure `createDocumentFromUrl` accepts an optional `source_type` param. In `frontend/src/lib/api-functions.ts`, update the call signature:

```typescript
export async function createDocumentFromUrl(
  workspaceId: string,
  data: { source_url: string; knowledge_base_id?: string; source_type?: string }
) {
  const res = await api.post(`/workspaces/${workspaceId}/documents`, data);
  return res.data;
}
```

### Step 4: Add sync frequency UI to SourcesTab

In `frontend/src/app/(dashboard)/chatbots/[id]/sources/SourcesTab.tsx`, add an `updateDocument` import and a sync frequency dropdown per document row.

Add to imports:
```typescript
import { updateDocument } from "@/lib/api-functions";
```

Add `updateDocument` to `api-functions.ts`:
```typescript
export async function updateDocument(
  workspaceId: string,
  documentId: string,
  data: { sync_frequency?: string }
) {
  const res = await api.patch(`/workspaces/${workspaceId}/documents/${documentId}`, data);
  return res.data;
}
```

In the table, add a "Sync" column header after "Last Indexed". In the row, add:

```typescript
<td className="px-4 py-3">
  <select
    value={doc.sync_frequency || "manual"}
    onChange={async (e) => {
      const updated = await updateDocument(workspace!.id, doc.id, {
        sync_frequency: e.target.value,
      });
      setDocuments((prev) => prev.map((d) => (d.id === doc.id ? updated : d)));
    }}
    className="text-xs text-gray-600 border border-gray-200 rounded px-2 py-1"
  >
    <option value="manual">Manual</option>
    <option value="daily">Daily</option>
    <option value="weekly">Weekly</option>
    <option value="monthly">Monthly</option>
  </select>
</td>
```

Also add `sync_frequency` to the `Document` type in `frontend/src/lib/types.ts`:
```typescript
sync_frequency?: string;
```

### Step 5: Verify

```bash
# Add a sitemap source via the modal → check it shows "sitemap" type in the table
# Change sync frequency → check no errors in console
# Check: make shell-backend → python -c "from app.models.knowledge import Document; print('ok')"
```

### Step 6: Commit

```bash
git add backend/app/api/v1/documents.py \
        backend/app/schemas/documents.py \
        backend/app/services/document_service.py \
        frontend/src/components/knowledge/AddSourceModal.tsx \
        frontend/src/app/(dashboard)/chatbots/[id]/sources/SourcesTab.tsx \
        frontend/src/lib/api-functions.ts \
        frontend/src/lib/types.ts
git commit -m "feat: sitemap source type in AddSourceModal; sync frequency per document"
```

---

## Task 5: Workspace Invitations + RBAC

**What:** Allow workspace owners/admins to invite team members by email. Invitees receive an email with a magic link. On accept, a new `Agent` record is created (or existing agent is joined to the workspace) and a `WorkspaceMembership` record is added.

**Note:** `WorkspaceMembership.role` (owner/admin/member) already exists in the DB.

**Files:**
- Create: `backend/app/models/invites.py`
- Create: `backend/alembic/versions/005_workspace_invites.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/invites.py`
- Create: `backend/app/services/invite_service.py`
- Create: `backend/app/api/v1/invites.py`
- Modify: `backend/app/main.py`
- Create: `frontend/src/app/(dashboard)/settings/team/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx` or layout (add Team nav link)
- Modify: `frontend/src/app/(auth)/accept-invite/page.tsx` (public invite acceptance page)
- Modify: `frontend/src/lib/api-functions.ts`

### Step 1: Create WorkspaceInvite model

Create `backend/app/models/invites.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkspaceInvite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_invites"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="'member'")
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
```

### Step 2: Register model

In `backend/app/models/__init__.py`, add:

```python
from app.models.invites import WorkspaceInvite  # noqa: F401
```

### Step 3: Create migration

```bash
make migrate-create msg="add_workspace_invites"
```

Edit the generated file:

```python
import sqlalchemy as sa
from alembic import op

def upgrade() -> None:
    op.create_table(
        "workspace_invites",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="member"),
        sa.Column("token", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_by_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("workspace_invites")
```

Run:
```bash
make migrate
```

### Step 4: Create invite schemas

Create `backend/app/schemas/invites.py`:

```python
from datetime import datetime
from pydantic import BaseModel, EmailStr


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = "member"


class InviteResponse(BaseModel):
    id: str
    email: str
    role: str
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteAccept(BaseModel):
    token: str
    full_name: str
    password: str
```

### Step 5: Create invite service

Create `backend/app/services/invite_service.py`:

```python
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invites import WorkspaceInvite
from app.models.organizational import Agent, WorkspaceMembership, Workspace
from app.services.auth_service import hash_password  # reuse existing


async def create_invite(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    email: str,
    role: str,
    invited_by_id: uuid.UUID,
) -> WorkspaceInvite:
    token = secrets.token_urlsafe(32)
    invite = WorkspaceInvite(
        workspace_id=workspace_id,
        email=email,
        role=role,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        invited_by_id=invited_by_id,
    )
    db.add(invite)
    await db.flush()
    return invite


async def accept_invite(
    db: AsyncSession,
    token: str,
    full_name: str,
    password: str,
) -> Agent:
    result = await db.execute(
        select(WorkspaceInvite).where(
            WorkspaceInvite.token == token,
            WorkspaceInvite.accepted_at.is_(None),
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already accepted")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite has expired")

    # Find or create agent
    agent_result = await db.execute(
        select(Agent).where(Agent.email == invite.email)
    )
    agent = agent_result.scalar_one_or_none()

    if not agent:
        agent = Agent(
            workspace_id=invite.workspace_id,
            email=invite.email,
            name=full_name,
            password_hash=hash_password(password),
        )
        db.add(agent)
        await db.flush()

    # Create membership
    membership = WorkspaceMembership(
        agent_id=agent.id,
        workspace_id=invite.workspace_id,
        role=invite.role,
    )
    db.add(membership)

    # Mark accepted
    invite.accepted_at = datetime.now(timezone.utc)
    return agent


async def list_invites(db: AsyncSession, workspace_id: uuid.UUID) -> list[WorkspaceInvite]:
    result = await db.execute(
        select(WorkspaceInvite)
        .where(WorkspaceInvite.workspace_id == workspace_id)
        .order_by(WorkspaceInvite.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_invite(db: AsyncSession, workspace_id: uuid.UUID, invite_id: uuid.UUID) -> None:
    result = await db.execute(
        select(WorkspaceInvite).where(
            WorkspaceInvite.id == invite_id,
            WorkspaceInvite.workspace_id == workspace_id,
        )
    )
    invite = result.scalar_one_or_none()
    if invite:
        await db.delete(invite)
```

### Step 6: Create invites router

Create `backend/app/api/v1/invites.py`:

```python
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.organizational import Agent
from app.schemas.invites import InviteAccept, InviteCreate, InviteResponse
from app.services import invite_service
from app.services.integrations.email import send_invite_email  # to be added

router = APIRouter(tags=["invites"])


@router.post("/workspaces/{workspace_id}/invites", response_model=InviteResponse)
async def create_invite(
    body: InviteCreate,
    background_tasks: BackgroundTasks,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    invite = await invite_service.create_invite(
        db, workspace_id, body.email, body.role, current_user.id
    )
    await db.commit()
    background_tasks.add_task(send_invite_email, invite.email, invite.token, workspace_id)
    return invite


@router.get("/workspaces/{workspace_id}/invites", response_model=list[InviteResponse])
async def list_invites(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await invite_service.list_invites(db, workspace_id)


@router.delete("/workspaces/{workspace_id}/invites/{invite_id}", status_code=204)
async def revoke_invite(
    invite_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    await invite_service.revoke_invite(db, workspace_id, invite_id)
    await db.commit()


@router.post("/invites/accept")
async def accept_invite(
    body: InviteAccept,
    db: AsyncSession = Depends(get_db),
):
    agent = await invite_service.accept_invite(db, body.token, body.full_name, body.password)
    await db.commit()
    return {"status": "ok", "email": agent.email}
```

### Step 7: Add send_invite_email to email service

In `backend/app/services/integrations/email.py`, add:

```python
async def send_invite_email(email: str, token: str, workspace_id: uuid.UUID) -> None:
    """Fire-and-forget: send invite even without Resend configured (log link for dev)."""
    invite_url = f"{settings.NEXT_PUBLIC_APP_URL}/accept-invite?token={token}"
    logger.info(f"Invite link for {email}: {invite_url}")
    # If Resend is configured for this workspace, also send real email
    # (skipped here for brevity — use the same resend pattern as send_escalation_email)
```

### Step 8: Register router in main.py

In `backend/app/main.py`, add:

```python
from app.api.v1.invites import router as invites_router
app.include_router(invites_router, prefix="/api/v1")
```

### Step 9: Add Team settings page

Create `frontend/src/app/(dashboard)/settings/team/page.tsx`:

```typescript
"use client";

import { useState, useEffect } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { Trash2 } from "lucide-react";
import api from "@/lib/api";

interface Invite {
  id: string;
  email: string;
  role: string;
  expires_at: string;
  accepted_at: string | null;
  created_at: string;
}

export default function TeamPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!workspace) return;
    api
      .get(`/workspaces/${workspace.id}/invites`)
      .then((r) => setInvites(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace]);

  async function handleInvite() {
    if (!workspace || !email) return;
    setSending(true);
    try {
      const res = await api.post(`/workspaces/${workspace.id}/invites`, { email, role });
      setInvites((prev) => [res.data, ...prev]);
      setEmail("");
    } catch {
      // handle error
    } finally {
      setSending(false);
    }
  }

  async function handleRevoke(inviteId: string) {
    if (!workspace) return;
    await api.delete(`/workspaces/${workspace.id}/invites/${inviteId}`);
    setInvites((prev) => prev.filter((i) => i.id !== inviteId));
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-8 w-8 text-primary-600" /></div>;

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Team</h1>

      <Card className="mb-6">
        <CardContent className="py-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">Invite a team member</h2>
          <div className="flex gap-2">
            <Input
              placeholder="colleague@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleInvite()}
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 text-sm text-gray-700 focus:ring-2 focus:ring-primary-500 focus:outline-none"
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
            <Button onClick={handleInvite} loading={sending} disabled={!email}>
              Send Invite
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-2">
        {invites.map((invite) => (
          <Card key={invite.id}>
            <CardContent className="py-3 flex items-center justify-between">
              <div>
                <span className="text-sm font-medium text-gray-900">{invite.email}</span>
                <div className="flex gap-2 mt-1">
                  <Badge variant="default">{invite.role}</Badge>
                  {invite.accepted_at ? (
                    <Badge variant="success">Accepted</Badge>
                  ) : (
                    <Badge variant="warning">Pending</Badge>
                  )}
                </div>
              </div>
              {!invite.accepted_at && (
                <button
                  onClick={() => handleRevoke(invite.id)}
                  className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-all duration-200"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </CardContent>
          </Card>
        ))}
        {invites.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-6">No invites sent yet.</p>
        )}
      </div>
    </div>
  );
}
```

### Step 10: Add accept-invite page

Create `frontend/src/app/(auth)/accept-invite/page.tsx`:

```typescript
"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import api from "@/lib/api";

function AcceptInviteForm() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const router = useRouter();
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleAccept() {
    setLoading(true);
    setError("");
    try {
      await api.post("/invites/accept", { token, full_name: name, password });
      router.push("/login?accepted=1");
    } catch {
      setError("Invalid or expired invite link.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm space-y-4 p-8 bg-white rounded-xl shadow-sm border border-gray-200">
        <h1 className="text-xl font-bold text-gray-900">Accept Invitation</h1>
        <p className="text-sm text-gray-500">Create your account to join the workspace.</p>
        <Input label="Your name" value={name} onChange={(e) => setName(e.target.value)} />
        <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <p className="text-sm text-red-500">{error}</p>}
        <Button onClick={handleAccept} loading={loading} className="w-full" disabled={!name || !password}>
          Join Workspace
        </Button>
      </div>
    </div>
  );
}

export default function AcceptInvitePage() {
  return <Suspense><AcceptInviteForm /></Suspense>;
}
```

### Step 11: Add Team link to settings nav

Check `frontend/src/app/(dashboard)/layout.tsx` for the sidebar nav. Add a "Team" link pointing to `/settings/team` in the settings section.

### Step 12: Verify

```bash
# Backend: test invite creation
curl -X POST http://localhost:8000/api/v1/workspaces/{wid}/invites \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "test2@example.com", "role": "member"}'
# Expected: 200 with invite object including token

# Check backend logs for invite URL
# Navigate to the invite URL in browser → should see accept form
```

### Step 13: Commit

```bash
git add backend/app/models/invites.py \
        backend/app/schemas/invites.py \
        backend/app/services/invite_service.py \
        backend/app/api/v1/invites.py \
        backend/app/models/__init__.py \
        backend/app/main.py \
        backend/alembic/versions/ \
        frontend/src/app/(dashboard)/settings/team/ \
        frontend/src/app/(auth)/accept-invite/
git commit -m "feat: workspace invitations with email links and team management page"
```

---

## Task 6: Lead Capture Widget Form

**What:** Add an optional pre-chat lead capture form to the widget. When `lead_capture_enabled` is true on the chatbot, the widget shows a form (name + email) before the first message. Submitted data is saved as a `Contact` record.

**Files:**
- Modify: `backend/app/models/chatbots.py` — add `lead_capture_enabled`, `lead_capture_fields`
- Create migration
- Modify: `backend/app/api/v1/public.py` — add `POST /public/chat/{chatbot_id}/lead` endpoint
- Modify: `backend/app/schemas/public.py` — add lead capture fields to widget config
- Modify: `widget/src/config.ts` — add `leadCaptureEnabled`, `leadCaptureFields`
- Modify: `widget/src/widget.ts` — show lead form before first chat
- Modify: `widget/src/ui/styles.ts` — style lead form
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx` — toggle + field config

### Step 1: Add lead capture fields to Chatbot model

In `backend/app/models/chatbots.py`, add:

```python
lead_capture_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
lead_capture_fields: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
# e.g. ["name", "email", "phone"]
```

### Step 2: Create migration

```bash
make migrate-create msg="add_chatbot_lead_capture"
```

Edit migration:
```python
def upgrade() -> None:
    op.add_column("chatbots", sa.Column("lead_capture_enabled", sa.Boolean(), server_default="FALSE", nullable=False))
    op.add_column("chatbots", sa.Column("lead_capture_fields", postgresql.ARRAY(sa.Text()), nullable=True))

def downgrade() -> None:
    op.drop_column("chatbots", "lead_capture_fields")
    op.drop_column("chatbots", "lead_capture_enabled")
```

```bash
make migrate
```

### Step 3: Expose in WidgetConfigResponse

In `backend/app/schemas/public.py` (wherever `WidgetConfigResponse` is), add:

```python
lead_capture_enabled: bool = False
lead_capture_fields: list[str] = ["name", "email"]
```

In the endpoint, populate from chatbot:

```python
lead_capture_enabled=chatbot.lead_capture_enabled,
lead_capture_fields=chatbot.lead_capture_fields or ["name", "email"],
```

### Step 4: Add lead submission endpoint

In `backend/app/api/v1/public.py`, add:

```python
from app.models.contacts import Contact

class LeadCapture(BaseModel):
    chatbot_id: uuid.UUID
    session_id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None

@public_router.post("/chat/lead")
async def capture_lead(body: LeadCapture, db: AsyncSession = Depends(get_db)):
    chatbot_result = await db.execute(select(Chatbot).where(Chatbot.id == body.chatbot_id))
    chatbot = chatbot_result.scalar_one_or_none()
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    # Find or create contact
    existing = None
    if body.email:
        result = await db.execute(
            select(Contact).where(
                Contact.workspace_id == chatbot.workspace_id,
                Contact.email == body.email,
            )
        )
        existing = result.scalar_one_or_none()

    if not existing:
        contact = Contact(
            workspace_id=chatbot.workspace_id,
            name=body.name,
            email=body.email,
            phone=body.phone,
        )
        db.add(contact)
        await db.commit()
        return {"status": "created"}

    return {"status": "existing"}
```

### Step 5: Update widget config.ts

In `widget/src/config.ts`, add:

```typescript
leadCaptureEnabled: boolean;
leadCaptureFields: string[];  // ["name", "email"]
```

In `widget/src/index.ts` (config fetch), add:

```typescript
leadCaptureEnabled: data.lead_capture_enabled || false,
leadCaptureFields: data.lead_capture_fields || ["name", "email"],
```

### Step 6: Render lead form in widget.ts

In `widget/src/widget.ts`, add a `leadFormSubmitted` flag and intercept the first message:

```typescript
private leadFormSubmitted = false;

private toggle(): void {
  this.isOpen = !this.isOpen;
  this.launcher.setOpen(this.isOpen);
  this.chatWindow.setOpen(this.isOpen);

  if (this.isOpen) {
    this.launcher.showUnread(false);
    if (!this.hasShownWelcome) {
      this.showWelcomeMessage();
      this.hasShownWelcome = true;
      // Show lead form if enabled and not yet submitted
      if (this.config.leadCaptureEnabled && !this.leadFormSubmitted) {
        this.showLeadForm();
        return;
      }
    }
    setTimeout(() => this.chatWindow.focusInput(), 300);
  }
}

private showLeadForm(): void {
  this.chatWindow.setInputDisabled(true);

  const form = document.createElement("div");
  form.className = "pulse-lead-form";

  const fields = this.config.leadCaptureFields;

  const inputs: Record<string, HTMLInputElement> = {};
  fields.forEach((field) => {
    const label = document.createElement("label");
    label.className = "pulse-lead-label";
    label.textContent = field.charAt(0).toUpperCase() + field.slice(1);
    const input = document.createElement("input");
    input.className = "pulse-lead-input";
    input.type = field === "email" ? "email" : "text";
    input.placeholder = field.charAt(0).toUpperCase() + field.slice(1);
    inputs[field] = input;
    form.appendChild(label);
    form.appendChild(input);
  });

  const btn = document.createElement("button");
  btn.className = "pulse-lead-btn";
  btn.textContent = "Start Chat";
  btn.onclick = async () => {
    const data: Record<string, string> = {};
    fields.forEach((f) => { data[f] = inputs[f]?.value || ""; });

    await fetch(`${this.config.apiUrl}/public/chat/lead`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chatbot_id: this.config.chatbotId, session_id: this.sessionId, ...data }),
    }).catch(() => {});

    form.remove();
    this.leadFormSubmitted = true;
    this.chatWindow.setInputDisabled(false);
    setTimeout(() => this.chatWindow.focusInput(), 100);
  };

  form.appendChild(btn);
  this.chatWindow.messagesContainer.appendChild(form);
}
```

### Step 7: Style lead form

In `widget/src/ui/styles.ts`, add to the styles string:

```css
.pulse-lead-form {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pulse-lead-label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}
.pulse-lead-input {
  width: 100%;
  border: 1.5px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}
.pulse-lead-input:focus {
  border-color: ${primaryColor};
}
.pulse-lead-btn {
  background: ${primaryColor};
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 4px;
}
```

### Step 8: Add toggle to customize page

In `frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx`, add:

```typescript
// State
const [leadCaptureEnabled, setLeadCaptureEnabled] = useState(chatbot?.lead_capture_enabled || false);
const [leadCaptureFields, setLeadCaptureFields] = useState<string[]>(
  chatbot?.lead_capture_fields || ["name", "email"]
);
```

Add UI section:
```tsx
<div className="border-t border-gray-100 pt-4">
  <div className="flex items-center justify-between mb-2">
    <label className="text-sm font-medium text-gray-900">Lead Capture Form</label>
    <input
      type="checkbox"
      checked={leadCaptureEnabled}
      onChange={(e) => setLeadCaptureEnabled(e.target.checked)}
      className="h-4 w-4 rounded border-gray-300 text-primary-600"
    />
  </div>
  {leadCaptureEnabled && (
    <div className="flex gap-2">
      {["name", "email", "phone"].map((field) => (
        <label key={field} className="flex items-center gap-1 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={leadCaptureFields.includes(field)}
            onChange={(e) => {
              setLeadCaptureFields(e.target.checked
                ? [...leadCaptureFields, field]
                : leadCaptureFields.filter((f) => f !== field)
              );
            }}
          />
          {field.charAt(0).toUpperCase() + field.slice(1)}
        </label>
      ))}
    </div>
  )}
</div>
```

Include in save payload: `lead_capture_enabled: leadCaptureEnabled, lead_capture_fields: leadCaptureFields`.

### Step 9: Rebuild widget and verify

```bash
cd /Users/yvanveldeman/dev/pulse/widget && npm run build
```

Enable lead capture in chatbot Customize settings. Open the test chat widget. A form should appear with Name/Email fields before chat starts. Fill and click "Start Chat" → form disappears → chat is now enabled.

### Step 10: Commit

```bash
git add backend/app/models/chatbots.py \
        backend/app/api/v1/public.py \
        backend/app/schemas/public.py \
        backend/alembic/versions/ \
        widget/src/widget.ts \
        widget/src/ui/styles.ts \
        widget/src/config.ts \
        frontend/src/app/(dashboard)/chatbots/[id]/customize/page.tsx
git commit -m "feat: lead capture pre-chat form in widget with contact creation"
```

---

## Task 7: AI Actions Framework

**What:** The largest gap. AI Actions allow the bot to trigger structured actions mid-conversation using OpenAI function calling. Phase 1 scope: support one built-in action type (`collect_lead`) and one custom action type (`webhook`) with configurable trigger conditions.

**Architecture:**
- `ChatbotAction` DB table: defines available actions per chatbot (type, name, trigger description, config)
- `ActionEvent` DB table: logs when actions fire (conversation, action type, payload, status)
- `chat_service.py` uses OpenAI function calling to detect when to fire an action
- Widget receives action event in SSE stream and renders appropriate UI (for `collect_lead`: inline form; for `webhook`: silent)
- Frontend: new "Actions" tab on chatbot detail page

**Files:**
- Create: `backend/app/models/actions.py`
- Create migration
- Create: `backend/app/schemas/actions.py`
- Create: `backend/app/services/action_service.py`
- Create: `backend/app/api/v1/actions.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/chat_service.py` (or wherever LLM is called) — inject tool definitions
- Modify: `backend/app/api/v1/public.py` — emit `action` SSE event
- Modify: `widget/src/widget.ts` — handle `action` event from SSE
- Modify: `widget/src/api.ts` — parse `action` SSE event type
- Create: `frontend/src/app/(dashboard)/chatbots/[id]/actions/page.tsx`
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/page.tsx` — add Actions tab

### Step 1: Create actions model

Create `backend/app/models/actions.py`:

```python
import uuid
from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChatbotAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chatbot_actions"

    chatbot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    # e.g. "collect_lead", "webhook", "create_ticket", "book_demo"
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Human label shown in the widget (e.g. "Get a demo")
    trigger_description: Mapped[str] = mapped_column(Text, nullable=False)
    # Describes when the AI should fire this action (used as the function description)
    config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # action_type="webhook" → {"url": "https://...", "secret": "..."}
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))


class ActionEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "action_events"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    chatbot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    action_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbot_actions.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'fired'"))
    # "fired", "completed", "failed"
```

### Step 2: Register models

In `backend/app/models/__init__.py`:

```python
from app.models.actions import ChatbotAction, ActionEvent  # noqa: F401
```

### Step 3: Create migration

```bash
make migrate-create msg="add_ai_actions"
```

Edit migration (two tables: `chatbot_actions`, `action_events`).

```bash
make migrate
```

### Step 4: Create action schemas

Create `backend/app/schemas/actions.py`:

```python
from pydantic import BaseModel
import uuid
from datetime import datetime


class ActionCreate(BaseModel):
    action_type: str  # "collect_lead" | "webhook" | "create_ticket"
    name: str
    trigger_description: str
    config: dict = {}
    is_enabled: bool = True


class ActionResponse(BaseModel):
    id: uuid.UUID
    chatbot_id: uuid.UUID
    action_type: str
    name: str
    trigger_description: str
    config: dict
    is_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ActionUpdate(BaseModel):
    name: str | None = None
    trigger_description: str | None = None
    config: dict | None = None
    is_enabled: bool | None = None
```

### Step 5: Create action service

Create `backend/app/services/action_service.py`:

```python
import uuid
import httpx
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.actions import ChatbotAction, ActionEvent

logger = logging.getLogger(__name__)


async def list_actions(db: AsyncSession, chatbot_id: uuid.UUID) -> list[ChatbotAction]:
    result = await db.execute(
        select(ChatbotAction).where(ChatbotAction.chatbot_id == chatbot_id, ChatbotAction.is_enabled == True)  # noqa: E712
    )
    return list(result.scalars().all())


async def create_action(db: AsyncSession, workspace_id: uuid.UUID, chatbot_id: uuid.UUID, data: dict) -> ChatbotAction:
    action = ChatbotAction(workspace_id=workspace_id, chatbot_id=chatbot_id, **data)
    db.add(action)
    await db.flush()
    return action


async def execute_action(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    action: ChatbotAction,
    arguments: dict,
) -> dict:
    """Execute a triggered action and log it. Returns data to send to widget."""
    event = ActionEvent(
        workspace_id=workspace_id,
        chatbot_id=chatbot_id,
        conversation_id=conversation_id,
        action_id=action.id,
        action_type=action.action_type,
        payload=arguments,
        status="fired",
    )
    db.add(event)
    await db.flush()

    if action.action_type == "webhook":
        url = action.config.get("url")
        if url:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(url, json={"action": action.name, **arguments})
                event.status = "completed"
            except Exception as e:
                logger.error(f"Webhook action failed: {e}")
                event.status = "failed"
        return {"type": "webhook", "name": action.name}

    elif action.action_type == "collect_lead":
        # Widget will render a form — no server-side action needed yet
        event.status = "completed"
        return {
            "type": "collect_lead",
            "name": action.name,
            "fields": action.config.get("fields", ["name", "email"]),
        }

    return {"type": action.action_type, "name": action.name}


def build_tools_for_chatbot(actions: list[ChatbotAction]) -> list[dict]:
    """Build OpenAI function definitions from chatbot actions."""
    tools = []
    for action in actions:
        if action.action_type == "collect_lead":
            tools.append({
                "type": "function",
                "function": {
                    "name": f"action_{str(action.id).replace('-', '_')}",
                    "description": action.trigger_description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string", "description": "Why the lead form is being shown"}
                        },
                        "required": [],
                    },
                },
            })
        elif action.action_type == "webhook":
            tools.append({
                "type": "function",
                "function": {
                    "name": f"action_{str(action.id).replace('-', '_')}",
                    "description": action.trigger_description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string", "description": "Brief summary of why this action was triggered"}
                        },
                        "required": ["summary"],
                    },
                },
            })
    return tools
```

### Step 6: Modify chat_service.py to inject tools

Read `backend/app/services/chat_service.py` to find where the OpenAI `chat.completions.create` call is made. Modify it to:

1. Load the chatbot's actions from DB before the LLM call:
```python
from app.services.action_service import list_actions, build_tools_for_chatbot, execute_action

actions = await list_actions(db, chatbot_id)
tools = build_tools_for_chatbot(actions)
```

2. Pass `tools=tools` (if non-empty) to the `chat.completions.create` call.

3. After the response, check for `tool_calls` in the response message:
```python
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        # Match tool call name back to action
        action_id_str = tool_call.function.name.replace("action_", "").replace("_", "-")
        matched_action = next((a for a in actions if str(a.id) == action_id_str), None)
        if matched_action:
            import json
            args = json.loads(tool_call.function.arguments or "{}")
            action_data = await execute_action(db, workspace_id, chatbot_id, conversation_id, matched_action, args)
            # Yield action SSE event BEFORE the text response
            yield f"data: {json.dumps({'type': 'action', 'data': action_data})}\n\n"
```

**Note:** This requires reading `chat_service.py` carefully before modifying — the exact streaming implementation may vary.

### Step 7: Handle action SSE event in widget/src/api.ts

In `widget/src/api.ts`, in the SSE parser loop (where `type === "token"` and `type === "done"` are handled), add:

```typescript
if (parsed.type === "action") {
  callbacks.onAction?.(parsed.data);
  continue;
}
```

Add `onAction` to the callback type definition.

### Step 8: Handle action in widget/src/widget.ts

In the `streamChat` callback options, add:

```typescript
onAction: (actionData: { type: string; name: string; fields?: string[] }) => {
  if (actionData.type === "collect_lead") {
    this.showLeadForm();
    // reuse the lead form from Task 6
  }
  // webhook actions are silent from widget perspective
},
```

### Step 9: Create actions API router

Create `backend/app/api/v1/actions.py`:

```python
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_workspace
from app.schemas.actions import ActionCreate, ActionResponse, ActionUpdate
from app.services import action_service
from app.models.actions import ChatbotAction
from sqlalchemy import select

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["actions"])


@router.post("/chatbots/{chatbot_id}/actions", response_model=ActionResponse)
async def create_action(
    chatbot_id: uuid.UUID,
    body: ActionCreate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    action = await action_service.create_action(db, workspace_id, chatbot_id, body.model_dump())
    await db.commit()
    return action


@router.get("/chatbots/{chatbot_id}/actions", response_model=list[ActionResponse])
async def list_actions(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await action_service.list_actions(db, chatbot_id)


@router.patch("/chatbots/{chatbot_id}/actions/{action_id}", response_model=ActionResponse)
async def update_action(
    chatbot_id: uuid.UUID,
    action_id: uuid.UUID,
    body: ActionUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatbotAction).where(ChatbotAction.id == action_id, ChatbotAction.chatbot_id == chatbot_id)
    )
    action = result.scalar_one()
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(action, k, v)
    await db.commit()
    return action


@router.delete("/chatbots/{chatbot_id}/actions/{action_id}", status_code=204)
async def delete_action(
    chatbot_id: uuid.UUID,
    action_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatbotAction).where(ChatbotAction.id == action_id, ChatbotAction.chatbot_id == chatbot_id)
    )
    action = result.scalar_one()
    await db.delete(action)
    await db.commit()
```

### Step 10: Register actions router

In `backend/app/main.py`:

```python
from app.api.v1.actions import router as actions_router
app.include_router(actions_router, prefix="/api/v1")
```

### Step 11: Create Actions tab in frontend

Create `frontend/src/app/(dashboard)/chatbots/[id]/actions/page.tsx`:

```typescript
"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { Trash2, Zap } from "lucide-react";
import api from "@/lib/api";

const ACTION_TYPES = [
  { value: "collect_lead", label: "Collect Lead", description: "Show a form to capture name and email" },
  { value: "webhook", label: "Webhook", description: "POST data to a custom URL" },
];

interface Action {
  id: string;
  action_type: string;
  name: string;
  trigger_description: string;
  config: Record<string, unknown>;
  is_enabled: boolean;
}

export default function ActionsPage() {
  const { id: chatbotId } = useParams<{ id: string }>();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [actions, setActions] = useState<Action[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    action_type: "collect_lead",
    name: "",
    trigger_description: "",
    config: {} as Record<string, unknown>,
  });

  useEffect(() => {
    if (!workspace) return;
    api
      .get(`/workspaces/${workspace.id}/chatbots/${chatbotId}/actions`)
      .then((r) => setActions(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, chatbotId]);

  async function handleCreate() {
    if (!workspace) return;
    setSaving(true);
    try {
      const res = await api.post(`/workspaces/${workspace.id}/chatbots/${chatbotId}/actions`, form);
      setActions((prev) => [...prev, res.data]);
      setShowForm(false);
      setForm({ action_type: "collect_lead", name: "", trigger_description: "", config: {} });
    } catch {
      // handle error
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(actionId: string) {
    if (!workspace) return;
    await api.delete(`/workspaces/${workspace.id}/chatbots/${chatbotId}/actions/${actionId}`);
    setActions((prev) => prev.filter((a) => a.id !== actionId));
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner className="h-6 w-6 text-primary-600" /></div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">AI Actions</h2>
          <p className="text-sm text-gray-500">Actions the AI can trigger during conversations.</p>
        </div>
        <Button onClick={() => setShowForm(true)} size="sm">
          <Zap className="h-4 w-4 mr-1" />
          Add Action
        </Button>
      </div>

      {actions.length === 0 && !showForm && (
        <Card>
          <CardContent className="flex flex-col items-center py-12 text-gray-400">
            <Zap className="h-10 w-10 mb-3" />
            <p className="text-sm font-medium">No actions yet</p>
            <p className="text-xs mt-1">Add actions the AI can trigger mid-conversation</p>
          </CardContent>
        </Card>
      )}

      {showForm && (
        <Card className="mb-4">
          <CardContent className="py-5 space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1 block">Action Type</label>
              <select
                value={form.action_type}
                onChange={(e) => setForm({ ...form, action_type: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                {ACTION_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label} — {t.description}</option>
                ))}
              </select>
            </div>
            <Input
              label="Button / Action Label"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder='e.g. "Get a Demo"'
            />
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1 block">
                When should the AI trigger this? (used as AI instruction)
              </label>
              <textarea
                value={form.trigger_description}
                onChange={(e) => setForm({ ...form, trigger_description: e.target.value })}
                rows={3}
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="Trigger this when the user expresses interest in a demo or pricing"
              />
            </div>
            {form.action_type === "webhook" && (
              <Input
                label="Webhook URL"
                value={(form.config.url as string) || ""}
                onChange={(e) => setForm({ ...form, config: { ...form.config, url: e.target.value } })}
                placeholder="https://your-server.com/webhook"
              />
            )}
            <div className="flex gap-2">
              <Button onClick={handleCreate} loading={saving} disabled={!form.name || !form.trigger_description}>
                Save Action
              </Button>
              <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-2">
        {actions.map((action) => (
          <Card key={action.id}>
            <CardContent className="py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
                  <Zap className="h-4 w-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-900">{action.name}</span>
                    <Badge variant="default">{action.action_type}</Badge>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">{action.trigger_description}</p>
                </div>
              </div>
              <button
                onClick={() => handleDelete(action.id)}
                className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-all duration-200"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

### Step 12: Add Actions tab to chatbot detail page

In `frontend/src/app/(dashboard)/chatbots/[id]/page.tsx`, the page has tabs (Sources, Settings, etc.). Add an "Actions" tab that navigates to `/chatbots/{id}/actions`.

### Step 13: End-to-end verification

```bash
# 1. Create a test action via API
curl -X POST http://localhost:8000/api/v1/workspaces/{wid}/chatbots/{cid}/actions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "collect_lead",
    "name": "Get Demo",
    "trigger_description": "Use this when the user asks about pricing or wants a demo",
    "config": {}
  }'

# 2. Test chat and ask about pricing
# Expected: SSE stream includes an "action" event of type "collect_lead"
# Widget renders a lead form inline
```

### Step 14: Commit

```bash
git add backend/app/models/actions.py \
        backend/app/schemas/actions.py \
        backend/app/services/action_service.py \
        backend/app/api/v1/actions.py \
        backend/app/main.py \
        backend/app/models/__init__.py \
        backend/app/services/chat_service.py \
        backend/alembic/versions/ \
        widget/src/widget.ts \
        widget/src/api.ts \
        frontend/src/app/(dashboard)/chatbots/[id]/actions/
git commit -m "feat: AI Actions framework — collect_lead and webhook action types with OpenAI function calling"
```

---

## Summary of Changes

| Task | Migrations | New Files | Modified Files |
|---|---|---|---|
| 1. Competitive Intel | — | `intelligence/competitive/page.tsx` | `intelligence/page.tsx`, `intelligence.py` |
| 2. Quick Replies | 1 (quick_replies col) | — | `chatbots.py`, `widget.ts`, `styles.ts`, `customize/page.tsx` |
| 3. Integrations Fix | — | `hubspot.py`, `linear.py` | `integrations/page.tsx`, `score_lead.py`, `cluster_feature_requests.py` |
| 4. KB Breadth | — | — | `documents.py`, `AddSourceModal.tsx`, `SourcesTab.tsx`, `api-functions.ts` |
| 5. Invitations | 1 (workspace_invites) | `invites.py`, `invite_service.py`, `invites router`, `settings/team/page.tsx`, `accept-invite/page.tsx` | `main.py`, `models/__init__.py` |
| 6. Lead Capture | 1 (lead_capture cols) | — | `chatbots.py`, `public.py`, `widget.ts`, `styles.ts`, `customize/page.tsx` |
| 7. AI Actions | 2 (chatbot_actions, action_events) | `actions.py`, `action_service.py`, `actions router`, `chatbots/[id]/actions/page.tsx` | `main.py`, `chat_service.py`, `widget.ts`, `api.ts` |

**Total migrations to run:** 4 new migrations (Tasks 2, 5, 6, 7)

**Execution order:** Tasks can be done in order 1→7. Tasks 1, 3, 4 have no DB migrations and can be done first for quick wins.
