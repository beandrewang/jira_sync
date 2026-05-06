"""Core sync logic: fetch, filter, deduplicate, and sync comments and descriptions."""

import hashlib

from . import client as cli


def _body_fingerprint(body: str) -> str:
    """Return a short hash of the first 100 chars of body for dedup."""
    return hashlib.sha256(body[:100].encode()).hexdigest()[:16]


def filter_comments(comments: list[dict], keywords: list[str]) -> list[dict]:
    """Return comments whose body matches any keyword (case-insensitive)."""
    if not keywords:
        return comments
    keywords_lower = [k.lower() for k in keywords]
    result = []
    for c in comments:
        body_lower = c["body"].lower()
        if any(kw in body_lower for kw in keywords_lower):
            result.append(c)
    return result


def format_comment_for_sync(
    comment: dict,
    source_name: str = "Source",
) -> str:
    """Format a comment for posting to the target Jira with attribution."""
    lines = [
        f"[Synced from {source_name} Jira]",
        f"Author: {comment['author_display']}",
        f"Date: {comment['created']}",
        "",
        comment["body"],
    ]
    return "\n".join(lines)


def get_existing_fingerprints(target_client: cli.JiraClient, target_key: str) -> set[str]:
    """Return set of body fingerprints already in the target issue."""
    existing = target_client.get_issue_comments(target_key)
    return {_body_fingerprint(c["body"]) for c in existing}


def format_description_for_sync(
    issue: dict,
    source_key: str,
    source_name: str = "Source",
) -> str:
    """Format an issue description for syncing with attribution header."""
    lines = [
        f"[Synced from {source_name} Jira]",
        f"Source: {source_key} - {issue['summary']}",
        "",
        issue["description"],
    ]
    return "\n".join(lines)


def sync_description(
    source_client: cli.JiraClient,
    target_client: cli.JiraClient,
    source_key: str,
    target_key: str,
    source_name: str = "Source",
    dry_run: bool = False,
) -> bool:
    """Sync issue description from source to target.

    Returns True if the description was synced (or would be in dry-run).
    """
    print(f"Fetching description from {source_key} ...")
    source_issue = source_client.get_issue(source_key)
    if not source_issue["description"]:
        print("  → Source issue has no description. Nothing to sync.")
        return False

    print(f"  → Source: {source_issue['summary']}")
    print(f"  → Description: {source_issue['description'][:120]}...")

    formatted = format_description_for_sync(source_issue, source_key, source_name)
    source_fp = _body_fingerprint(formatted)

    print(f"Fetching description from {target_key} ...")
    target_issue = target_client.get_issue(target_key)
    target_fp = _body_fingerprint(target_issue["description"]) if target_issue["description"] else ""

    if source_fp == target_fp:
        print("  ⏭  Description already synced (fingerprint match). Nothing to sync.")
        return False

    if dry_run:
        print("\n[Dry run] Description would be updated on target.")
        return True

    print(f"\nUpdating description on {target_key} ...")
    try:
        target_client.update_issue_description(target_key, formatted)
        print("  ✓ Description synced successfully.")
        return True
    except Exception as e:
        print(f"  ✗ Failed to sync description: {e}")
        return False


def sync_comments(
    source_client: cli.JiraClient,
    target_client: cli.JiraClient,
    source_key: str,
    target_key: str,
    keywords: list[str] | None = None,
    source_name: str = "Source",
    dry_run: bool = False,
) -> list[dict]:
    """Fetch source comments, filter by keywords, and sync to target.

    Returns the list of comments that would be / were synced.
    """
    print(f"Fetching comments from {source_key} ...")
    source_comments = source_client.get_issue_comments(source_key)
    print(f"  → {len(source_comments)} total comments")

    filtered = filter_comments(source_comments, keywords or [])
    print(f"  → {len(filtered)} comments match keyword filter")

    if not filtered:
        print("No matching comments to sync.")
        return []

    print(f"Fetching existing comments from {target_key} ...")
    existing_fps = get_existing_fingerprints(target_client, target_key)
    print(f"  → {len(existing_fps)} existing comments")

    to_sync = []
    for c in filtered:
        formatted = format_comment_for_sync(c, source_name)
        fp = _body_fingerprint(formatted)
        if fp in existing_fps:
            print(f"  ⏭  Skipping (duplicate): comment #{c['id']} by {c['author_display']}")
        else:
            to_sync.append(c)

    if not to_sync:
        print("All matching comments already exist in target. Nothing to sync.")
        return []

    print(f"\nComments to sync ({len(to_sync)}):")
    for i, c in enumerate(to_sync, 1):
        preview = c["body"][:120].replace("\n", " ")
        print(f"  {i}. [{c['author_display']}] {preview}...")

    if dry_run:
        print("\n[Dry run] No comments were posted.")
        return to_sync

    print(f"\nSyncing {len(to_sync)} comments to {target_key} ...")
    synced = []
    for c in to_sync:
        formatted = format_comment_for_sync(c, source_name)
        try:
            target_client.add_comment(target_key, formatted)
            synced.append(c)
            print(f"  ✓ Synced comment #{c['id']}")
        except Exception as e:
            print(f"  ✗ Failed to sync comment #{c['id']}: {e}")

    print(f"\nDone! {len(synced)}/{len(to_sync)} comments synced.")
    return synced
