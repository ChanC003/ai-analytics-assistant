"""Central config: env loading + the LLM provider registry the UI reads from."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────── Database ───────────────────────────────

@dataclass(frozen=True)
class DBConfig:
    host: str
    port: int
    name: str
    # Owner role — used by the seeder to create/populate tables.
    user: str
    password: str
    # Read-only role — used by the executor to run LLM-generated SQL.
    readonly_user: str
    readonly_password: str


def db_config() -> DBConfig:
    return DBConfig(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5433")),
        name=os.getenv("DB_NAME", "ecommerce"),
        user=os.getenv("DB_USER", "assistant"),
        password=os.getenv("DB_PASSWORD", "assistant_pwd"),
        readonly_user=os.getenv("DB_READONLY_USER", "readonly"),
        readonly_password=os.getenv("DB_READONLY_PASSWORD", "readonly_pwd"),
    )


# ─────────────────────────── Streaming + data lake ───────────────────────────

@dataclass(frozen=True)
class StreamConfig:
    kafka_bootstrap: str
    topic: str
    consumer_group: str
    # MinIO (S3-compatible) — the raw data lake.
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool


def stream_config() -> StreamConfig:
    return StreamConfig(
        kafka_bootstrap=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
        topic=os.getenv("KAFKA_TOPIC", "crypto.ticks"),
        consumer_group=os.getenv("KAFKA_CONSUMER_GROUP", "crypto-sink"),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        minio_bucket=os.getenv("MINIO_BUCKET", "crypto-raw"),
        minio_secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )


# ─────────────────────────── LLM provider registry ───────────────────────────
#
# The single source of truth for "which LLMs can I pick in the UI".
# The Streamlit sidebar renders Provider + Model dropdowns straight from this.
#
# kind:
#   "openai_compatible" — reached via the openai SDK by swapping base_url + key.
#                         Gemini, OpenAI, DeepSeek and Groq all fit here.
#   "anthropic"         — Claude, via the official anthropic SDK (not OpenAI-compatible).
#   "ollama"            — local HTTP server, no API key.
#
# To add a provider: append one ProviderSpec. No app/pipeline changes needed
# (unless it's a genuinely non-OpenAI-compatible API → add a class in src/llm/).

@dataclass(frozen=True)
class ProviderSpec:
    key: str                       # internal id, e.g. "gemini"
    label: str                     # display name in the UI
    kind: str                      # "openai_compatible" | "ollama"
    models: list[str]              # selectable models
    env_key: str = ""              # env var holding the API key (if any)
    base_url: str = ""             # OpenAI-compatible endpoint (if any)
    base_url_env: str = ""         # env var overriding base_url (Ollama)
    notes: str = ""


PROVIDER_REGISTRY: dict[str, ProviderSpec] = {
    "claude": ProviderSpec(
        key="claude",
        label="Claude (Anthropic)",
        kind="anthropic",
        env_key="ANTHROPIC_API_KEY",
        # Haiku first = cheapest/fastest, good default for NL2SQL.
        models=["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"],
        notes="Best SQL quality; needs an Anthropic API key.",
    ),
    "gemini": ProviderSpec(
        key="gemini",
        label="Gemini (Google AI Studio)",
        kind="openai_compatible",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        env_key="GEMINI_API_KEY",
        models=["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"],
        notes="Free tier — recommended for the demo.",
    ),
    "openai": ProviderSpec(
        key="openai",
        label="OpenAI",
        kind="openai_compatible",
        base_url="https://api.openai.com/v1",
        env_key="OPENAI_API_KEY",
        models=["gpt-4o-mini", "gpt-4o"],
    ),
    "deepseek": ProviderSpec(
        key="deepseek",
        label="DeepSeek",
        kind="openai_compatible",
        base_url="https://api.deepseek.com",
        env_key="DEEPSEEK_API_KEY",
        models=["deepseek-chat"],
    ),
    "groq": ProviderSpec(
        key="groq",
        label="Groq",
        kind="openai_compatible",
        base_url="https://api.groq.com/openai/v1",
        env_key="GROQ_API_KEY",
        models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        notes="Free + very fast.",
    ),
    "ollama": ProviderSpec(
        key="ollama",
        label="Ollama (local)",
        kind="ollama",
        base_url_env="OLLAMA_BASE_URL",
        models=["llama3", "qwen2.5", "mistral"],
        notes="Runs offline; no API key needed.",
    ),
}


def default_provider_key() -> str:
    key = os.getenv("DEFAULT_LLM_PROVIDER", "gemini").lower()
    return key if key in PROVIDER_REGISTRY else "gemini"


def default_model(provider_key: str) -> str:
    spec = PROVIDER_REGISTRY[provider_key]
    # Prefer an env-pinned model (e.g. GEMINI_MODEL) if it's in the allow-list.
    env_model = os.getenv(f"{provider_key.upper()}_MODEL", "")
    if env_model and env_model in spec.models:
        return env_model
    return spec.models[0]


def env_api_key(provider_key: str) -> str:
    spec = PROVIDER_REGISTRY[provider_key]
    return os.getenv(spec.env_key, "") if spec.env_key else ""


def resolve_base_url(spec: ProviderSpec) -> str:
    if spec.base_url_env:
        return os.getenv(spec.base_url_env, "http://localhost:11434")
    return spec.base_url


# ─────────────────────────── Executor limits ───────────────────────────

MAX_RESULT_ROWS = 1000          # hard cap injected into / enforced on queries
STATEMENT_TIMEOUT_MS = 8000     # per-query timeout on the read-only session
