"""CLI entry point for aij commands."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import click

from aij import __version__


@click.group()
@click.version_option(version=__version__, prog_name="aij")
def main() -> None:
    """Automated daily thinking journal from AI coding assistant conversations."""
    _load_dotenv()


def _load_dotenv() -> None:
    """Load ~/.aij/.env into os.environ (won't overwrite existing vars)."""
    import os
    env_path = Path.home() / ".aij" / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# ── run ─────────────────────────────────────────────────────────────────

@main.command()
@click.option("--date", default=None, help="Date (YYYY-MM-DD). Default: today.")
@click.option("--weekly", "run_weekly", is_flag=True, help="Generate weekly rollup.")
@click.option("--monthly", "run_monthly", is_flag=True, help="Generate monthly rollup.")
@click.option("--all", "run_all", is_flag=True, help="Daily + weekly (if Mon) + monthly (if 1st).")
@click.option("--force", is_flag=True, help="Re-run even if output exists.")
@click.option("--poster", is_flag=True, help="Also generate poster.")
@click.option("--dry-run", is_flag=True, help="Print what would happen.")
@click.option("--signal-only", is_flag=True, default=True, help="Use signal extraction (default).")
@click.option("--config", "config_path", default=None, help="Config file path.")
def run(date: str | None, run_weekly: bool, run_monthly: bool, run_all: bool,
        force: bool, poster: bool, dry_run: bool, signal_only: bool,
        config_path: str | None) -> None:
    """Run the daily journal pipeline."""
    from aij.config import load_config
    from aij.date_utils import target_date, weekday_name
    from aij.pipeline import run_daily
    from aij.ui import banner, success, warn, error, info, Spinner, CHECK, CROSS

    config = load_config(Path(config_path) if config_path else None)
    tz_name = config["general"]["timezone"]

    from zoneinfo import ZoneInfo
    tz = ZoneInfo(tz_name)

    date_str = target_date(date, tz)
    day_name = weekday_name(date_str)

    banner("aij — Daily Thinking Summary", "%s %s" % (date_str, day_name))
    click.echo()

    if dry_run:
        info("Dry run — no LLM call, no output written")
        click.echo()

    # Progress callback for pipeline
    def on_progress(event: str, data: dict) -> None:
        if event == "source_found":
            name = data["name"]
            sessions = data["sessions"]
            projects = data["projects"]
            if data.get("warning"):
                warn("%s — %s" % (name, data["warning"]))
            else:
                success("%s — %d sessions, %d projects" % (name, sessions, projects))
        elif event == "no_sessions":
            error("No sessions found for %s" % date_str)
        elif event == "summarizer_start":
            click.echo()
            info("Summarizing (%s / %s)..." % (data["backend"], data["model"]))
        elif event == "summarizer_done":
            words = data["words"]
            click.echo(click.style("  ✓ ", fg="green") + "Summary generated (%d words)" % words)
        elif event == "output_ok":
            success("%s" % data["message"])
        elif event == "output_skip":
            warn("%s" % data["message"])

    t0 = time.time()

    entry = run_daily(date_str, config, dry_run=dry_run, progress=on_progress)

    elapsed = time.time() - t0

    click.echo()
    if entry:
        _save_last_run(date_str, config, entry)
        banner("Done in %.0fs" % elapsed)
    elif dry_run:
        banner("Dry run complete")
    else:
        error("No output generated for %s" % date_str)


def _save_last_run(date_str: str, config: dict, entry) -> None:
    """Write last run metadata for aij status."""
    try:
        from aij.config import CONFIG_DIR
        last_run_path = CONFIG_DIR / "last_run.json"
        word_count = len(entry.body.split()) if entry.body else 0
        data = {
            "date": date_str,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "word_count": word_count,
            "backend": config["summarizer"]["backend"],
        }
        last_run_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    except Exception:
        pass  # non-critical


# ── config ──────────────────────────────────────────────────────────────

@main.command()
@click.argument("action", default="show", type=click.Choice(["show", "edit", "set", "get", "path"]))
@click.argument("key", default=None, required=False)
@click.argument("value", default=None, required=False)
@click.option("--config", "config_path", default=None, help="Config file path.")
def config(action: str, key: str | None, value: str | None, config_path: str | None) -> None:
    """Manage aij configuration."""
    from aij.config import (
        config_path_str,
        get_nested,
        load_config,
        save_config,
        set_nested,
        CONFIG_PATH,
    )
    from aij.ui import success, warn, error

    cfg_path = Path(config_path) if config_path else None

    if action == "path":
        click.echo(cfg_path or CONFIG_PATH)
        return

    if action == "show":
        cfg = load_config(cfg_path)
        _print_config(cfg)
        return

    if action == "edit":
        import os
        editor = os.environ.get("EDITOR", "vim")
        path = cfg_path or CONFIG_PATH
        os.execvp(editor, [editor, str(path)])
        return

    if action == "get":
        if not key:
            error("Key required for 'config get'")
            sys.exit(1)
        cfg = load_config(cfg_path)
        result = get_nested(cfg, key)
        if result is None:
            warn("Key not found: %s" % key)
        else:
            click.echo(result)
        return

    if action == "set":
        if not key or not value:
            error("Key and value required for 'config set'")
            sys.exit(1)
        cfg = load_config(cfg_path)
        set_nested(cfg, key, value)
        save_config(cfg, cfg_path)
        success("%s = %s" % (key, value))
        return


def _print_config(config: dict, prefix: str = "") -> None:
    """Print config with secrets redacted."""
    from aij.ui import DIM
    secret_keys = {"api_key", "app_secret", "password", "webhook_url"}
    for key, value in config.items():
        full_key = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            _print_config(value, full_key)
        else:
            if any(s in key.lower() for s in secret_keys) and isinstance(value, str) and value:
                click.echo(click.style(full_key, **DIM) + " = " + click.style("***", fg="yellow"))
            else:
                click.echo(click.style(full_key, **DIM) + " = " + str(value))


# ── status ──────────────────────────────────────────────────────────────

@main.command()
def status() -> None:
    """Show aij status: sources, summarizer, outputs, last run."""
    from aij.config import load_config, CONFIG_DIR
    from aij.sources.registry import discover_sources
    from aij.summarizers.registry import get_summarizer
    from aij.ui import CHECK, CROSS, WARN, DIM, BOLD, GREEN, YELLOW, RED

    config = load_config()

    click.echo(click.style("  Sources", **BOLD))
    for source in discover_sources():
        detected = source.detect()
        if detected:
            path_short = _shorten_path(str(detected))
            click.echo("  %s %-18s %s" % (
                click.style("✓", fg=GREEN),
                source.display_name.split(" (")[0],  # strip "(experimental)"
                click.style(path_short, **DIM),
            ))
        else:
            name = source.display_name.split(" (")[0]
            extra = ""
            if "(" in source.display_name:
                extra = " " + click.style(source.display_name[source.display_name.index("("):], fg=YELLOW)
            click.echo("  %s %-18s %s%s" % (
                click.style("✗", fg=RED),
                name,
                click.style("not detected", **DIM),
                extra,
            ))

    click.echo()
    click.echo(click.style("  Summarizer", **BOLD))
    backend = config["summarizer"]["backend"]
    summarizer_config = config["summarizer"].get(backend, {})
    summarizer = get_summarizer(backend, summarizer_config)
    if summarizer:
        available = summarizer.check_availability()
        model = getattr(summarizer, "model", "?")
        icon = click.style("✓", fg=GREEN) if available else click.style("✗", fg=RED)
        status_text = "available" if available else "not available"
        click.echo("  %s %s (%s) — %s" % (icon, backend, model, status_text))

    click.echo()
    click.echo(click.style("  Outputs", **BOLD))
    outputs_config = config.get("outputs", {})
    for name, cfg in outputs_config.items():
        enabled = cfg.get("enabled", False)
        if enabled:
            click.echo("  %s %s" % (click.style("✓", fg=GREEN), name))
        else:
            click.echo("  %s %s" % (click.style("✗", fg=RED), click.style(name, **DIM)))

    # Last run
    last_run_path = CONFIG_DIR / "last_run.json"
    if last_run_path.exists():
        try:
            lr = json.loads(last_run_path.read_text())
            click.echo()
            click.echo(click.style("  Last run", **BOLD))
            click.echo("  %s %s  (%d words, %s)" % (
                click.style("•", **DIM),
                lr.get("date", "?"),
                lr.get("word_count", 0),
                lr.get("backend", "?"),
            ))
        except Exception:
            pass


def _shorten_path(p: str) -> str:
    return p.replace(str(Path.home()), "~")


# ── init ────────────────────────────────────────────────────────────────

@main.command()
@click.option("--config", "config_path", default=None, help="Config file path.")
def init(config_path: str | None) -> None:
    """Interactive setup wizard."""
    from aij.config import load_config, save_config, CONFIG_PATH
    from aij.sources.registry import _REGISTRY as source_registry
    from aij.summarizers.registry import list_summarizer_names
    from aij.ui import banner, success, warn, info, step, summary_box, arrow

    config = load_config()

    banner("aij — AI Thinking Journal", "Interactive Setup")
    click.echo()

    # ── Auto-detect sources ──
    click.echo(click.style("  Sources detected", bold=True))
    detected_sources = []
    for reg_key, source_cls in source_registry.items():
        source = source_cls()
        found = source.detect()
        if found:
            config["sources"][reg_key]["enabled"] = True
            detected_sources.append(reg_key)
            name = source.display_name.split(" (")[0]
            click.echo("  %s %s" % (click.style("✓", fg="green"), name))
        else:
            config["sources"][reg_key]["enabled"] = False
    if not detected_sources:
        warn("No AI tool sources detected")
    click.echo()

    while True:
        # ── Step 1/4: LLM backend ──
        step(1, 4, "LLM backend")
        backends = list_summarizer_names()
        backend = click.prompt("  Backend", type=click.Choice(backends), default="openai")
        config["summarizer"]["backend"] = backend

        # Improvement 4: API key / backend availability check
        _check_backend_available(backend)
        click.echo()

        # ── Step 2/4: Output destinations ──
        step(2, 4, "Output destinations")
        info("Local Markdown — always on")
        config["outputs"]["terminal"]["enabled"] = click.confirm("  Terminal display?", default=False)

        # Improvement 1: "Set up now or later?" for configurable outputs
        for output_key, label, fields in _OUTPUT_SETUP_FIELDS:
            choice = _ask_output_setup(label)
            if choice == "now":
                config["outputs"][output_key]["enabled"] = True
                _setup_output_now(config, output_key, fields)
            elif choice == "later":
                config["outputs"][output_key]["enabled"] = True
                arrow("Enable later: aij config set outputs.%s.<field> <value>" % output_key)
            else:
                config["outputs"][output_key]["enabled"] = False
        click.echo()

        # ── Step 3/4: Confirm ──
        step(3, 4, "Review")

        enabled_sources = [k for k in source_registry if config["sources"].get(k, {}).get("enabled")]
        enabled_outputs = ["markdown"] + [k for k in config.get("outputs", {}) if config["outputs"][k].get("enabled") and k != "markdown"]

        summary_box([
            ("Backend:", config["summarizer"]["backend"]),
            ("Sources:", ", ".join(enabled_sources) if enabled_sources else "none"),
            ("Outputs:", ", ".join(enabled_outputs)),
            ("Timezone:", config["general"]["timezone"]),
        ])
        click.echo()

        # Improvement 2: allow going back
        save_choice = click.prompt(
            "  Save this config?",
            type=click.Choice(["yes", "back"], case_sensitive=False),
            default="yes",
        )
        if save_choice.lower() == "back":
            click.echo()
            info("Restarting wizard...")
            click.echo()
            config = load_config()
            continue

        break

    # ── Step 4/4: Save ──
    step(4, 4, "Save")
    cfg_path = Path(config_path) if config_path else CONFIG_PATH
    save_config(config, cfg_path)
    click.echo()
    success("Config saved to %s" % cfg_path)

    # Improvement 3: offer to run journal now
    click.echo()
    if click.confirm("  Run a journal now?", default=True):
        click.echo()
        _run_journal_inline(config)


def _check_backend_available(backend: str) -> None:
    """Check if the selected backend's API key or service is available."""
    import os
    import shutil
    from aij.config import CONFIG_DIR
    from aij.ui import warn, success, arrow, info

    checks = {
        "openai": ("OPENAI_API_KEY", "env"),
        "anthropic": ("ANTHROPIC_API_KEY", "env"),
        "ollama": ("http://localhost:11434", "url"),
        "claude_cli": ("claude", "path"),
    }
    check = checks.get(backend)
    if not check:
        return

    name, kind = check
    if kind == "env":
        if os.getenv(name):
            return
        click.echo()
        warn("%s not found in environment" % name)
        click.echo()
        choice = click.prompt(
            "  What to do?",
            type=click.Choice(["enter", "later", "quit"], case_sensitive=False),
            default="enter",
        )
        choice = choice.lower()
        if choice == "enter":
            key_value = click.prompt("  Paste your %s" % name, hide_input=True)
            if key_value.strip():
                _save_env_key(name, key_value.strip())
                os.environ[name] = key_value.strip()
                success("Key saved to ~/.aij/.env and loaded for this session")
            else:
                warn("Empty value — skipped")
        elif choice == "later":
            arrow('Set it later: export %s="your-key-here"' % name)
            arrow("Add to ~/.zshrc to persist across sessions.")
        else:
            raise SystemExit(0)
    elif kind == "path":
        if not shutil.which(name):
            click.echo()
            warn("'%s' not found in PATH" % name)
            click.echo()
            if not click.confirm("  Continue anyway?", default=False):
                raise SystemExit(0)
    elif kind == "url":
        try:
            import urllib.request
            urllib.request.urlopen(name, timeout=3)
        except Exception:
            click.echo()
            warn("Ollama not reachable at %s" % name)
            click.echo()
            if not click.confirm("  Continue anyway?", default=False):
                raise SystemExit(0)


def _save_env_key(key_name: str, key_value: str) -> None:
    """Append or update a key in ~/.aij/.env (mode 600)."""
    import os
    from aij.config import CONFIG_DIR

    env_path = CONFIG_DIR / ".env"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    lines = []
    replaced = False
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(key_name + "="):
                lines.append('%s="%s"' % (key_name, key_value))
                replaced = True
            else:
                lines.append(line)
    if not replaced:
        lines.append('%s="%s"' % (key_name, key_value))

    env_path.write_text("\n".join(lines) + "\n")
    os.chmod(env_path, 0o600)


_OUTPUT_SETUP_FIELDS = [
    ("lark_webhook", "Lark group webhook", [
        ("webhook_url", "Webhook URL", "Create a bot in your Lark group settings to get the webhook URL"),
    ]),
    ("lark_app", "Lark app DM", [
        ("app_id", "App ID", "Create a custom app at https://open.feishu.cn/app"),
        ("app_secret", "App Secret (stored in config)", "Found in app credentials page"),
        ("open_id", "Recipient open_id", "Use lark-cli contact +resolve <name> to find"),
    ]),
    ("email", "Email delivery", [
        ("from_addr", "From address", "Your email address for sending"),
        ("to_addr", "To address", "Recipient email address"),
        ("smtp_host", "SMTP host", "e.g. smtp.gmail.com"),
        ("smtp_port", "SMTP port", "e.g. 587"),
    ]),
]


def _ask_output_setup(label: str) -> str:
    """Ask user: now / later / skip for an output destination."""
    click.echo()
    choice = click.prompt(
        "  %s" % label,
        type=click.Choice(["now", "later", "skip"], case_sensitive=False),
        default="skip",
    )
    return choice.lower()


def _setup_output_now(config: dict, output_key: str, fields: list) -> None:
    """Walk through each field for an output, prompting with guidance."""
    from aij.ui import info, arrow
    for field_key, prompt_text, help_text in fields:
        info(help_text)
        value = click.prompt("  %s (or 'skip')" % prompt_text, default="skip")
        if value.lower() == "skip":
            arrow("Skipped — set later: aij config set outputs.%s.%s <value>" % (output_key, field_key))
            continue
        config["outputs"][output_key][field_key] = value


def _run_journal_inline(config: dict) -> None:
    """Run the journal pipeline inline after init."""
    from aij.date_utils import target_date, weekday_name
    from aij.pipeline import run_daily
    from aij.ui import banner, success, warn, error, info

    tz_name = config["general"]["timezone"]
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(tz_name)

    date_str = target_date(None, tz)
    day_name = weekday_name(date_str)

    banner("aij — First Run", "%s %s" % (date_str, day_name))
    click.echo()

    def on_progress(event: str, data: dict) -> None:
        if event == "source_found":
            name = data["name"]
            sessions = data["sessions"]
            projects = data["projects"]
            if data.get("warning"):
                warn("%s — %s" % (name, data["warning"]))
            else:
                success("%s — %d sessions, %d projects" % (name, sessions, projects))
        elif event == "no_sessions":
            error("No sessions found for %s" % date_str)
        elif event == "summarizer_start":
            click.echo()
            info("Summarizing (%s / %s)..." % (data["backend"], data["model"]))
        elif event == "summarizer_done":
            words = data["words"]
            click.echo(click.style("  ✓ ", fg="green") + "Summary generated (%d words)" % words)
        elif event == "output_ok":
            success("%s" % data["message"])
        elif event == "output_skip":
            warn("%s" % data["message"])

    t0 = time.time()
    entry = run_daily(date_str, config, progress=on_progress)
    elapsed = time.time() - t0

    click.echo()
    if entry:
        _save_last_run(date_str, config, entry)
        banner("Done in %.0fs" % elapsed)
    else:
        error("No output generated for %s" % date_str)


if __name__ == "__main__":
    main()
