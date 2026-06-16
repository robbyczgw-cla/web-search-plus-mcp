"""Local web UI for Web Search Plus configuration and monitoring.

This module is only imported when the user runs ``web-search-plus-mcp ui``.
FastAPI/uvicorn are therefore optional dependencies declared under the ``[ui]``
extra in pyproject.toml.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

from . import __version__

# Optional dependencies: only required for the web UI subcommand.
try:
    from fastapi import FastAPI, Header, HTTPException, Request, Response
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field, field_validator
except Exception as exc:  # pragma: no cover - deferred import guard
    raise ImportError(
        "The web UI requires the optional [ui] dependencies. "
        "Install: pip install 'web-search-plus-mcp[ui]'"
    ) from exc


try:
    from .cache import cache_stats, CACHE_DIR
    from .config import _deepcopy_default_config, load_config
    from .provider_registry import (
        DEFAULT_AUTO_ALLOW,
        DEFAULT_PROVIDER_PRIORITY,
        PROVIDER_SPECS,
    )
    from .provider_health import PROVIDER_HEALTH_FILE
except ImportError:  # pragma: no cover
    from cache import cache_stats, CACHE_DIR  # type: ignore
    from config import (  # type: ignore
        _deepcopy_default_config,
        load_config,
    )
    from provider_registry import (  # type: ignore
        DEFAULT_AUTO_ALLOW,
        DEFAULT_PROVIDER_PRIORITY,
        PROVIDER_SPECS,
    )
    from provider_health import PROVIDER_HEALTH_FILE  # type: ignore

PROVIDER_STATS_PATH = CACHE_DIR / "provider_stats.json"


def _default_config_path() -> Path:
    return Path(
        os.environ.get("WEB_SEARCH_PLUS_CONFIG")
        or (Path(__file__).parent.parent / "config.json")
    ).expanduser()


def _config_path() -> Path:
    return _default_config_path()


def _load_ui_config() -> Dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return _deepcopy_default_config()
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {exc}")


def _write_ui_config(config: Dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_suffix(f".json.bak.{int(time.time())}")
        shutil.copy2(path, backup)
    with open(path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _normalize_provider_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [p.strip() for p in value.split(",") if p.strip()]
    result = []
    for item in value:
        item = str(item).strip().lower()
        if item and item not in result:
            result.append(item)
    return result


class RoutingUpdate(BaseModel):
    enabled: bool = True
    provider_priority: list[str] = Field(default_factory=list)
    disabled_providers: list[str] = Field(default_factory=list)
    fallback_provider: Optional[str] = "serper"
    confidence_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    @field_validator("provider_priority", "disabled_providers", mode="before")
    @classmethod
    def _normalize_lists(cls, value: Any) -> list[str]:
        return _normalize_provider_list(value)


class ConfigUpdate(BaseModel):
    auto_routing: RoutingUpdate = Field(default_factory=RoutingUpdate)


def _validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a config dict against the runtime schema."""
    try:
        validated = ConfigUpdate(**config)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid config: {exc}") from exc

    all_providers = set(PROVIDER_SPECS.keys())
    auto = validated.auto_routing
    for field_name in ("provider_priority", "disabled_providers"):
        value = getattr(auto, field_name)
        unknown = [p for p in value if p not in all_providers]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown providers in {field_name}: {', '.join(unknown)}",
            )
    if auto.fallback_provider and auto.fallback_provider not in all_providers:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown fallback provider: {auto.fallback_provider}",
        )

    merged = _deepcopy_default_config()
    merged["auto_routing"].update({
        "enabled": auto.enabled,
        "provider_priority": auto.provider_priority or list(DEFAULT_PROVIDER_PRIORITY),
        "disabled_providers": auto.disabled_providers,
        "fallback_provider": auto.fallback_provider,
        "confidence_threshold": auto.confidence_threshold,
        "auto_allow": dict(DEFAULT_AUTO_ALLOW),
    })
    return merged


def _load_health() -> Dict[str, Any]:
    path = PROVIDER_HEALTH_FILE
    if not path.exists():
        return {"status": "no health file", "path": str(path), "providers": {}}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as exc:
        return {"status": "error", "path": str(path), "error": str(exc)}


def _load_stats() -> Dict[str, Any]:
    try:
        return {"status": "ok", "cache": cache_stats()}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _build_doctor_report_sync(live: bool = False) -> Dict[str, Any]:
    try:
        from .search import _build_doctor_report
    except ImportError:  # pragma: no cover
        from search import _build_doctor_report  # type: ignore
    config = load_config()
    return _build_doctor_report(config, live=live)


def _origin_allowed(origin: str | None) -> bool:
    if origin is None:
        return True
    return origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")


def create_app() -> FastAPI:
    app = FastAPI(title="Web Search Plus UI", version=__version__)

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        index_path = static_dir / "index.html"
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        return _fallback_index()

    @app.get("/api/config")
    def get_config() -> Dict[str, Any]:
        config = _load_ui_config()
        return {
            "config_path": str(_config_path()),
            "config": config,
            "defaults": {
                "provider_priority": list(DEFAULT_PROVIDER_PRIORITY),
                "disabled_providers": [],
                "auto_allow": dict(DEFAULT_AUTO_ALLOW),
            },
        }

    @app.post("/api/config")
    def post_config(
        update: ConfigUpdate,
        request: Request,
        x_csrf_token: str | None = Header(None, alias="X-CSRF-Token"),
    ) -> Dict[str, Any]:
        origin = request.headers.get("origin")
        if not _origin_allowed(origin):
            raise HTTPException(status_code=403, detail="Cross-origin write not allowed")
        cookie_token = request.cookies.get("wsp_csrf")
        if not cookie_token or cookie_token != (x_csrf_token or ""):
            raise HTTPException(status_code=403, detail="Invalid CSRF token")

        incoming = update.model_dump(mode="json")
        merged = _validate_config(incoming)
        _write_ui_config(merged)
        return {"status": "saved", "config_path": str(_config_path())}

    @app.get("/api/health")
    def get_health() -> Dict[str, Any]:
        return _load_health()

    @app.get("/api/stats")
    def get_stats() -> Dict[str, Any]:
        return _load_stats()

    @app.get("/api/doctor")
    def get_doctor(live: bool = False) -> Dict[str, Any]:
        return _build_doctor_report_sync(live=live)

    @app.get("/api/csrf")
    def get_csrf(response: Response) -> Dict[str, str]:
        token = secrets.token_urlsafe(32)
        response.set_cookie(
            key="wsp_csrf",
            value=token,
            httponly=True,
            samesite="strict",
            max_age=3600,
            path="/",
        )
        return {"csrf_token": token}

    @app.get("/api/version")
    def get_version() -> Dict[str, str]:
        return {"version": __version__}

    @app.get("/api/providers")
    def get_providers() -> Dict[str, Any]:
        return {
            name: {
                "env": spec.env_var,
                "capabilities": [
                    cap for cap in ("search", "extract") if getattr(spec, f"supports_{cap}")
                ],
                "signup_url": spec.signup_url,
            }
            for name, spec in PROVIDER_SPECS.items()
        }

    return app


def _fallback_index() -> str:
    return (
        "<html><body><h1>Web Search Plus UI</h1>"
        "<p>Static assets not found. Run from an installed package.</p></body></html>"
    )


def run_ui(host: str = "127.0.0.1", port: int = 8080) -> int:
    import uvicorn

    app = create_app()
    print(f"Starting Web Search Plus UI at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0
