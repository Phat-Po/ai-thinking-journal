"""CLI entry point for aij commands."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from aij import __version__


@click.group()
@click.version_option(version=__version__, prog_name="aij")
def main() -> None:
    """Automated daily thinking journal from AI coding assistant conversations."""
    pass


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
    from aij.date_utils import target_date
    from aij.pipeline import run_daily

    config = load_config(Path(config_path) if config_path else None)
    tz_name = config["general"]["timezone"]

    from zoneinfo import ZoneInfo
    tz = ZoneInfo(tz_name)

    date_str = target_date(date, tz)

    if dry_run:
        print("=== Dry Run ===")
        print("Date: %s" % date_str)
        print("Config: %s" % (config_path or "~/.aij/config.toml"))

    entry = run_daily(date_str, config, dry_run=dry_run)

    if entry:
        print("Done. Journal entry for %s" % date_str)
    elif dry_run:
        print("Dry run complete.")
    else:
        print("No output generated for %s" % date_str)


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

    cfg_path = Path(config_path) if config_path else None

    if action == "path":
        print(cfg_path or CONFIG_PATH)
        return

    if action == "show":
        config = load_config(cfg_path)
        _print_config(config)
        return

    if action == "edit":
        import os
        editor = os.environ.get("EDITOR", "vim")
        path = cfg_path or CONFIG_PATH
        os.execvp(editor, [editor, str(path)])
        return

    if action == "get":
        if not key:
            print("Error: key required for 'config get'", file=sys.stderr)
            sys.exit(1)
        config = load_config(cfg_path)
        result = get_nested(config, key)
        if result is None:
            print("Key not found: %s" % key)
        else:
            print(result)
        return

    if action == "set":
        if not key or not value:
            print("Error: key and value required for 'config set'", file=sys.stderr)
            sys.exit(1)
        config = load_config(cfg_path)
        set_nested(config, key, value)
        save_config(config, cfg_path)
        print("Set %s = %s" % (key, value))
        return


def _print_config(config: dict, prefix: str = "") -> None:
    """Print config with secrets redacted."""
    secret_keys = {"api_key", "app_secret", "password", "webhook_url"}
    for key, value in config.items():
        full_key = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            _print_config(value, full_key)
        else:
            if any(s in key.lower() for s in secret_keys) and isinstance(value, str) and value:
                print("%s = ***" % full_key)
            else:
                print("%s = %s" % (full_key, value))


@main.command()
def status() -> None:
    """Show aij status: sources, summarizer, outputs, last run."""
    from aij.config import load_config
    from aij.sources.registry import discover_sources
    from aij.summarizers.registry import get_summarizer

    config = load_config()

    print("Sources:")
    for source in discover_sources():
        detected = source.detect()
        if detected:
            print("  ✓ %s — %s" % (source.display_name, detected))
        else:
            print("  ✗ %s — not detected" % source.display_name)

    backend = config["summarizer"]["backend"]
    summarizer_config = config["summarizer"].get(backend, {})
    summarizer = get_summarizer(backend, summarizer_config)
    if summarizer:
        available = summarizer.check_availability()
        model = getattr(summarizer, "model", "?")
        status_icon = "✓" if available else "✗"
        print("\nSummarizer: %s (%s) — %s %s" % (backend, model, status_icon,
            "available" if available else "not available"))

    print("\nOutputs:")
    outputs_config = config.get("outputs", {})
    for name, cfg in outputs_config.items():
        if cfg.get("enabled", False):
            print("  ✓ %s" % name)
        else:
            print("  ✗ %s" % name)


@main.command()
@click.option("--config", "config_path", default=None, help="Config file path.")
def init(config_path: str | None) -> None:
    """Interactive setup wizard."""
    click.echo("=== aij init ===")
    click.echo("This will create ~/.aij/config.toml with your settings.")
    click.echo("")

    from aij.config import load_config, save_config, CONFIG_PATH

    config = load_config()

    # Step 1: Detect sources
    click.echo("Step 1: Detecting AI tool sources...")
    from aij.sources.registry import discover_sources
    for source in discover_sources():
        detected = source.detect()
        if detected:
            enabled = click.confirm("  Found %s at %s. Enable?" % (source.display_name, detected),
                                   default=True)
            config["sources"][source.name]["enabled"] = enabled
        else:
            click.echo("  %s: not detected" % source.display_name)

    # Step 2: Timezone
    click.echo("")
    tz = click.prompt("Step 2: Timezone", default=config["general"]["timezone"])
    config["general"]["timezone"] = tz

    # Step 3: Frequency
    click.echo("")
    click.echo("Step 3: Report frequency")
    freq = click.Choice(["daily", "daily+weekly", "all"])
    config["schedule"]["frequency"] = click.prompt("  Frequency", type=freq, default="all")

    # Step 4: LLM backend
    click.echo("")
    click.echo("Step 4: LLM backend")
    from aij.summarizers.registry import list_summarizer_names
    backends = list_summarizer_names()
    backend = click.prompt("  Backend", type=click.Choice(backends), default="openai")
    config["summarizer"]["backend"] = backend

    # Step 5: Poster
    click.echo("")
    poster = click.confirm("Step 5: Generate daily poster image? (requires OpenAI API)", default=False)
    config["poster"]["enabled"] = poster

    # Step 6: Output destinations
    click.echo("")
    click.echo("Step 6: Output destinations")
    click.echo("  Local Markdown is always enabled.")
    config["outputs"]["terminal"]["enabled"] = click.confirm("  Enable terminal display?", default=False)
    config["outputs"]["lark_webhook"]["enabled"] = click.confirm("  Enable Lark webhook (group notifications)?", default=False)
    config["outputs"]["lark_app"]["enabled"] = click.confirm("  Enable Lark custom app (DM + images)?", default=False)
    config["outputs"]["email"]["enabled"] = click.confirm("  Enable email delivery?", default=False)

    # Step 7: Conditional output config
    click.echo("")
    if config["outputs"]["lark_webhook"]["enabled"]:
        click.echo("Step 7a: Lark Webhook configuration")
        webhook_url = click.prompt("  Webhook URL", default="")
        if webhook_url:
            config["outputs"]["lark_webhook"]["webhook_url"] = webhook_url

    if config["outputs"]["lark_app"]["enabled"]:
        click.echo("Step 7b: Lark App configuration")
        app_id = click.prompt("  App ID", default="")
        if app_id:
            config["outputs"]["lark_app"]["app_id"] = app_id
        click.echo("  App secret should be set via env: LARK_APP_SECRET")
        user_id = click.prompt("  Recipient open_id (for DM)", default="")
        if user_id:
            config["outputs"]["lark_app"]["user_id"] = user_id

    if config["outputs"]["email"]["enabled"]:
        click.echo("Step 7c: Email SMTP configuration")
        config["outputs"]["email"]["smtp_host"] = click.prompt("  SMTP host", default="smtp.gmail.com")
        config["outputs"]["email"]["smtp_port"] = click.prompt("  SMTP port", default=587, type=int)
        config["outputs"]["email"]["from_addr"] = click.prompt("  From address", default="")
        config["outputs"]["email"]["to_addr"] = click.prompt("  To address", default="")
        click.echo("  Password should be set via env: AIJ_EMAIL_PASSWORD")

    # Step 8: Save
    click.echo("")
    cfg_path = Path(config_path) if config_path else CONFIG_PATH
    save_config(config, cfg_path)
    click.echo("Config saved to: %s" % cfg_path)
    click.echo("Done! Run 'aij run' to generate your first journal entry.")


if __name__ == "__main__":
    main()
