# PulseLite UX Redesign — Design Spec
_Date: 2026-03-10_

## Vision

Warm Studio aesthetic with custom SVG glyphs. Fun, functional, butter-smooth. Not generic SaaS — every screen should feel intentional. First-time users find a clear path forward; power users never need more than one click to get where they're going.

---

## Design Language

**Direction:** Warm Studio
**Palette:** Warm whites (#faf8f5, #fff), orange accent (#ff6b35), warm borders (#f0ebe3, #ede8e0)
**Typography:** System sans-serif, weight 900 for display numbers, 700 for headings, 500 for body
**Radius:** 8–16px (consistent, larger for cards/modals, smaller for inputs/pills)
**Icons:** Custom SVG glyphs — no emoji, no Lucide defaults for nav. Each section has a bespoke shape that metaphorically represents its purpose:
- Overview → pulse/heartbeat wave
- Chatbots → starburst/spark diamond
- Conversations → speech bubble with dots
- Intelligence → overlapping circles (Venn)
- Settings → quad grid

---

## 1. Navigation & Information Architecture

### Problem
Sidebar has 10 flat items — Settings sub-pages (Team, Webhooks, Security, Data Retention, AI Models) live at the top level alongside core navigation. Hard to scan. Dead search bar in topbar.

### Design
**Sidebar — 5 top-level items only:**
1. Overview (pulse wave glyph)
2. Chatbots (starburst glyph) — shows chatbot count badge
3. Conversations (speech bubble glyph) — shows unread/open badge
4. Intelligence (intersecting circles glyph)
5. Settings (quad grid glyph) — expands inline to sub-pages: General · Team · Billing · Integrations · AI Models · Security · Data Retention · Webhooks

**Sidebar bottom:** Workspace switcher (coloured dot + name + chevron) above logo. User avatar + name + plan pill at the very bottom.

**Topbar:**
- Page title (left)
- ⌘K command bar (centre-right) — replaces dead search, opens a command palette for global search, navigation, and quick actions
- Notification bell icon
- Global "+ New" button (context-aware: on chatbots page creates chatbot, on conversations page exports, etc.)

**Workspace switcher:** In sidebar top, not topbar. Frees topbar real estate.

---

## 2. Dashboard

### Problem
No "what to do next". Empty state shows zeros. Intelligence highlights feel disconnected. No quick actions.

### Design
**Greeting header:** "Good morning, [Name] 👋" + contextual subtitle ("3 bots active · 47 conversations while you were away").

**Quick action strip** (below greeting):
- `+ New chatbot` (primary)
- `View conversations` (secondary)
- `Add knowledge` (secondary)
- Strip is hidden once user has activity (replaced by chatbot filter chips)

**KPI row (3 cards):**
- Auto-resolution rate (hero, orange accent, trend arrow)
- Total conversations (trend)
- Escalated (trend, red if rising)

**Second row (2 columns):**
- Resolution trend — 12-week bar chart (single GROUP BY query, not a loop)
- Recent activity feed — last 5 notable events with timestamps and coloured dots

**Empty state (new workspace):** Single card with pulse wave illustration, "Your first chatbot is one URL away", two CTAs: "Create my first chatbot" + "See a demo".

---

## 3. Chatbot Detail — Tab Order & Labels

### Problem
Current order: Sources → Settings → Actions → Chat → Customize → Deploy. "Chat" (testing) buried at position 4. "Deploy" last but doesn't feel like a reward. "Settings" label is vague.

### Design
**New tab order:** Knowledge → Configure → Actions → Appearance → Test → Publish

Each tab has a custom SVG icon (12×12, stroke style):
- Knowledge → horizontal lines (document)
- Configure → starburst (spark/config)
- Actions → clock face (triggers/timing)
- Appearance → rounded rectangle with wave (widget preview)
- Test → speech bubble (try it)
- Publish → checkmark (done/live)

**"Test" tab** — renamed from "Chat". Has a prominent "Test this bot" button that opens a real chat widget inline. Feels like a reward/preview.

**"Publish" tab** — renamed from "Deploy". Shows embed code, domain allowlist, and a "Go live" toggle with satisfying on/off animation.

**Chatbot header bar:** Bot name + URL + conversation count + "Live" badge (green pulsing dot). "Duplicate" + "Test bot" buttons always visible.

---

## 4. Conversations

### Problem
Clicking a conversation navigates to a full new page. No bulk actions. Filters reset on nav. Status updates require going deep into detail view.

### Design
**Split-pane layout:** Conversation list (left, 280px) + slide-over detail (right, takes remaining space) + metadata sidebar (right, 180px, collapsible).

**List panel:**
- Filter chips row: status (Open / All / Resolved / Escalated) + bot selector + time range
- Each row: coloured avatar (gradient based on name hash) + name + message preview (truncated) + timestamp + status dot
- Active row: orange left border + warm background
- Filters persist in URL params (survive refresh/navigation)

**Slide-over panel:**
- Header: avatar + name + bot/domain info + inline status dropdown (no navigate-away)
- Message thread with bot/user bubble distinction
- Auto-tag chips shown below thread
- Confidence bar in metadata sidebar

**Metadata sidebar (collapsible):**
- Contact info, session data, confidence score, tags
- "Export CSV" button

**No full-page navigation.** The URL updates (e.g. `/conversations?id=abc`) for shareability but the UI stays in split-pane.

---

## 5. Knowledge Base / Sources Tab

### Problem
Failed docs have no inline retry. Reindexing has no progress feedback. "Chunks" count is meaningless to non-technical users.

### Design
**Table columns:** Source name (with type icon) · Type · Status · Last synced · Sync frequency · Actions

**Row actions** (visible on hover): Reindex · Delete
**Failed status pill** includes a "Retry" link inline: `● Failed — Retry`
**Processing pill** pulses and shows "Processing…" — clicking shows a mini progress indicator
**"Chunks" column removed** — replaced with "Last synced" timestamp
**Sync frequency** — dropdown per row, same as before
**Bulk actions:** Checkbox column, "Reindex selected" + "Delete selected" appear in a floating action bar when any row is checked

---

## 6. Widget Customization

### Problem
Long unsectioned form. No reset. Preview doesn't show mobile. Save at bottom of long scroll.

### Design
**Form structure — named sections:**
1. Identity (bot name, brand colour, welcome message, avatar)
2. Layout & Position (bottom-right / bottom-left toggle)
3. Quick replies (chip editor — add/remove suggested questions)
4. Behaviour (lead capture, GDPR consent, persist conversation — toggle row)
5. Advanced (custom CSS — collapsed by default, expandable)

**Sticky header** with "Reset to defaults" (secondary) + "Save changes" (primary) — always visible regardless of scroll position.

**Live preview panel (right column):**
- Desktop/Mobile toggle — mobile view shows the widget at phone dimensions
- Preview updates in real-time as form values change (no save needed to preview)
- Preview label: "Live preview · Desktop"

---

## 7. First-Time User Experience

### Problem
Onboarding wizard exists but unclear when triggered. Empty dashboard shows zeros. After wizard, no clear next step.

### Design
**Trigger:** On first login after registration, redirect to `/onboarding`. Skip button available at every step. Progress persisted in backend.

**Empty states (post-onboarding):**
- Dashboard → pulse wave illo + "Create my first chatbot" CTA
- Chatbots → starburst illo + "Your first bot is one URL away" + CTA
- Conversations → speech bubble illo + "Conversations will appear here once your bot is live" + "Deploy a bot" CTA
- Intelligence → "Add more conversations to unlock insights" with a progress bar toward threshold

**Wizard completion:** After step 4 (Deploy), show a celebration moment — confetti burst, "You're live!" heading, copy-embed-code as the primary CTA, then "Go to dashboard" secondary.

---

## 8. Quick Wins — Micro-interactions & Polish

- **Copy buttons:** Show "Copied!" for 1.5s then revert (no full-page feedback, no toast)
- **Toasts:** Appear bottom-right, auto-dismiss after 3s. Used for: save success, reindex started, invite sent. Not for every action.
- **Page titles:** `<title>` updates per route — "Conversations — PulseLite", "Support Bot — PulseLite"
- **Loading states:** Skeleton screens (not full-page spinners) for table rows and KPI cards
- **Row hover hints:** Action buttons fade in on row hover (opacity 0 → 1, transition 150ms)
- **⌘K command palette:** Global search across chatbots, conversations, knowledge bases. Keyboard navigation (↑↓ arrows, Enter to select). Quick nav shortcuts.
- **Status dropdown** in conversation detail: inline `<select>` styled as a pill, updates optimistically
- **Breadcrumbs:** Show on all sub-pages (Chatbots › Support Bot › Knowledge)
- **Keyboard shortcuts:** `N` = new chatbot, `C` = conversations, `/` = open ⌘K, `Esc` = close panel/modal

---

## Implementation Notes

- All nav icons: inline SVG, 16×16 viewBox, 1.6px stroke, `stroke-linecap="round"` `stroke-linejoin="round"`
- Active nav item: `bg-orange-50 text-orange-500 font-semibold`
- Warm border: `border-[#f0ebe3]`
- Warm background: `bg-[#faf8f5]`
- Accent: `#ff6b35` (not Tailwind's indigo — replace globally)
- Conversations split-pane: URL param `?id=` for shareability, no router.push to detail page
- ⌘K: `cmdk` library (already common in Next.js apps) or custom
- Skeleton screens: `animate-pulse bg-[#f5f0ea] rounded`
- Toasts: `react-hot-toast` or custom, bottom-right, max 3 visible
