# Spendily — AI Financial Coach
## Technical Specification Document

**Version:** 1.0
**Status:** Draft — ready for implementation
**Owner:** [FILL IN]

---

## 1. Overview

### 1.1 Purpose
Add an AI Financial Coach module to Spendily that analyzes a user's transaction history and produces personalized, plain-language financial insights, budget status updates, predictions, savings suggestions, and habit observations, surfaced on a dashboard.

### 1.2 Scope
In scope: analytics engine, insight generation and storage, weekly/monthly summaries, dashboard UI, supporting APIs.
Out of scope: bank/CSV import, multi-currency support, push notifications, any investment/credit product recommendations.

### 1.3 Design Principle
All numeric values (amounts, percentages, predictions) are computed deterministically in Python/SQL. The LLM is used only to phrase already-computed numbers into natural language — it never calculates or invents a figure.

---

## 2. Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.10+ |
| Web framework | Flask 3.1.3 |
| Auth | Werkzeug Security (`generate_password_hash`, `check_password_hash`) |
| Database | SQLite (`spendly.db`), raw `sqlite3`, parameterized SQL, connections cached in `flask.g` |
| Frontend | HTML5 + Jinja2 (extends `base.html`), vanilla CSS3, vanilla JavaScript |
| Testing | pytest 8.3.5, pytest-flask 1.3.0 |
| LLM provider | [FILL IN — e.g. Anthropic Claude API / OpenAI API] |
| Scheduling | APScheduler (no Celery/Redis) |

Explicitly excluded: React, TypeScript, Framer Motion, any ORM, CSS frameworks.

---

## 3. Data Model

Monetary values stored as **integer cents/paise**, not floating point.

### 3.1 `users`
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| email | TEXT UNIQUE | |
| password_hash | TEXT | |
| currency | TEXT | default configured currency |
| created_at | TEXT | ISO8601 |

### 3.2 `transactions`
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK → users.id | |
| amount | INTEGER | cents/paise |
| category_id | INTEGER FK → categories.id | |
| merchant | TEXT | |
| payment_method | TEXT | |
| occurred_at | TEXT | ISO8601 |
| is_recurring | INTEGER (0/1) | |
| is_transfer | INTEGER (0/1) | excluded from spend aggregations |
| note | TEXT | nullable |
| created_at | TEXT | |

### 3.3 `categories`
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK | |
| name | TEXT | |
| parent_category_id | INTEGER FK, nullable | |

### 3.4 `budgets`
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK | |
| category_id | INTEGER FK | |
| monthly_limit | INTEGER | cents/paise |
| period_start | TEXT | |
| active | INTEGER (0/1) | |

### 3.5 `insights`
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK | |
| type | TEXT | info / warning / success / critical |
| title | TEXT | |
| description | TEXT | |
| action | TEXT | |
| importance | INTEGER | 0–100, rule-computed |
| confidence | REAL | 0.0–1.0, based on data sufficiency |
| category | TEXT | nullable |
| period_start | TEXT | |
| period_end | TEXT | |
| created_at | TEXT | |
| read | INTEGER (0/1) | |
| dismissed | INTEGER (0/1) | |

### 3.6 Constraints & Indexing
- `PRAGMA foreign_keys = ON` on every connection.
- Index: `transactions(user_id, occurred_at)`, `transactions(user_id, category_id)`.
- Migrations as numbered SQL files: `migrations/0001_init.sql`, `migrations/0002_insights.sql`, etc. (no Alembic).

---

## 4. Backend Services

Located in `app/services/`. Each takes an injected `sqlite3.Connection` (not `flask.g` directly) so it is testable in isolation.

| Service | Responsibility |
|---|---|
| `FinancialAnalyticsEngine` | Spend aggregation by category, merchant, day-of-week, week, month, payment method; period-over-period comparison via SQLite `strftime()` |
| `BudgetAnalyzer` | % of budget used, pace vs. limit, days remaining in period |
| `PredictionEngine` | End-of-month spend projection: linear extrapolation from days-elapsed vs. days-in-month, adjusted for known recurring transactions |
| `HabitDetector` | Recurring behavior detection: peak spend weekday, time-of-day clustering, per-merchant frequency |
| `SavingsCalculator` | Annualized savings projections derived strictly from actual transaction counts/amounts |
| `FinancialInsightService` | Orchestrator: runs the above, assembles insight objects, calls the LLM formatter, persists to `insights` |
| `InsightLLMFormatter` | Only class permitted to call the LLM. Input: computed numbers + insight type. Output: title/description/action. Validates output numbers match input before save |

---

## 5. Insight Object Contract

```json
{
  "type": "warning",
  "importance": 95,
  "confidence": 0.94,
  "category": "Food",
  "title": "Food spending increased",
  "description": "You spent ₹4,200 more on Food than your average.",
  "action": "Reduce restaurant spending this week."
}
```

- `type`/`importance` are rule-derived (e.g., budget used >80% → warning, >100% → critical), never LLM-chosen.
- `confidence` reflects data sufficiency (e.g., reduced if category has <3 months of history).

---

## 6. Regeneration & Caching Strategy

- `transactions` writes set a `dirty`/`stale_since` marker per user.
- Insights regenerate lazily on next dashboard load if stale; otherwise served from the `insights` table (no LLM call per page view).
- Weekly/monthly summaries pre-generated via an APScheduler job.
- LLM calls rate-limited per user/day. On LLM failure or timeout, fall back to a template built directly from computed numbers — no insight is ever lost due to an outage.

---

## 7. API Specification

Blueprint: `ai_coach`. All routes require `session['user_id']`; all queries scoped with `WHERE user_id = ?`.

| Method | Route | Response | Notes |
|---|---|---|---|
| GET | `/ai/dashboard` | HTML | Jinja2 page |
| GET | `/api/ai/insights` | JSON | paginated, filterable by type/read/dismissed |
| GET | `/api/ai/weekly-summary` | JSON | |
| GET | `/api/ai/monthly-report` | JSON | |
| GET | `/api/ai/predictions` | JSON | |
| POST | `/api/ai/generate` | JSON | rate-limited, checks `dirty` flag |
| POST | `/api/ai/insights/<id>/dismiss` | JSON | |
| POST | `/api/ai/insights/<id>/read` | JSON | |

---

## 8. Frontend Specification

- Template: `templates/ai_coach/dashboard.html`, extends `base.html`.
- Cards: AI Coach feed, Weekly Summary, Predictions, Recommendations, Financial Score, Savings Opportunities.
- Each card: icon, severity color via CSS custom properties, load-in transition (CSS + `IntersectionObserver`), expandable detail (vanilla JS toggle), "Take Action" button (`fetch()`-wired).
- Loading skeletons: CSS-only pulse animation during `fetch()`.
- Empty state: shown below a defined minimum-data threshold (e.g., fewer than 10 transactions across 2 weeks).
- Responsive using existing CSS patterns; dark mode extends existing variables if already present in Spendily.

---

## 9. Financial Score Formula

| Component | Weight |
|---|---|
| Savings rate (income − spend) / income | 40% |
| Budget adherence (% categories within budget) | 30% |
| Spending consistency (month-to-month variance) | 20% |
| On-time recurring payment handling | 10% |

Score range 0–100, recalculated with each monthly report. Formula is explicit and auditable in code, not opaque.

---

## 10. Cold-Start Behavior

- Insight types define minimum data thresholds (e.g., no 3-month comparison before 3 months of data exist).
- Below threshold: "not enough data yet" state, never a fabricated baseline.
- New users see the defined empty state, not zeroed/broken cards.

---

## 11. Compliance & Safety Requirements

- Persistent disclaimer on all insight surfaces: *"These are automated observations based on your transaction history, not professional financial advice."*
- No insight may recommend a specific financial product, investment, or credit action.

---

## 12. Testing Requirements

- Fixture: temp/in-memory SQLite DB seeded with a fixed, known transaction dataset.
- Unit tests per service asserting exact numeric outputs against seeded data (deterministic, no LLM).
- `InsightLLMFormatter` mocked in all standard tests; one explicitly-marked integration test hits the real LLM API and asserts numeric integrity of its output.
- Route tests via `pytest-flask` test client: auth enforcement, user-scoping, response shape.

---

## 13. Non-Goals

- No CSV/bank import — transactions entered via existing Spendily entry flow.
- No multi-currency support.
- No push notifications — alerts surface as insight cards / Flask flash messages only.
- No Celery/Redis — background jobs via APScheduler only.

---

## 14. Deliverables Checklist

- [ ] SQL migration files for new tables
- [ ] `app/services/` modules + unit tests (LLM mocked)
- [ ] `ai_coach` Blueprint with routes
- [ ] Jinja2 templates + CSS + vanilla JS dashboard
- [ ] `InsightLLMFormatter` with number-integrity validation
- [ ] Seed script for demo/test transaction data

---

## 15. Open Items Requiring a Decision Before Build

- [ ] LLM provider and model
- [ ] Exact empty-state / minimum-data thresholds per insight type
- [ ] Whether dark mode already exists in Spendily or needs to be added