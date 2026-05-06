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
        comment["body"],
    ]
    return "\n".join(lines)


def get_existing_fingerprints(target_client: cli.JiraClient, target_key: str) -> set[str]:
    """Return set of body fingerprints already in the target issue."""
    existing = target_client.get_issue_comments(target_key)
    return {_body_fingerprint(c["body"]) for c in existing}


def _collect_attachment_ids(adf_node) -> list[dict]:
    """Walk ADF and collect attachment info from media nodes."""
    results = []
    if isinstance(adf_node, dict):
        if adf_node.get("type") == "media":
            attrs = adf_node.get("attrs", {})
            entry = {
                "id": attrs.get("id", ""),
                "alt": attrs.get("alt", ""),
                "filename": attrs.get("filename", ""),
                "type": attrs.get("type", ""),
            }
            if not entry["id"]:
                entry["id"] = attrs.get("fileId", "")
            results.append(entry)
        for child in adf_node.get("content", []):
            results.extend(_collect_attachment_ids(child))
    elif isinstance(adf_node, list):
        for item in adf_node:
            results.extend(_collect_attachment_ids(item))
    return results


def _transfer_attachments(
    source_client: cli.JiraClient,
    target_client: cli.JiraClient,
    source_key: str,
    target_key: str,
    adf_node,
    verbose: bool = False,
) -> dict[str, str]:
    """Download attachments from source, upload to target.

    Returns mapping: old ADF UUID → new media file UUID.
    """
    att_infos = _collect_attachment_ids(adf_node)
    if not att_infos:
        return {}

    if verbose:
        print(f"  [verbose] {len(att_infos)} media node(s) found in ADF")

    src_attachments = source_client.get_issue_attachments(source_key)
    filename_to_id = {a["filename"]: a["id"] for a in src_attachments}

    mapping = {}
    seen = set()
    for info in att_infos:
        label = info["alt"] or info["filename"] or ""
        raw_id = info["id"]
        plain_key = cli._parse_plain_attachment_id(raw_id)

        rest_id = filename_to_id.get(label) or filename_to_id.get(info["filename"])
        if not rest_id:
            if verbose:
                print(f"  ⚠ No source attachment match for: {label}")
            continue

        if rest_id in seen:
            continue
        seen.add(rest_id)

        try:
            filename, data = source_client.download_attachment(rest_id)
        except Exception as e:
            print(f"  ✗ Download failed: {filename if 'filename' in dir() else label} — {e}")
            continue

        try:
            result = target_client.upload_attachment(target_key, filename, data)
            att_id = str(result["id"])
            media_uuid = target_client.resolve_media_uuid(att_id)
            if media_uuid:
                mapping[plain_key] = media_uuid
                if verbose:
                    print(f"  📎 {filename} → uploaded (UUID: {media_uuid[:16]}...)")
            else:
                print(f"  ⚠ {filename} uploaded but media UUID not resolved")
        except Exception as e:
            print(f"  ✗ Upload failed: {filename} — {e}")

    return mapping


def _build_comment_adf(
    comment: dict, source_name: str,
    media_id_mapping: dict[str, str] | None = None,
    target_content_id: str = "",
) -> dict:
    """Build ADF body for a comment with attribution header prepended."""
    header_nodes = [
        cli.text_to_adf_paragraph(f"[Synced from {source_name} Jira]"),
        cli.text_to_adf_paragraph(f"Author: {comment['author_display']}"),
        cli.text_to_adf_paragraph(f"Date: {comment['created']}"),
    ]
    original = comment.get("body_adf", {}).get("content", [])
    sanitized = cli.sanitize_adf_node(original, media_id_mapping, target_content_id)
    return {"type": "doc", "version": 1, "content": header_nodes + sanitized}


def _build_description_adf(
    issue: dict,
    source_key: str,
    source_name: str,
    media_id_mapping: dict[str, str] | None = None,
    target_content_id: str = "",
) -> dict:
    """Build ADF body for a description with attribution header prepended."""
    header_nodes = [
        cli.text_to_adf_paragraph(f"[Synced from {source_name} Jira]"),
        cli.text_to_adf_paragraph(f"Source: {source_key} - {issue['summary']}"),
    ]
    original = issue.get("description_adf", {}).get("content", [])
    sanitized = cli.sanitize_adf_node(original, media_id_mapping, target_content_id)
    return {"type": "doc", "version": 1, "content": header_nodes + sanitized}


def format_description_for_sync(
    issue: dict,
    source_key: str,
    source_name: str = "Source",
) -> str:
    """Format an issue description for syncing with attribution header."""
    lines = [
        f"[Synced from {source_name} Jira]",
        f"Source: {source_key} - {issue['summary']}",
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
    verbose: bool = False,
) -> bool:
    """Sync issue description from source to target."""
    print(f"Fetching description from {source_key} ...")
    source_issue = source_client.get_issue(source_key)
    if not source_issue["description"]:
        print("  → Source issue has no description. Nothing to sync.")
        return False

    print(f"  → Source: {source_issue['summary']}")

    formatted = format_description_for_sync(source_issue, source_key, source_name)
    source_fp = _body_fingerprint(formatted)

    target_issue = target_client.get_issue(target_key)
    target_fp = _body_fingerprint(target_issue["description"]) if target_issue["description"] else ""

    if source_fp == target_fp:
        print("  ⏭  Description already synced (fingerprint match). Nothing to sync.")
        return False

    if dry_run:
        print("\n[Dry run] Description would be updated on target.")
        return True

    print(f"Updating description on {target_key} ...")
    try:
        id_mapping = _transfer_attachments(
            source_client, target_client,
            source_key, target_key,
            source_issue.get("description_adf", {}),
            verbose=verbose,
        )
        target_issue_id = target_client.get_issue(target_key)["id"]
        adf = _build_description_adf(
            source_issue, source_key, source_name, id_mapping, target_issue_id
        )
        target_client.update_issue_description(target_key, adf)
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
    verbose: bool = False,
) -> list[dict]:
    """Fetch source comments, filter by keywords, and sync to target."""
    print(f"Fetching comments from {source_key} ...")
    source_comments = source_client.get_issue_comments(source_key)
    print(f"  → {len(source_comments)} total comments")

    filtered = filter_comments(source_comments, keywords or [])
    print(f"  → {len(filtered)} comments match keyword filter")

    if not filtered:
        print("No matching comments to sync.")
        return []

    existing_fps = get_existing_fingerprints(target_client, target_key)

    to_sync = []
    for c in filtered:
        formatted = format_comment_for_sync(c, source_name)
        fp = _body_fingerprint(formatted)
        if fp in existing_fps:
            if verbose:
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
    target_issue_id = target_client.get_issue(target_key)["id"]
    synced = []
    for c in to_sync:
        id_mapping = _transfer_attachments(
            source_client, target_client,
            source_key, target_key,
            c.get("body_adf", {}),
            verbose=verbose,
        )
        adf = _build_comment_adf(c, source_name, id_mapping, target_issue_id)
        try:
            target_client.add_comment(target_key, adf)
            synced.append(c)
            print(f"  ✓ Synced comment #{c['id']}")
        except Exception as e:
            print(f"  ✗ Failed to sync comment #{c['id']}: {e}")

    print(f"\nDone! {len(synced)}/{len(to_sync)} comments synced.")
    return synced
