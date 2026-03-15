# Document Content Viewer — Design Spec

## Goal

Let users view the content of each knowledge source document — both the raw extracted text and the individual chunks used for RAG retrieval.

## Backend

### New endpoint

`GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/content`

**Auth**: `Depends(get_workspace)` + `Depends(get_current_user)` (same as all authenticated routes).

**Response shape**:

```json
{
  "id": "uuid",
  "title": "Pricing | Acme",
  "source_type": "url",
  "source_url": "https://acme.com/pricing",
  "status": "indexed",
  "error_message": null,
  "char_count": 4200,
  "chunk_count": 8,
  "raw_content": "Full extracted text...",
  "chunks": [
    {
      "id": "uuid",
      "chunk_index": 0,
      "content": "Chunk text...",
      "heading_path": "Pricing > Enterprise",
      "token_count": 312
    }
  ]
}
```

**Query**: Reuse `document_service.get_document(db, workspace_id, document_id)` for the document lookup (it already enforces workspace isolation). Then load chunks via `select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index)`. No embeddings or search vectors in response.

**Payload size**: Typical crawled pages produce <50 chunks and <100KB total. All chunks are returned without pagination — the frontend handles large content with scrollable containers and truncation. This matches the fact that ingestion already caps page size.

**Schema**: New `DocumentContentResponse` and `ChunkResponse` Pydantic models in `backend/app/schemas/documents.py`.

**404**: If document not found or wrong workspace.

**Note on URL pattern**: The existing list endpoint requires `knowledge_base_id` as a query parameter (`GET /documents?knowledge_base_id=...`) because it scopes by KB. The detail endpoint does not need it — `(document_id, workspace_id)` is sufficient for a unique lookup.

### No changes to existing endpoints

The existing `GET /documents` list endpoint is unchanged — it returns metadata only, which is what the SourcesTab table needs.

## Frontend

### API function

New function in `api-functions.ts`:

```typescript
export function getDocumentContent(workspaceId: string, documentId: string) {
  return api.get<DocumentContentResponse>(
    `/api/v1/workspaces/${workspaceId}/documents/${documentId}/content`
  );
}
```

### Types

New types in `types.ts`:

```typescript
export interface ChunkItem {
  id: string;
  chunk_index: number;
  content: string;
  heading_path: string | null;
  token_count: number | null;
}

export interface DocumentContentResponse {
  id: string;
  title: string | null;
  source_type: string;
  source_url: string | null;
  status: string;
  error_message: string | null;
  char_count: number;
  chunk_count: number;
  raw_content: string | null;
  chunks: ChunkItem[];
}
```

### UI: Inline detail panel in SourcesTab

**Location**: `frontend/src/app/(dashboard)/chatbots/[id]/sources/SourcesTab.tsx`

**Interaction**:
- Click a document row → toggles an inline detail panel below that row
- Only one document expanded at a time (clicking another collapses the current one)
- Clicking the same row again collapses it
- Content fetched on expand (lazy load), cached in local state
- Cache is invalidated when `handleReindex` is called for a document (status changes, content may differ after re-ingestion)

**Detail panel layout**:

1. **Header row**: Title, source URL (as clickable external link), status badge, `{char_count} chars · {chunk_count} chunks`

2. **Two tabs**: "Content" and "Chunks"

3. **Content tab**:
   - Full `raw_content` in a scrollable `<pre>` block (max-height ~400px)
   - "Copy" button to copy raw content to clipboard
   - Empty state if `raw_content` is null: "Content not available for this source type"

4. **Chunks tab**:
   - Ordered list of chunks
   - Each chunk shows: index badge, heading path (muted, if present), content (truncated to ~200 chars with "Show more" toggle), token count
   - Empty state if no chunks: "No chunks — document may still be processing"

5. **Failed documents**: Show error message prominently, no content/chunks tabs

### Error and empty states

| Condition | Behavior |
|---|---|
| `raw_content` is null | Show "Content not available for this source type" in Content tab |
| `chunks` is empty | Show "No chunks — document may still be processing" in Chunks tab |
| `status === "failed"` | Show error message from `error_message` field, hide tabs |
| Loading | Spinner inside the expanded panel |
| API call fails | Show "Failed to load content" error in the expanded panel with a retry button |

## Testing

### Backend
- Test endpoint returns document metadata + chunks ordered by chunk_index
- Test 404 for wrong workspace
- Test empty chunks list for pending document
- Test null raw_content handling
- Test error_message included for failed documents

### Frontend
- Test expand/collapse toggle
- Test content and chunks tab switching
- Test copy-to-clipboard
- Test empty states render correctly
- Test API error state shows retry option
