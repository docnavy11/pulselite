# Email Reports — Design Spec

## Goal

Let workspace admins configure periodic email reports with relevant stats, choosing frequency (daily/weekly/monthly), which sections to include, and recipients. Support both Resend (SaaS) and custom SMTP (self-hosted) as email providers.

## Email Provider Config

The existing email integration (`IntegrationConfig` with `integration_type="email"`) gains a `provider` field in its JSONB config:

**Resend (current):**
```json
{
  "provider": "resend",
  "api_key": "re_...",
  "from_email": "Pulse <notifications@pulse.app>",
  "to_email": "admin@example.com",
  "app_url": "https://app.pulse.dev"
}
```

**SMTP (new):**
```json
{
  "provider": "smtp",
  "host": "smtp.example.com",
  "port": 587,
  "username": "user@example.com",
  "password": "...",
  "tls": true,
  "from_email": "Pulse <notifications@example.com>",
  "to_email": "admin@example.com",
  "app_url": "https://app.pulse.dev"
}
```

### Email Service Changes

`backend/app/services/integrations/email.py` gets a routing layer:
- If `provider == "smtp"`: use Python `smtplib` + `email.mime`
- If `provider == "resend"` (or missing, for backwards compat): use Resend SDK as today
- All existing email functions (`send_escalation_email`, `send_invite_email`, `send_weekly_digest_email`) route through this

### Frontend: Integration Settings

In `frontend/src/app/(dashboard)/settings/integrations/page.tsx`, the email section adds:
- **Provider** dropdown: Resend / SMTP
- Resend selected: shows API Key, From Email (current fields)
- SMTP selected: shows Host, Port, Username, Password, TLS toggle, From Email
- Both show: To Email, App URL
- "Test" button works for both providers

## Report Configuration

Stored in `Workspace.intelligence_config` JSONB alongside existing keys:

```json
{
  "auto_analyze": true,
  "sentiment_trends": true,
  "gap_clustering": true,
  "report_frequency": "weekly",
  "report_recipients": ["admin@example.com"],
  "report_sections": {
    "conversations": true,
    "confidence": true,
    "sentiment": true,
    "gaps": true,
    "top_topics": true,
    "qa_performance": true
  }
}
```

### Frequency Options

| Value | Schedule | Period covered |
|-------|----------|---------------|
| `"off"` | Disabled | — |
| `"daily"` | Every day at 08:00 UTC | Last 24 hours |
| `"weekly"` | Monday at 08:00 UTC | Last 7 days |
| `"monthly"` | 1st of month at 08:00 UTC | Last 30 days |

### Report Sections (all default to `true`)

| Key | Contents |
|-----|----------|
| `conversations` | Total, resolved, escalated, resolution rate |
| `confidence` | Average confidence score, trend vs previous period |
| `sentiment` | Average sentiment score, trend vs previous period |
| `gaps` | Open gap clusters, new this period |
| `top_topics` | Top 5 most asked-about topics |
| `qa_performance` | Q&A pair count, average confidence (if Q&A pairs exist) |

### Recipients

Comma-separated emails. Defaults to workspace admin emails if not configured.

### API Changes

Extend `PUT /workspaces/{workspace_id}/intelligence/config`:

```python
class IntelligenceConfigUpdate(BaseModel):
    auto_analyze: bool | None = None
    sentiment_trends: bool | None = None
    gap_clustering: bool | None = None
    report_frequency: str | None = None  # "off" | "daily" | "weekly" | "monthly"
    report_recipients: list[str] | None = None
    report_sections: dict[str, bool] | None = None
```

Extend `GET /workspaces/{workspace_id}/intelligence/config` to return report fields.

### Frontend: Intelligence Settings

In `frontend/src/app/(dashboard)/settings/intelligence/page.tsx`, add a "Reports" card:
- Frequency dropdown (Off / Daily / Weekly / Monthly)
- Recipients text input (comma-separated)
- Section toggles (checkboxes for each of the 6 sections)

## Celery Task

### Migration from `weekly_digest`

The existing `weekly_digest.py` task is replaced by `send_report.py`:

**Schedule:** Runs every hour via Celery Beat (lightweight — checks timestamps, skips quickly if nothing to send).

**Logic per workspace:**
1. Read `intelligence_config.report_frequency` — skip if `"off"` or missing
2. Read `workspace.last_report_sent_at` — compute whether it's time to send
3. Compute stats for the period (reuses existing dashboard query logic)
4. Build email body with only enabled sections
5. Send via configured email provider (Resend or SMTP)
6. Update `workspace.last_report_sent_at`

### Database Migration

Add `last_report_sent_at` column to `workspaces` table:

```python
last_report_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

## File Changes Summary

### Backend
| File | Change |
|------|--------|
| `backend/app/services/integrations/email.py` | Add SMTP send path, provider routing |
| `backend/app/workers/tasks/send_report.py` | New task replacing weekly_digest |
| `backend/app/workers/tasks/weekly_digest.py` | Remove (replaced by send_report) |
| `backend/app/workers/celery_app.py` | Update beat schedule + includes |
| `backend/app/api/v1/intelligence.py` | Extend config schema with report fields |
| `backend/app/models/organizational.py` | Add `last_report_sent_at` to Workspace |
| `backend/alembic/versions/...` | Migration for new column |

### Frontend
| File | Change |
|------|--------|
| `frontend/src/app/(dashboard)/settings/integrations/page.tsx` | Provider toggle (Resend/SMTP) |
| `frontend/src/app/(dashboard)/settings/intelligence/page.tsx` | Reports config card |

## Non-Goals

- Per-user report preferences (workspace-level only for now)
- PDF/attachment reports (HTML email body only)
- Custom report templates
- Scheduling at specific times per workspace (global 08:00 UTC)
