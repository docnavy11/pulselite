# Workspace-Level OpenRouter BYOK Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace per-chatbot BYOK with a single workspace-level OpenRouter API key; admin selects allowed models; chatbot model picker is limited to those models.

**Architecture:** Two new JSONB/Text columns on `workspaces`; three new REST endpoints; new `openrouter_client.py` in the LLM service; key threaded from `handle_message → process_query → stream_response`; frontend settings page + updated chatbot SettingsTab.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, Alembic, Fernet encryption, OpenAI SDK (custom base_url), Next.js 15, TypeScript, Tailwind, Zustand.

---

## Background

- `backend/app/services/resolution_service.py` — `handle_message()` drives every chat request; it calls `process_query(db, message, chatbot, conversation_id)` from the RAG engine
- `backend/app/services/rag/engine.py` — `process_query()` calls `stream_response(messages, chatbot)` from the generator
- `backend/app/services/rag/generator.py` — `stream_response()` calls `get_llm_client(chatbot.llm_provider, api_key=...)` — this is where we plug in the workspace key
- `backend/app/services/llm/__init__.py` — `get_llm_client(provider, api_key)` factory; currently supports `openai`, `anthropic`, `google`
- `backend/app/models/organizational.py` — `Workspace` model lives here; add two new columns
- `backend/app/api/v1/workspaces.py` — workspace router; add three new endpoints here
- `backend/app/services/encryption.py` — `encrypt_api_key()` / `decrypt_api_key()` using Fernet; re-use for the workspace key
- `frontend/src/app/(dashboard)/chatbots/[id]/SettingsTab.tsx` — currently has hard-coded `LLM_PROVIDERS` + `LLM_MODELS`; replace with workspace-fetched list
- `frontend/src/components/layout/Sidebar.tsx` — add "AI Models" nav item
- `frontend/src/lib/api-functions.ts` — add `getLLMSettings`, `updateLLMSettings`, `getOpenRouterModels`
- `frontend/src/lib/types.ts` — add `LLMSettings` and `OpenRouterModel` types

---

### Task 1: Alembic migration — add columns to workspaces

**Files:**
- Create: `backend/alembic/versions/add_workspace_openrouter.py`

**Step 1: Create the migration file**

```python
# backend/alembic/versions/add_workspace_openrouter.py
"""add openrouter columns to workspaces

Revision ID: add_workspace_openrouter
Revises: add_2fa
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "add_workspace_openrouter"
down_revision = "add_2fa"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workspaces",
        sa.Column("openrouter_api_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "allowed_models",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade():
    op.drop_column("workspaces", "allowed_models")
    op.drop_column("workspaces", "openrouter_api_key")
```

**Step 2: Run the migration**

```bash
make migrate
```

Expected: `Running upgrade add_2fa -> add_workspace_openrouter, add openrouter columns to workspaces`

**Step 3: Commit**

```bash
git add backend/alembic/versions/add_workspace_openrouter.py
git commit -m "feat: add openrouter_api_key + allowed_models to workspaces"
```

---

### Task 2: SQLAlchemy model — add columns to Workspace

**Files:**
- Modify: `backend/app/models/organizational.py`

**Step 1: Add two mapped columns after `white_label_enabled`**

In `backend/app/models/organizational.py`, find the `white_label_enabled` line and add after it:

```python
    openrouter_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_models: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )
```

The `JSONB` import already exists at the top of the file.

**Step 2: Restart backend to pick up model changes**

```bash
docker compose restart backend
```

**Step 3: Commit**

```bash
git add backend/app/models/organizational.py
git commit -m "feat: Workspace model — openrouter_api_key + allowed_models columns"
```

---

### Task 3: Backend — OpenRouter LLM client

**Files:**
- Create: `backend/app/services/llm/openrouter_client.py`
- Modify: `backend/app/services/llm/__init__.py`

**Step 1: Write a failing test**

```python
# backend/tests/unit/test_openrouter_client.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_openrouter_client_streams_tokens():
    """OpenRouterLLMClient.stream_generate yields tokens via OpenAI SDK with custom base_url."""
    from app.services.llm.openrouter_client import OpenRouterLLMClient

    client = OpenRouterLLMClient(api_key="sk-or-test")

    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock()]
    mock_chunk.choices[0].delta.content = "hello"

    async def fake_stream():
        yield mock_chunk

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=fake_stream())

    with patch("app.services.llm.openrouter_client.AsyncOpenAI", return_value=mock_openai):
        tokens = []
        async for token in client.stream_generate(
            messages=[{"role": "user", "content": "hi"}],
            model="openai/gpt-4o-mini",
        ):
            tokens.append(token)

    assert tokens == ["hello"]


def test_get_llm_client_openrouter():
    """get_llm_client('openrouter') returns an OpenRouterLLMClient."""
    from app.services.llm import get_llm_client
    from app.services.llm.openrouter_client import OpenRouterLLMClient

    client = get_llm_client("openrouter", api_key="sk-or-test")
    assert isinstance(client, OpenRouterLLMClient)
```

**Step 2: Run test — expect failure**

```bash
docker compose exec backend pytest tests/unit/test_openrouter_client.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'app.services.llm.openrouter_client'`

**Step 3: Create the OpenRouter client**

```python
# backend/app/services/llm/openrouter_client.py
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from app.config import settings
from app.services.llm.base import BaseLLMClient

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLMClient(BaseLLMClient):
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.OPENROUTER_API_KEY
        self._client = AsyncOpenAI(api_key=key, base_url=OPENROUTER_BASE_URL)

    async def stream_generate(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]:
        stream = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

**Step 4: Register in the factory**

In `backend/app/services/llm/__init__.py`, add the `openrouter` case:

```python
from app.services.llm.base import BaseLLMClient
from app.services.llm.openai_client import OpenAILLMClient
from app.services.llm.anthropic_client import AnthropicLLMClient
from app.services.llm.google_client import GoogleLLMClient
from app.services.llm.openrouter_client import OpenRouterLLMClient


def get_llm_client(provider: str, api_key: str | None = None) -> BaseLLMClient:
    match provider:
        case "openai":
            return OpenAILLMClient(api_key=api_key)
        case "anthropic":
            return AnthropicLLMClient(api_key=api_key)
        case "google":
            return GoogleLLMClient(api_key=api_key)
        case "openrouter":
            return OpenRouterLLMClient(api_key=api_key)
        case _:
            raise ValueError(f"Unsupported LLM provider: {provider}")
```

**Step 5: Run tests — expect pass**

```bash
docker compose exec backend pytest tests/unit/test_openrouter_client.py -v
```

Expected: 2 PASSED

**Step 6: Commit**

```bash
git add backend/app/services/llm/openrouter_client.py backend/app/services/llm/__init__.py backend/tests/unit/test_openrouter_client.py
git commit -m "feat: add OpenRouterLLMClient and register in get_llm_client factory"
```

---

### Task 4: Thread workspace key through the RAG pipeline

The goal: `handle_message` loads + decrypts the workspace OpenRouter key once, passes it all the way to `stream_response`.

**Files:**
- Modify: `backend/app/services/rag/generator.py`
- Modify: `backend/app/services/rag/engine.py`
- Modify: `backend/app/services/resolution_service.py`

**Step 1: Update `generator.py` — accept optional `openrouter_key`**

Replace the full `stream_response` function:

```python
async def stream_response(
    messages: list[dict],
    chatbot: Chatbot,
    openrouter_key: str | None = None,
) -> AsyncGenerator[str, None]:
    # Workspace OpenRouter key takes priority over chatbot-level byoak
    api_key = openrouter_key
    if api_key is None and chatbot.byoak:
        try:
            from app.services.encryption import decrypt_api_key
            api_key = decrypt_api_key(chatbot.byoak)
        except Exception:
            logger.warning(f"Failed to decrypt BYOK key for chatbot {chatbot.id}, using platform key")

    # If workspace OpenRouter key provided, always use openrouter provider
    provider = "openrouter" if openrouter_key else chatbot.llm_provider
    client = get_llm_client(provider, api_key=api_key)
    async for token in client.stream_generate(
        messages=messages,
        model=chatbot.llm_model,
        temperature=chatbot.temperature,
        max_tokens=chatbot.max_tokens,
    ):
        yield token
```

**Step 2: Update `engine.py` — thread `openrouter_key` through `process_query`**

Change the `process_query` signature to accept the key and pass it to `stream_response`:

```python
async def process_query(
    db: AsyncSession,
    query: str,
    chatbot: Chatbot,
    conversation_id: uuid.UUID | None = None,
    openrouter_key: str | None = None,
) -> AsyncGenerator[RAGResult | str, None]:
```

Then at the `stream_response` call (line ~106), update to:

```python
    async for token in stream_response(messages, chatbot, openrouter_key=openrouter_key):
```

**Step 3: Update `resolution_service.py` — load workspace key**

At the top of `handle_message`, after loading the conversation, add key loading logic. Also update the `process_query` call.

At the top of the file, add the import:

```python
from app.models.organizational import Workspace
from app.services.encryption import decrypt_api_key
```

Inside `handle_message`, before the `process_query` call, add:

```python
    # Load workspace OpenRouter key if configured
    openrouter_key: str | None = None
    ws_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = ws_result.scalar_one_or_none()
    if ws and ws.openrouter_api_key:
        try:
            openrouter_key = decrypt_api_key(ws.openrouter_api_key)
        except Exception:
            logger.warning(f"Failed to decrypt workspace OpenRouter key for {workspace_id}")
```

Then update the `process_query` call:

```python
    async for item in process_query(db, message, chatbot, conversation_id, openrouter_key=openrouter_key):
```

Also add `select` to the existing sqlalchemy imports if not already there (it is — check `from sqlalchemy import select` in the file... resolution_service.py doesn't import sqlalchemy directly. Add at the top):

```python
from sqlalchemy import select
```

**Step 4: Restart backend and verify no import errors**

```bash
docker compose restart backend
docker compose logs backend --tail=20
```

Expected: No traceback, server starts on port 8000.

**Step 5: Run existing tests to confirm no regression**

```bash
docker compose exec backend pytest tests/unit/ -v --tb=short -q
```

Expected: All existing tests pass (or close to it — check any failures are pre-existing).

**Step 6: Commit**

```bash
git add backend/app/services/rag/generator.py backend/app/services/rag/engine.py backend/app/services/resolution_service.py
git commit -m "feat: thread workspace OpenRouter key through RAG pipeline"
```

---

### Task 5: Backend API — LLM settings endpoints

**Files:**
- Modify: `backend/app/api/v1/workspaces.py`

**Step 1: Write a failing test**

```python
# backend/tests/unit/test_llm_settings_api.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_llm_settings_no_key(auth_client: AsyncClient, workspace_id: str):
    """GET /llm-settings returns key_set=False when no key configured."""
    resp = await auth_client.get(f"/api/v1/workspaces/{workspace_id}/llm-settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["openrouter_api_key_set"] is False
    assert data["allowed_models"] == []


@pytest.mark.asyncio
async def test_put_llm_settings_saves_key(auth_client: AsyncClient, workspace_id: str):
    """PUT /llm-settings encrypts and stores the key."""
    resp = await auth_client.put(
        f"/api/v1/workspaces/{workspace_id}/llm-settings",
        json={"openrouter_api_key": "sk-or-test-key", "allowed_models": ["openai/gpt-4o"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["openrouter_api_key_set"] is True
    assert data["allowed_models"] == ["openai/gpt-4o"]
```

**Step 2: Run test — expect failure**

```bash
docker compose exec backend pytest tests/unit/test_llm_settings_api.py -v
```

Expected: `FAILED` — 404 Not Found (endpoints don't exist yet).

**Step 3: Add the endpoints to `workspaces.py`**

Add these Pydantic models near the top of `workspaces.py` (after the existing model classes):

```python
class LLMSettingsResponse(BaseModel):
    openrouter_api_key_set: bool
    allowed_models: list[str]


class LLMSettingsUpdate(BaseModel):
    openrouter_api_key: str | None = None
    allowed_models: list[str] = []
```

Add these imports at the top of `workspaces.py` if not present:

```python
import httpx
from app.services.encryption import encrypt_api_key, decrypt_api_key
```

Add these three route handlers (place them before the `@router.get("/{workspace_id}/data-retention")` block):

```python
@router.get("/{workspace_id}/llm-settings", response_model=LLMSettingsResponse)
async def get_llm_settings(
    workspace: Workspace = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return LLMSettingsResponse(
        openrouter_api_key_set=bool(workspace.openrouter_api_key),
        allowed_models=workspace.allowed_models or [],
    )


@router.put("/{workspace_id}/llm-settings", response_model=LLMSettingsResponse)
async def update_llm_settings(
    body: LLMSettingsUpdate,
    workspace: Workspace = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    if body.openrouter_api_key is not None:
        if body.openrouter_api_key == "":
            workspace.openrouter_api_key = None
        else:
            workspace.openrouter_api_key = encrypt_api_key(body.openrouter_api_key)
    if len(body.allowed_models) > 100:
        raise HTTPException(status_code=400, detail="allowed_models may not exceed 100 items")
    workspace.allowed_models = body.allowed_models
    await db.commit()
    await db.refresh(workspace)
    return LLMSettingsResponse(
        openrouter_api_key_set=bool(workspace.openrouter_api_key),
        allowed_models=workspace.allowed_models or [],
    )


@router.get("/{workspace_id}/llm-settings/models")
async def list_openrouter_models(
    workspace: Workspace = Depends(get_workspace),
):
    if not workspace.openrouter_api_key:
        raise HTTPException(status_code=400, detail="No OpenRouter API key configured for this workspace")
    try:
        api_key = decrypt_api_key(workspace.openrouter_api_key)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decrypt OpenRouter API key")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch models from OpenRouter")

    data = resp.json()
    # Filter to text generation models only (exclude embedding, image, audio)
    models = [
        {
            "id": m["id"],
            "name": m.get("name", m["id"]),
            "context_length": m.get("context_length"),
            "pricing": m.get("pricing"),
        }
        for m in data.get("data", [])
        if "embedding" not in m["id"] and "image" not in m.get("architecture", {}).get("modality", "")
    ]
    return {"models": models}
```

**Step 4: Restart backend**

```bash
docker compose restart backend
```

**Step 5: Run tests**

```bash
docker compose exec backend pytest tests/unit/test_llm_settings_api.py -v
```

Expected: PASSED (integration tests may need fixtures — skip if fixture setup is complex; manual test via curl is fine).

**Step 6: Quick smoke test via curl**

```bash
# Get a token first
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@pulse.dev","password":"test"}' | jq -r '.tokens.access_token')

WID="350863e7-3dc8-430e-bc23-fd41d4499d7b"

curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/workspaces/$WID/llm-settings | jq
```

Expected: `{"openrouter_api_key_set": false, "allowed_models": []}`

**Step 7: Commit**

```bash
git add backend/app/api/v1/workspaces.py
git commit -m "feat: GET/PUT /llm-settings and GET /llm-settings/models endpoints"
```

---

### Task 6: Frontend types and API functions

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api-functions.ts`

**Step 1: Add types to `types.ts`**

Append to `frontend/src/lib/types.ts`:

```typescript
export interface LLMSettings {
  openrouter_api_key_set: boolean;
  allowed_models: string[];
}

export interface OpenRouterModel {
  id: string;
  name: string;
  context_length: number | null;
  pricing: { prompt: string; completion: string } | null;
}
```

**Step 2: Add API functions to `api-functions.ts`**

Append to `frontend/src/lib/api-functions.ts`:

```typescript
export function getLLMSettings(workspaceId: string): Promise<LLMSettings> {
  return apiClient.get(`/workspaces/${workspaceId}/llm-settings`);
}

export function updateLLMSettings(
  workspaceId: string,
  data: { openrouter_api_key?: string; allowed_models: string[] },
): Promise<LLMSettings> {
  return apiClient.put(`/workspaces/${workspaceId}/llm-settings`, data);
}

export function getOpenRouterModels(workspaceId: string): Promise<{ models: OpenRouterModel[] }> {
  return apiClient.get(`/workspaces/${workspaceId}/llm-settings/models`);
}
```

**Step 3: Verify TypeScript compiles**

```bash
cd /Users/yvanveldeman/dev/pulse/frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors related to these additions.

**Step 4: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api-functions.ts
git commit -m "feat: add LLMSettings types and api-functions for OpenRouter BYOK"
```

---

### Task 7: Frontend — `/settings/llm` page

**Files:**
- Create: `frontend/src/app/(dashboard)/settings/llm/page.tsx`

**Step 1: Create the page**

```tsx
// frontend/src/app/(dashboard)/settings/llm/page.tsx
"use client";

import { useState, useEffect } from "react";
import { Key, Cpu, CheckCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { getLLMSettings, updateLLMSettings, getOpenRouterModels } from "@/lib/api-functions";
import { LLMSettings, OpenRouterModel } from "@/lib/types";
import { useWorkspaceStore } from "@/stores/workspace-store";

export default function LLMSettingsPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);

  // API key card state
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [savingKey, setSavingKey] = useState(false);
  const [keyError, setKeyError] = useState<string | null>(null);
  const [keySuccess, setKeySuccess] = useState(false);

  // Model picker card state
  const [models, setModels] = useState<OpenRouterModel[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelSearch, setModelSearch] = useState("");
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
  const [savingModels, setSavingModels] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);
  const [modelSuccess, setModelSuccess] = useState(false);

  const [pageLoading, setPageLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    getLLMSettings(workspace.id)
      .then((data) => {
        setSettings(data);
        setSelectedModels(new Set(data.allowed_models));
      })
      .finally(() => setPageLoading(false));
  }, [workspace]);

  async function handleSaveKey() {
    if (!workspace) return;
    setKeyError(null);
    setKeySuccess(false);
    setSavingKey(true);
    try {
      const updated = await updateLLMSettings(workspace.id, {
        openrouter_api_key: keyInput || "",
        allowed_models: [...selectedModels],
      });
      setSettings(updated);
      setKeyInput("");
      setKeySuccess(true);
    } catch {
      setKeyError("Failed to save API key. Please try again.");
    } finally {
      setSavingKey(false);
    }
  }

  async function handleLoadModels() {
    if (!workspace) return;
    setModelError(null);
    setLoadingModels(true);
    try {
      const data = await getOpenRouterModels(workspace.id);
      setModels(data.models);
    } catch {
      setModelError("Failed to load models. Ensure your API key is saved and valid.");
    } finally {
      setLoadingModels(false);
    }
  }

  async function handleSaveModels() {
    if (!workspace) return;
    setModelError(null);
    setModelSuccess(false);
    setSavingModels(true);
    try {
      const updated = await updateLLMSettings(workspace.id, {
        allowed_models: [...selectedModels],
      });
      setSettings(updated);
      setModelSuccess(true);
    } catch {
      setModelError("Failed to save model selection.");
    } finally {
      setSavingModels(false);
    }
  }

  function toggleModel(modelId: string) {
    setSelectedModels((prev) => {
      const next = new Set(prev);
      if (next.has(modelId)) next.delete(modelId);
      else next.add(modelId);
      return next;
    });
  }

  const filteredModels = models.filter(
    (m) =>
      m.id.toLowerCase().includes(modelSearch.toLowerCase()) ||
      m.name.toLowerCase().includes(modelSearch.toLowerCase()),
  );

  if (pageLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">AI Models</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure your OpenRouter API key and select which models chatbots in this workspace can use.
        </p>
      </div>

      {/* Card 1 — API Key */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 mb-4">
            <Key className="h-5 w-5 text-primary-600" />
            <h2 className="text-base font-semibold text-gray-900">OpenRouter API Key</h2>
            {settings?.openrouter_api_key_set && (
              <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                <CheckCircle className="h-3 w-3" /> Key saved
              </span>
            )}
          </div>

          <div className="flex gap-3 max-w-lg">
            <input
              type="password"
              placeholder={settings?.openrouter_api_key_set ? "••••••••••••••••••••" : "sk-or-v1-..."}
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <Button onClick={handleSaveKey} loading={savingKey} disabled={!keyInput}>
              Save key
            </Button>
          </div>

          {settings?.openrouter_api_key_set && (
            <button
              onClick={() => {
                setKeyInput(" ");
                setTimeout(() => handleSaveKey(), 0);
              }}
              className="mt-2 text-xs text-red-500 hover:underline"
            >
              Remove key
            </button>
          )}

          {keyError && <p className="mt-3 text-sm text-red-600">{keyError}</p>}
          {keySuccess && <p className="mt-3 text-sm text-green-600">API key saved successfully.</p>}
        </CardContent>
      </Card>

      {/* Card 2 — Allowed Models */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Cpu className="h-5 w-5 text-primary-600" />
              <h2 className="text-base font-semibold text-gray-900">Allowed Models</h2>
              {settings && settings.allowed_models.length > 0 && (
                <span className="rounded-full bg-primary-100 px-2 py-0.5 text-xs font-medium text-primary-700">
                  {settings.allowed_models.length} selected
                </span>
              )}
            </div>
            <Button
              variant="secondary"
              onClick={handleLoadModels}
              loading={loadingModels}
              disabled={!settings?.openrouter_api_key_set}
            >
              <RefreshCw className="h-4 w-4 mr-1" />
              Load from OpenRouter
            </Button>
          </div>

          {!settings?.openrouter_api_key_set && (
            <p className="text-sm text-gray-500 mb-4">Save your API key first to load available models.</p>
          )}

          {models.length > 0 && (
            <>
              <input
                type="text"
                placeholder="Search models..."
                value={modelSearch}
                onChange={(e) => setModelSearch(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />

              <div className="max-h-80 overflow-y-auto space-y-1 border border-gray-200 rounded-lg p-2">
                {filteredModels.map((model) => (
                  <label
                    key={model.id}
                    className="flex items-center gap-3 px-2 py-2 rounded hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedModels.has(model.id)}
                      onChange={() => toggleModel(model.id)}
                      className="h-4 w-4 text-primary-600 border-gray-300 rounded"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{model.name}</p>
                      <p className="text-xs text-gray-500 truncate">{model.id}</p>
                    </div>
                    {model.context_length && (
                      <span className="text-xs text-gray-400 shrink-0">
                        {(model.context_length / 1000).toFixed(0)}k ctx
                      </span>
                    )}
                  </label>
                ))}
              </div>

              <div className="mt-4 flex items-center gap-3">
                <Button onClick={handleSaveModels} loading={savingModels}>
                  Save model selection
                </Button>
                <button
                  onClick={() =>
                    setSelectedModels((prev) => {
                      if (prev.size === filteredModels.length) return new Set();
                      return new Set(filteredModels.map((m) => m.id));
                    })
                  }
                  className="text-sm text-primary-600 hover:underline"
                >
                  {selectedModels.size === filteredModels.length ? "Deselect all" : "Select all"}
                </button>
              </div>
            </>
          )}

          {/* Show saved selections even before loading */}
          {models.length === 0 && settings && settings.allowed_models.length > 0 && (
            <div className="space-y-1">
              {settings.allowed_models.map((m) => (
                <div key={m} className="text-sm text-gray-700 flex items-center gap-2">
                  <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                  {m}
                </div>
              ))}
            </div>
          )}

          {modelError && <p className="mt-3 text-sm text-red-600">{modelError}</p>}
          {modelSuccess && <p className="mt-3 text-sm text-green-600">Model selection saved.</p>}
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/(dashboard)/settings/llm/page.tsx
git commit -m "feat: /settings/llm page — OpenRouter API key + model picker"
```

---

### Task 8: Add "AI Models" to the sidebar

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`

**Step 1: Add the import and nav item**

In `Sidebar.tsx`, add `Cpu` to the lucide-react import:

```typescript
import {
  LayoutDashboard,
  Bot,
  MessageSquare,
  AlertTriangle,
  Brain,
  Settings,
  Users,
  Sparkles,
  Webhook,
  ShieldCheck,
  ShieldAlert,
  Database,
  ClipboardList,
  Cpu,
} from "lucide-react";
```

Then add the nav item in `navItems` array (after `"data-retention"`, before `"audit-logs"`):

```typescript
  { href: "/settings/llm", label: "AI Models", icon: Cpu },
```

**Step 2: Commit**

```bash
git add frontend/src/components/layout/Sidebar.tsx
git commit -m "feat: add AI Models nav item to sidebar"
```

---

### Task 9: Update chatbot SettingsTab — model picker from workspace

Currently `SettingsTab.tsx` uses hard-coded `LLM_PROVIDERS` and `LLM_MODELS`. Replace with a workspace-fetched OpenRouter model list.

**Files:**
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/SettingsTab.tsx`

**Step 1: Replace provider/model UI**

The new behavior:
- Remove the provider `<select>` entirely (OpenRouter is the only option)
- Replace the model `<select>` with a `<select>` populated from `getLLMSettings(workspace.id).allowed_models`
- If `allowed_models` is empty, show all (no restriction) — just a plain text input as fallback

Replace the imports block at the top to add `getLLMSettings`:

```typescript
import { updateChatbot, updateLLMConfig, getLLMSettings } from "@/lib/api-functions";
```

Add state variables (after existing state declarations around line 82):

```typescript
  const [allowedModels, setAllowedModels] = useState<string[]>([]);
  const [modelsLoaded, setModelsLoaded] = useState(false);
```

Add a `useEffect` to load workspace allowed models (after existing state declarations):

```typescript
  useEffect(() => {
    if (!workspace) return;
    getLLMSettings(workspace.id)
      .then((data) => {
        setAllowedModels(data.allowed_models);
        setModelsLoaded(true);
      })
      .catch(() => setModelsLoaded(true));
  }, [workspace]);
```

Remove the `LLM_PROVIDERS` and `LLM_MODELS` constants (lines 46-66 in original file).

In the JSX, find the AI Behavior form and replace the provider/model section with:

```tsx
{/* Model */}
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
  {!modelsLoaded ? (
    <Spinner className="h-5 w-5 text-primary-600" />
  ) : allowedModels.length > 0 ? (
    <select
      value={llmModel}
      onChange={(e) => setLlmModel(e.target.value)}
      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
    >
      {allowedModels.map((m) => (
        <option key={m} value={m}>
          {m}
        </option>
      ))}
    </select>
  ) : (
    <input
      type="text"
      value={llmModel}
      onChange={(e) => setLlmModel(e.target.value)}
      placeholder="e.g. openai/gpt-4o"
      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
    />
  )}
  {allowedModels.length === 0 && modelsLoaded && (
    <p className="mt-1 text-xs text-gray-500">
      Configure allowed models in{" "}
      <a href="/settings/llm" className="text-primary-600 hover:underline">
        AI Models settings
      </a>
      .
    </p>
  )}
</div>
```

Also update `handleSaveLLM` — remove `llm_provider` from the payload or hard-code it to `"openrouter"`:

```typescript
  async function handleSaveLLM(e: React.FormEvent) {
    e.preventDefault();
    setSavingLLM(true);
    try {
      const updated = await updateLLMConfig(workspace.id, chatbot.id, {
        llm_provider: "openrouter",
        llm_model: llmModel,
        temperature: chatbot.temperature,
        max_tokens: chatbot.max_tokens,
        confidence_threshold: chatbot.confidence_threshold,
        retrieval_top_k: chatbot.retrieval_top_k,
        use_reranking: chatbot.use_reranking,
        use_hybrid_retrieval: chatbot.use_hybrid_retrieval,
      });
      onUpdate(updated);
    } catch {
      // existing error handling
    } finally {
      setSavingLLM(false);
    }
  }
```

Add `Spinner` import if not present:

```typescript
import { Spinner } from "@/components/ui/Spinner";
```

**Step 2: Build check**

```bash
cd /Users/yvanveldeman/dev/pulse/frontend && npx tsc --noEmit 2>&1 | head -30
```

Fix any TypeScript errors before committing.

**Step 3: Commit**

```bash
git add frontend/src/app/(dashboard)/chatbots/[id]/SettingsTab.tsx
git commit -m "feat: chatbot model picker now uses workspace allowed_models from OpenRouter BYOK"
```

---

### Task 10: Update embedder to use workspace key (optional upgrade)

Currently `embedder.py` uses `settings.OPENROUTER_API_KEY` from env. For true workspace isolation, the ingestion pipeline should use the workspace's key. This task wires it up.

**Files:**
- Modify: `backend/app/services/ingestion/embedder.py`
- Modify: `backend/app/workers/tasks/ingest_document.py`

**Step 1: Update `embed_chunks` to accept an optional key**

```python
async def embed_chunks(texts: list[str], api_key: str | None = None) -> list[list[float]]:
    client, model = _make_client(api_key=api_key)
    ...
```

Update `_make_client` to accept and prefer the passed key:

```python
def _make_client(api_key: str | None = None) -> tuple[AsyncOpenAI, str]:
    key = api_key or settings.OPENROUTER_API_KEY
    if key:
        return (
            AsyncOpenAI(api_key=key, base_url=OPENROUTER_BASE_URL),
            OPENROUTER_MODEL,
        )
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY), OPENAI_MODEL
```

**Step 2: Load workspace key in `ingest_document.py`**

In `_run()`, after the `await engine.dispose()` line, load the workspace key:

```python
async def _run(document_id: uuid.UUID) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            # Load workspace OpenRouter key for embeddings
            from sqlalchemy import select
            from app.models.organizational import Workspace
            from app.models.knowledge import Document
            from app.services.encryption import decrypt_api_key

            doc_result = await session.execute(select(Document).where(Document.id == document_id))
            doc = doc_result.scalar_one_or_none()
            workspace_embedding_key: str | None = None
            if doc:
                ws_result = await session.execute(
                    select(Workspace).where(Workspace.id == doc.workspace_id)
                )
                ws = ws_result.scalar_one_or_none()
                if ws and ws.openrouter_api_key:
                    try:
                        workspace_embedding_key = decrypt_api_key(ws.openrouter_api_key)
                    except Exception:
                        pass

            await run_ingestion(session, document_id, embedding_key=workspace_embedding_key)
            await session.commit()
            return {"status": "success", "document_id": str(document_id)}
        except Exception:
            await session.rollback()
            raise
```

Then update `run_ingestion` signature in the ingestion pipeline to accept and pass through `embedding_key`. This threading is somewhat deep — if `run_ingestion` calls `embed_chunks` indirectly, you'll need to trace the call path through `backend/app/services/ingestion/pipeline.py` and pass the key.

**Note:** If this threading is complex, the env-var fallback in `embedder.py` already works (the workspace key is also in `.env` as `OPENROUTER_API_KEY`). Skip this task if the tracing is too deep — the feature works without per-workspace embedding isolation.

**Step 3: Commit**

```bash
git add backend/app/services/ingestion/embedder.py backend/app/workers/tasks/ingest_document.py
git commit -m "feat: pass workspace OpenRouter key to embedder for per-workspace embedding isolation"
```

---

### Task 11: End-to-end smoke test

**Step 1: Open the app and navigate to Settings → AI Models**

```
http://localhost:3001/settings/llm
```

Expected: Page loads with "OpenRouter API Key" card (Key saved ✓ badge since env var was set previously) and "Allowed Models" card.

**Step 2: Save the key via the UI**

Paste the OpenRouter API key and click "Save key". Expected: success message + "Key saved ✓" badge.

**Step 3: Load models**

Click "Load from OpenRouter". Expected: list of models appears (100+).

**Step 4: Select a few models and save**

Check `openai/gpt-4o-mini`, `anthropic/claude-3-haiku`, click "Save model selection". Expected: success message.

**Step 5: Open a chatbot → Settings → AI Behavior**

Expected: Model dropdown shows only the 2 selected models. Saving sets `llm_provider = "openrouter"`.

**Step 6: Test a chat**

Go to the chatbot chat page and send a message. Expected: response streams back using the OpenRouter key.

**Step 7: Run full test suite**

```bash
make test
```

Expected: same pass rate as before (no regressions).

---

### Summary

| Task | What it does |
|------|-------------|
| 1 | Alembic migration — two new columns on workspaces |
| 2 | SQLAlchemy Workspace model update |
| 3 | OpenRouterLLMClient + factory registration |
| 4 | Thread workspace key through RAG pipeline |
| 5 | Three new backend endpoints |
| 6 | Frontend types + API functions |
| 7 | /settings/llm page |
| 8 | Sidebar nav item |
| 9 | Chatbot SettingsTab model picker |
| 10 | Embedder workspace key (optional) |
| 11 | E2E smoke test |
