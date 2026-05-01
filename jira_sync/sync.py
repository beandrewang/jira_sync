"""CLI entry point for jira-sync tool."""

import sys

import click

from . import config
from .client import JiraClient
from .syncer import sync_comments


@click.group()
def cli():
    """Jira Sync Tool — sync comments between Jira instances."""


@cli.command()
@click.option("--name", required=True, help="Connection name (e.g. 'my', 'customer')")
@click.option("--url", required=True, help="Jira base URL (e.g. https://xxx.atlassian.net)")
@click.option("--email", required=True, help="Jira account email")
@click.option("--api-token", required=True, help="Jira API token")
def configure(name, url, email, api_token):
    """Save a Jira connection profile and verify it works."""
    click.echo(f"Testing connection '{name}' ... ", nl=False)
    client = JiraClient(url, email, api_token)
    if client.test_connection():
        click.echo(click.style("OK", fg="green"))
    else:
        click.echo(click.style("FAILED", fg="red"))
        click.echo(
            "Could not connect. Check your URL, email, and API token."
        )
        sys.exit(1)

    config.save_connection(name, url, email, api_token)
    click.echo(
        click.style(f"Connection '{name}' saved.", fg="green")
    )


@cli.command()
def list():
    """List all saved connection profiles."""
    connections = config.list_connections()
    if not connections:
        click.echo("No connections saved.")
        return
    click.echo("Saved connections:")
    for name in connections:
        conn = config.get_connection(name)
        click.echo(f"  • {name}  ({conn['url']} / {conn['email']})")


@cli.command()
@click.option("--name", required=True, help="Connection name to delete")
def delete(name):
    """Delete a saved connection profile."""
    if config.delete_connection(name):
        click.echo(click.style(f"Connection '{name}' deleted.", fg="green"))
    else:
        click.echo(click.style(f"Connection '{name}' not found.", fg="red"))
        sys.exit(1)


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be synced without posting")
def sync(dry_run):
    """Sync comments from source Jira to target Jira."""
    connections = config.list_connections()
    if len(connections) < 2:
        click.echo(
            "Please configure at least 2 connections first using 'configure' command."
        )
        sys.exit(1)

    # --- Select source connection ---
    click.echo("\nSelect SOURCE Jira (where comments come from):")
    for i, name in enumerate(connections, 1):
        conn = config.get_connection(name)
        click.echo(f"  {i}. {name}  ({conn['url']})")
    source_idx = click.prompt(
        "Enter number", type=click.IntRange(1, len(connections))
    )
    source_name = connections[source_idx - 1]
    source_conn = config.get_connection(source_name)

    # --- Select target connection ---
    click.echo("\nSelect TARGET Jira (where comments go to):")
    for i, name in enumerate(connections, 1):
        conn = config.get_connection(name)
        click.echo(f"  {i}. {name}  ({conn['url']})")
    target_idx = click.prompt(
        "Enter number", type=click.IntRange(1, len(connections))
    )
    target_name = connections[target_idx - 1]
    target_conn = config.get_connection(target_name)

    # --- Issue keys ---
    source_key = click.prompt("Source issue key", type=str)
    target_key = click.prompt("Target issue key", type=str)

    # --- Keywords ---
    keywords_str = click.prompt(
        "Filter keywords (comma-separated, leave empty for all)",
        default="",
    )
    keywords = (
        [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
        if keywords_str
        else None
    )

    # --- Confirm ---
    click.echo("\n" + "=" * 50)
    click.echo("Sync Plan:")
    click.echo(f"  Source:      {source_name}  →  {source_key}")
    click.echo(f"  Target:      {target_name}  →  {target_key}")
    click.echo(f"  Keywords:    {', '.join(keywords) if keywords else '(all comments)'}")
    click.echo(f"  Mode:        {'Dry run' if dry_run else 'Live'}")
    click.echo("=" * 50)
    click.confirm("Proceed?", abort=True)

    # --- Execute ---
    source_client = JiraClient(
        source_conn["url"], source_conn["email"], source_conn["api_token"]
    )
    target_client = JiraClient(
        target_conn["url"], target_conn["email"], target_conn["api_token"]
    )

    sync_comments(
        source_client=source_client,
        target_client=target_client,
        source_key=source_key,
        target_key=target_key,
        keywords=keywords,
        source_name=source_name,
        dry_run=dry_run,
    )


def main():
    cli()


if __name__ == "__main__":
    main()
