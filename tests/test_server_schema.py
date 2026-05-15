import asyncio
import json
from types import SimpleNamespace

import web_search_plus_mcp.server as server
import web_search_plus_mcp.search as search


def run(coro):
    return asyncio.run(coro)


def tool_by_name(name):
    tools = run(server.list_tools())
    return next(tool for tool in tools if tool.name == name)


def test_web_search_schema_exposes_v17_providers_and_controls():
    tool = tool_by_name("web_search")
    props = tool.inputSchema["properties"]

    assert props["provider"]["enum"] == [
        "auto",
        "serper",
        "brave",
        "tavily",
        "exa",
        "linkup",
        "firecrawl",
        "perplexity",
        "kilo-perplexity",
        "you",
        "searxng",
        "serpbase",
        "querit",
    ]
    assert props["depth"]["enum"] == ["normal", "deep", "deep-reasoning"]
    assert props["mode"]["enum"] == ["normal", "research"]
    assert props["quality_report"]["type"] == "boolean"
    assert props["research_time_budget"]["maximum"] == 75


def test_web_extract_tool_is_exposed_with_linkup_first_capable_schema():
    tool = tool_by_name("web_extract")
    props = tool.inputSchema["properties"]

    assert tool.inputSchema["required"] == ["urls"]
    assert props["provider"]["enum"] == ["auto", "firecrawl", "linkup", "tavily", "exa", "you"]
    assert props["render_js"]["type"] == "boolean"
    assert props["format"]["enum"] == ["markdown", "html"]


def test_web_answer_is_hidden_until_beta_env_enabled(monkeypatch):
    monkeypatch.delenv("WSP_ENABLE_WEB_ANSWER", raising=False)
    names = [tool.name for tool in run(server.list_tools())]
    assert names == ["web_search", "web_extract"]


def test_web_answer_schema_when_enabled(monkeypatch):
    monkeypatch.setenv("WSP_ENABLE_WEB_ANSWER", "1")
    tool = tool_by_name("web_answer")
    props = tool.inputSchema["properties"]

    assert "optional beta" in tool.description.lower()
    assert props["freshness"]["default"] == "none"
    assert props["freshness"]["enum"] == ["none", "auto", "day", "week", "month", "year"]
    assert props["output"]["enum"] == ["answer", "brief", "sources", "json"]


def test_web_search_call_maps_mcp_args_to_cli(monkeypatch):
    seen = {}

    def fake_run(cmd, capture_output, text, env, timeout):
        seen["cmd"] = cmd
        seen["timeout"] = timeout
        return SimpleNamespace(returncode=0, stdout=json.dumps({"ok": True}), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)

    result = run(server.call_tool("web_search", {
        "query": "latest Hermes release",
        "provider": "linkup",
        "count": 7,
        "depth": "deep",
        "time_range": "week",
        "include_domains": ["github.com"],
        "exclude_domains": ["reddit.com"],
        "mode": "research",
        "quality_report": True,
        "research_time_budget": 12,
    }))

    cmd = seen["cmd"]
    assert "--query" in cmd and "latest Hermes release" in cmd
    assert "--provider" in cmd and "linkup" in cmd
    assert "--max-results" in cmd and "7" in cmd
    assert "--exa-depth" in cmd and "deep" in cmd
    assert "--time-range" in cmd and "week" in cmd
    assert "--include-domains" in cmd and "github.com" in cmd
    assert "--exclude-domains" in cmd and "reddit.com" in cmd
    assert "--mode" in cmd and "research" in cmd
    assert "--quality-report" in cmd
    assert "--research-time-budget" in cmd and "12" in cmd
    assert result[0].text == '{"ok": true}'


def test_web_extract_call_maps_mcp_args_to_cli(monkeypatch):
    seen = {}

    def fake_run(cmd, capture_output, text, env, timeout):
        seen["cmd"] = cmd
        seen["timeout"] = timeout
        return SimpleNamespace(returncode=0, stdout=json.dumps({"results": []}), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)

    result = run(server.call_tool("web_extract", {
        "urls": ["https://example.com"],
        "provider": "linkup",
        "format": "markdown",
        "include_images": True,
        "include_raw_html": True,
        "render_js": True,
    }))

    cmd = seen["cmd"]
    assert "--extract-urls" in cmd and "https://example.com" in cmd
    assert "--provider" in cmd and "linkup" in cmd
    assert "--format" in cmd and "markdown" in cmd
    assert "--extract-images" in cmd
    assert "--include-raw-html" in cmd
    assert "--render-js" in cmd
    assert seen["timeout"] == 90
    assert result[0].text == '{"results": []}'


def test_web_answer_call_searches_then_extracts_and_formats_json(monkeypatch):
    calls = []
    monkeypatch.setenv("WSP_ENABLE_WEB_ANSWER", "1")
    monkeypatch.setenv("TAVILY_API_KEY", "tv-test")
    monkeypatch.setenv("LINKUP_API_KEY", "lk-test")

    def fake_run(cmd, capture_output, text, env, timeout):
        calls.append(cmd)
        if "--extract-urls" in cmd:
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "provider": "linkup",
                "results": [{"url": "https://example.com/a", "content": "Full extracted evidence from page A."}],
            }), stderr="")
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "provider": "tavily",
            "results": [{"url": "https://example.com/a", "title": "A", "snippet": "Snippet A"}],
            "routing": {"provider": "tavily"},
        }), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    result = run(server.call_tool("web_answer", {"query": "explain A", "output": "json"}))
    payload = json.loads(result[0].text)

    assert payload["beta"] is True
    assert payload["freshness"]["applied"] == "none"
    assert payload["sources"][0]["url"] == "https://example.com/a"
    assert "Full extracted evidence" in payload["answer"]
    assert any("--extract-urls" in c for c in calls)


def test_web_answer_search_failure_returns_structured_error(monkeypatch):
    monkeypatch.setenv("WSP_ENABLE_WEB_ANSWER", "1")
    monkeypatch.setenv("BRAVE_API_KEY", "brv-test")

    def fake_run(cmd, capture_output, text, env, timeout):
        return SimpleNamespace(returncode=1, stdout="", stderr="provider exploded")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    result = run(server.call_tool("web_answer", {"query": "explain failure", "output": "json"}))
    payload = json.loads(result[0].text)

    assert payload["beta"] is True
    assert payload["stage"] == "search"
    assert "provider exploded" in payload["error"]


def test_web_answer_auto_freshness_english_only(monkeypatch):
    monkeypatch.setenv("WSP_ENABLE_WEB_ANSWER", "1")
    monkeypatch.setenv("BRAVE_API_KEY", "brv-test")
    seen = []

    def fake_run(cmd, capture_output, text, env, timeout):
        seen.append(cmd)
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "provider": "brave",
            "results": [{"url": "https://example.com/a", "title": "A", "snippet": "Snippet A"}],
        }), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    payload = json.loads(run(server.call_tool("web_answer", {"query": "latest updates", "freshness": "auto", "max_extracts": 0, "output": "json"}))[0].text)
    assert payload["freshness"]["applied"] == "week"
    assert "--time-range" in seen[0] and "week" in seen[0]

    seen.clear()
    payload = json.loads(run(server.call_tool("web_answer", {"query": "neueste nachrichten", "freshness": "auto", "max_extracts": 0, "output": "json"}))[0].text)
    assert payload["freshness"]["applied"] == "none"
    assert "--time-range" not in seen[0]


def test_web_answer_handles_malformed_source_url(monkeypatch):
    monkeypatch.setenv("WSP_ENABLE_WEB_ANSWER", "1")
    monkeypatch.setenv("BRAVE_API_KEY", "brv-test")

    def fake_run(cmd, capture_output, text, env, timeout):
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "provider": "brave",
            "results": [{"url": "http://", "title": "Broken", "snippet": "Still should not crash"}],
        }), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    payload = json.loads(run(server.call_tool("web_answer", {"query": "bad url", "max_extracts": 0, "output": "json"}))[0].text)
    assert payload["sources"][0]["url"] == "http://"


def test_cli_status_json_and_setup_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BRAVE_API_KEY", "brv-test")
    assert server.cli_main(["status", "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["search_configured"] is True
    assert "web_search" in status["tools_if_started_now"]

    env_file = tmp_path / ".env"
    assert server.cli_main(["setup", "--preset", "starter", "--env-file", str(env_file), "--dry-run", "--json"]) == 0
    setup = json.loads(capsys.readouterr().out)
    assert setup["preset"] == "starter"
    assert setup["web_answer_enabled"] is False
    assert "WSP_ENABLE_WEB_ANSWER" not in setup["snippet"]["mcpServers"]["web-search-plus"]["env"]
    assert "TAVILY_API_KEY" in setup["keys"]
    assert not env_file.exists()

    assert server.cli_main(["setup", "--preset", "starter", "--env-file", str(env_file), "--enable-answer", "--dry-run", "--json"]) == 0
    setup = json.loads(capsys.readouterr().out)
    assert setup["web_answer_enabled"] is True
    assert setup["snippet"]["mcpServers"]["web-search-plus"]["env"]["WSP_ENABLE_WEB_ANSWER"] == "1"


def test_cli_config_commands_persist_routing_preferences(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "config.json"
    monkeypatch.setenv(server.CONFIG_ENV_VAR, str(config_path))

    assert server.cli_main(["config", "show"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["routing_preferences"]["enabled"] is True

    assert server.cli_main(["config", "set-default", "brave"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["default_provider"] == "brave"
    assert payload["routing_preferences"]["enabled"] is False

    assert server.cli_main(["config", "set-routing", "on"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["routing_preferences"]["enabled"] is True

    assert server.cli_main(["config", "set-priority", "tavily,linkup,kilo-perplexity,brave"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["routing_preferences"]["provider_priority"] == ["tavily", "linkup", "kilo-perplexity", "brave"]

    assert server.cli_main(["config", "disable", "perplexity"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "perplexity" in payload["routing_preferences"]["disabled_providers"]

    assert server.cli_main(["config", "enable", "perplexity"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "perplexity" not in payload["routing_preferences"]["disabled_providers"]

    assert server.cli_main(["config", "set-threshold", "0.45"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["routing_preferences"]["confidence_threshold"] == 0.45

    assert server.cli_main(["config", "set-fallback", "tavily"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["routing_preferences"]["fallback_provider"] == "tavily"

    assert server.cli_main(["config", "reset", "--yes"]) == 0
    capsys.readouterr()
    assert any(config_path.parent.glob("config.json.bak-*"))


def test_status_json_includes_routing_preferences_without_secrets(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "config.json"
    monkeypatch.setenv(server.CONFIG_ENV_VAR, str(config_path))
    monkeypatch.setenv("BRAVE_API_KEY", "brv-super-secret")
    assert server.cli_main(["config", "set-default", "brave"]) == 0
    capsys.readouterr()

    assert server.cli_main(["status", "--json"]) == 0
    payload_text = capsys.readouterr().out
    payload = json.loads(payload_text)
    assert payload["default_provider"] == "brave"
    assert payload["routing_preferences"]["enabled"] is False
    assert "brv-super-secret" not in payload_text


def test_invalid_config_is_quarantined_by_server_loader(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"auto_routing":{"confidence_threshold": 4}}')
    monkeypatch.setenv(server.CONFIG_ENV_VAR, str(config_path))

    config, warning = server._load_behavior_config()
    assert config["auto_routing"]["confidence_threshold"] == 0.3
    assert warning and "Invalid config moved" in warning
    assert not config_path.exists()
    assert list(tmp_path.glob("config.json.broken-*"))


def test_search_runtime_honors_strict_fixed_provider_mode(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "defaults": {"provider": "brave"},
        "auto_routing": {
            "enabled": False,
            "fallback_provider": "tavily",
            "provider_priority": ["tavily", "brave"],
            "disabled_providers": [],
            "confidence_threshold": 0.3,
        },
    }))
    monkeypatch.setenv(search.CONFIG_ENV_VAR, str(config_path))
    monkeypatch.setenv("BRAVE_API_KEY", "brv-test")
    monkeypatch.setenv("TAVILY_API_KEY", "tv-test")
    monkeypatch.setattr(search.sys, "argv", ["search.py", "--query", "strict provider", "--provider", "auto", "--compact", "--no-cache"])
    calls = []

    def fake_brave(**kwargs):
        calls.append("brave")
        return {"provider": "brave", "results": [{"title": "B", "url": "https://example.com", "snippet": "ok"}]}

    def fake_tavily(**kwargs):
        calls.append("tavily")
        return {"provider": "tavily", "results": []}

    monkeypatch.setattr(search, "search_brave", fake_brave)
    monkeypatch.setattr(search, "search_tavily", fake_tavily)
    monkeypatch.setattr(search, "validate_api_key", lambda prov, config=None: f"{prov}-key-long-enough-for-test")
    search.main()
    payload = json.loads(capsys.readouterr().out)

    assert calls == ["brave"]
    assert payload["provider"] == "brave"
    assert payload["routing"]["reason"] == "auto_routing_disabled_default_provider"


def test_search_runtime_quarantines_semantic_invalid_config(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"defaults": {"provider": "not-real"}}))
    monkeypatch.setenv(search.CONFIG_ENV_VAR, str(config_path))

    config = search.load_config()
    stderr = capsys.readouterr().err
    assert config["defaults"]["provider"] == "serper"
    assert "Invalid config moved" in stderr
    assert not config_path.exists()
    assert list(tmp_path.glob("config.json.broken-*"))
