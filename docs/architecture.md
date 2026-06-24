# Architecture — AI Analytics Assistant

## Goal

Turn a natural-language question into a **safe, read-only SQL query**, execute it against a
PostgreSQL crypto warehouse, and return a chart-ready result with an explanation — while
letting the user **swap the underlying LLM from the UI** without touching code. Data is fed by
a **real-time streaming pipeline** (Kafka) and archived in a **data lake** (MinIO).

---

## Data ingestion (streaming + data lake)

```
CoinGecko /coins/markets
        │  (fetch top-50, normalize → src/crawler/coingecko.py)
        ▼
src/streaming/producer.py ──▶ Kafka topic 'crypto.ticks'  (keyed by coin_id)
                                        │
                                        ▼
                            src/streaming/consumer.py
                            ├─▶ MinIO (src/streaming/lake.py)   raw JSON, append-only
                            │     key: ticks/dt=YYYY-MM-DD/<coin>/<ts>.json
                            └─▶ PostgreSQL (src/crawler/store.py)
                                  ├─ coins        UPSERT (one row/coin)
                                  └─ price_ticks  APPEND (time series)
```

**Two sinks, two purposes:**
- **MinIO (data lake)** — keeps every tick exactly as received. It is the durable source of
  truth; the warehouse can always be re-derived from it. Stored long-term, cheap, immutable.
- **PostgreSQL (warehouse)** — query-optimized tables the AI Assistant runs SQL against.

Producer + consumer run **24/7 as Docker containers** (`restart: unless-stopped`), so ingestion
is automatic — no terminal needed. Both data stores persist in Docker volumes across restarts.

**Why Kafka here?** It decouples "fetch" from "store" and lets us add more sinks/consumers later
without touching the producer. For 50 coins/minute it's modest load — the value is the
architecture (streaming + lake + warehouse), which mirrors a real production data platform.

## Query pipeline

```
NL question
   │
   ▼
[schema context]  introspect DB → table DDL + sample rows + time-series hints  (src/db/introspect.py)
   │
   ▼
[prompt builder]  system prompt + schema + question        (src/llm/prompt.py)
   │
   ▼
[LLM provider]    Gemini / OpenAI / DeepSeek / Groq / Ollama  (src/llm/*)
   │  generated SQL
   ▼
[safety guard]    single SELECT only, no DDL/DML, no multi-stmt  (src/safety/guard.py)
   │
   ▼
[executor]        run as read-only role, row cap, timeout    (src/safety/executor.py)
   │  DataFrame
   ▼
[result render]   pick chart (bar/line/table) + explanation   (src/app/)
```

---

## Provider abstraction — how "switch LLM from the UI" works

This is the core design decision. We never hard-code a single vendor.

### 1. One interface

```python
class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str) -> str: ...
```

Every vendor implements `complete()`. The pipeline only ever calls `provider.complete(...)`.

### 2. One registry (the single source of truth the UI reads)

`PROVIDER_REGISTRY` in `src/config.py` declares each provider's:
- display name, kind (`openai_compatible` | `ollama`),
- `base_url` (Gemini/DeepSeek/Groq differ only here),
- env var holding the API key, and the list of selectable models.

The Streamlit sidebar renders its **Provider** and **Model** dropdowns directly from this
registry — so the UI is always in sync with what's supported.

### 3. One factory

```python
provider = get_provider(name, model, api_key)   # src/llm/factory.py
```

Because **Gemini, OpenAI, DeepSeek, and Groq all expose an OpenAI-compatible endpoint**, they
share a single `OpenAICompatibleProvider` class — only `base_url` + `model` change. Ollama gets
its own tiny `OllamaProvider` (plain HTTP). 

> **Adding a new vendor:**
> - OpenAI-compatible (most are) → add one entry to `PROVIDER_REGISTRY`. Zero new code.
> - Truly different API → add a ~30-line class + one registry entry.
> The app, prompt, safety, and executor are untouched.
>
> **Claude is the worked example of the second case:** the Anthropic API is *not*
> OpenAI-compatible (system prompt is a top-level arg, `messages.create` returns content
> blocks), so it gets its own `AnthropicProvider` (`kind="anthropic"`) using the official
> `anthropic` SDK — proving the abstraction handles non-compatible vendors with one small class.

### Why OpenAI-compatible for everything

Google exposes Gemini at `https://generativelanguage.googleapis.com/v1beta/openai/`,
DeepSeek at `https://api.deepseek.com`, Groq at `https://api.groq.com/openai/v1`. All accept
the same `chat.completions` shape as OpenAI, so the `openai` Python SDK talks to all of them by
just changing `base_url` + `api_key`. This collapses 4 vendors into one code path.

---

## Safety model

The LLM is **never trusted**. Two independent layers:

1. **Static guard** (`src/safety/guard.py`) — parse with `sqlparse`; reject if:
   - more than one statement (blocks `; DROP TABLE ...`),
   - the statement is not a `SELECT`/`WITH … SELECT`,
   - it contains DDL/DML keywords (`INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/GRANT/COPY`).
2. **Least-privilege execution** (`src/safety/executor.py`) — runs as a DB role with `SELECT`-only
   grants, a `statement_timeout`, and an enforced `LIMIT`. Even if the guard were bypassed, the
   role cannot mutate data.

---

## Database — crypto market (crawled from CoinGecko)

Live data makes the demo "realtime": the more you crawl, the more history accumulates.

| Table | Grain | Key columns |
|---|---|---|
| `coins` | one row / coin (upsert) | `coin_id`, `symbol`, `name`, `market_cap_rank`, `ath` |
| `price_ticks` | one row / coin / crawl (append) | `coin_id`, `price_usd`, `price_change_pct_24h`, `total_volume`, `captured_at` |

- **Latest snapshot** = rows where `captured_at = (SELECT MAX(captured_at) FROM price_ticks)`.
- **Price history** of a coin = filter `coin_id`, `ORDER BY captured_at`.
These conventions are injected into the LLM prompt so generated SQL handles "now" vs "over time".

---

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-09 | Multi-provider via OpenAI-compatible + registry | User wants to swap LLM from the UI; OpenAI-compat collapses 4 vendors into 1 class |
| 2026-06-09 | Read-only role + static guard (two layers) | LLM output is untrusted; defense in depth |
| 2026-06-09 | **Pivot: e-commerce (Faker) → crypto crawl (CoinGecko)** | User wants live crawled data persisted to a DB for ongoing analysis |
| 2026-06-09 | CoinGecko public API (no key) over HTML scraping | Stable, legal, doesn't break when a site changes its HTML |
| 2026-06-09 | `price_ticks` append-only time series in a Docker volume | Data must survive restarts and accumulate history for trend questions |
| 2026-06-09 | Default LLM = Groq llama-3.3-70b | Free + fast; Gemini free-tier key returned 429 limit:0 for the test project |
| 2026-06-09 | **Add Kafka + MinIO streaming pipeline** | User wanted real-time ingest + a long-term store for analysis → streaming + data lake |
| 2026-06-09 | Kafka in KRaft mode (no Zookeeper) | Simpler single-node setup, fewer containers |
| 2026-06-09 | MinIO raw lake + Postgres warehouse (two sinks) | Lake = durable source of truth (re-derivable); warehouse = query layer for the assistant |
| 2026-06-09 | `kafka-python-ng` instead of `kafka-python` | Original lib breaks on Python 3.12 (`kafka.vendor.six.moves`) |
| 2026-06-09 | Producer/consumer as always-on containers | "Auto-crawl long-term" without keeping a terminal open |
| 2026-06-09 | AI Assistant remains the final product | Streaming/lake are ingest only; the NL2SQL Streamlit app is the endpoint |
