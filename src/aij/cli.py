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
    pass


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
    from aij.ui import banner, success, warn, info, step, summary_box, CHECK, DOT

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

    # ── Step 1/4: LLM backend ──
    step(1, 4, "LLM backend")
    backends = list_summarizer_names()
    backend = click.prompt("  Backend", type=click.Choice(backends), default="openai")
    config["summarizer"]["backend"] = backend
    click.echo()

    # ── Step 2/4: Output destinations ──
    step(2, 4, "Output destinations")
    info("Local Markdown — always on")
    config["outputs"]["terminal"]["enabled"] = click.confirm("  Terminal display?", default=False)
    config["outputs"]["lark_webhook"]["enabled"] = click.confirm("  Lark group webhook?", default=False)
    config["outputs"]["lark_app"]["enabled"] = click.confirm("  Lark app DM?", default=False)
    config["outputs"]["email"]["enabled"] = click.confirm("  Email delivery?", default=False)
    click.echo()

    # ── Step 3/4: Hints for enabled outputs ──
    step(3, 4, "Configuration hints")
    hints = []
    if config["outputs"]["lark_webhook"]["enabled"]:
        hints.append("Lark webhook: aij config set outputs.lark_webhook.webhook_url <url>")
    if config["outputs"]["lark_app"]["enabled"]:
        hints.append("Lark app: aij config set outputs.lark_app.app_id <id>")
        hints.append("  env: export LARK_APP_SECRET=<secret>")
    if config["outputs"]["email"]["enabled"]:
        hints.append("Email: aij config set outputs.email.from_addr <addr>")
        hints.append("  env: export AIJ_EMAIL_PASSWORD=<password>")
    if hints:
        for h in hints:
            click.echo(click.style("  → ", fg="cyan") + h)
    else:
        info("No additional configuration needed")
    click.echo()

    # ── Step 4/4: Confirm & save ──
    step(4, 4, "Confirm & save")

    enabled_sources = [k for k in source_registry if config["sources"].get(k, {}).get("enabled")]
    enabled_outputs = ["markdown"] + [k for k in config.get("outputs", {}) if config["outputs"][k].get("enabled") and k != "markdown"]

    summary_box([
        ("Backend:", config["summarizer"]["backend"]),
        ("Sources:", ", ".join(enabled_sources) if enabled_sources else "none"),
        ("Outputs:", ", ".join(enabled_outputs)),
        ("Timezone:", config["general"]["timezone"]),
    ])
    click.echo()

    if not click.confirm("  Save this config?", default=True):
        warn("Aborted — config not saved")
        return

    cfg_path = Path(config_path) if config_path else CONFIG_PATH
    save_config(config, cfg_path)
    click.echo()
    success("Config saved to %s" % cfg_path)
    click.echo(click.style("  → ", fg="cyan") + "Run 'aij run' to generate your first journal entry.")


if __name__ == "__main__":
    main()
