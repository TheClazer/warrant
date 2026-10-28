"""Runtime settings, read once from the environment. Secrets are never logged or returned by the API."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

TOKEN_FACTORY_URL = "https://api.tokenfactory.nebius.com/v1"
SUPER = "nvidia/nemotron-3-super-120b-a12b"
NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("WARRANT_DATA_DIR", "data")))
    nebius_api_key: str = field(default_factory=lambda: os.environ.get("NEBIUS_API_KEY", ""), repr=False)
    token_factory_url: str = field(
        default_factory=lambda: os.environ.get("WARRANT_TOKEN_FACTORY_URL", TOKEN_FACTORY_URL)
    )
    planner_model: str = field(default_factory=lambda: os.environ.get("WARRANT_PLANNER_MODEL", SUPER))
    agent_model: str = field(default_factory=lambda: os.environ.get("WARRANT_AGENT_MODEL", SUPER))
    portal_url: str = field(default_factory=lambda: os.environ.get("WARRANT_PORTAL_URL", "http://127.0.0.1:8201"))
    enforcer: str = field(default_factory=lambda: os.environ.get("WARRANT_ENFORCER", "proxy"))
    admin_token: str = field(default_factory=lambda: os.environ.get("WARRANT_ADMIN_TOKEN", ""), repr=False)
    tavily_api_key: str = field(default_factory=lambda: os.environ.get("TAVILY_API_KEY", ""), repr=False)
    guest_daily_usd_cap: float = field(default_factory=lambda: _float("WARRANT_GUEST_DAILY_USD_CAP", 3.0))
    # Hard daily limits that work even when no prices are configured. They protect a public demo's credits.
    daily_run_cap: int = field(default_factory=lambda: _int("WARRANT_DAILY_RUN_CAP", 30))
    daily_draft_cap: int = field(default_factory=lambda: _int("WARRANT_DAILY_DRAFT_CAP", 30))
    run_max_model_calls: int = field(default_factory=lambda: _int("WARRANT_RUN_MAX_MODEL_CALLS", 40))
    eval_usd_cap: float = field(default_factory=lambda: _float("WARRANT_EVAL_USD_CAP", 10.0))
    # USD per million tokens, {"model-id": [input, output]}. Costs are reported only for priced models,
    # so nothing is estimated from unconfirmed prices.
    prices: dict[str, list[float]] = field(
        default_factory=lambda: json.loads(os.environ.get("WARRANT_PRICES_JSON", "{}"))
    )

    @property
    def live_model(self) -> bool:
        return bool(self.nebius_api_key.strip())

    def public(self) -> dict:
        return {
            "planner_model": self.planner_model,
            "agent_model": self.agent_model,
            "provider": "Nebius Token Factory",
            "enforcer": self.enforcer,
            "live_model": self.live_model,
            "portal_url": self.portal_url,
            "tavily": bool(self.tavily_api_key),
            "guest_daily_usd_cap": self.guest_daily_usd_cap,
            "daily_run_cap": self.daily_run_cap,
            "daily_draft_cap": self.daily_draft_cap,
            "run_max_model_calls": self.run_max_model_calls,
            "priced_models": sorted(self.prices),
        }


def get_settings() -> Settings:
    return Settings()
