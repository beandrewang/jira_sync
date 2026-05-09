"""Jira Cloud REST API client.

Uses Basic Auth (email + API token) against Jira Cloud REST API v3.
"""

import base64

import requests


def extract_text_from_adf(node) -> str:
    """Recursively extract plain text from an Atlassian Document Format node."""
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        parts = []
        for child in node.get("content", []):
            parts.append(extract_text_from_adf(child))
        if node.get("type") in ("paragraph", "heading", "listItem"):
            parts.append("\n")
        if node.get("type") == "bulletList":
            parts.append("\n")
        return "".join(parts)
    return ""


def text_to_adf_paragraph(text: str) -> dict:
    """Convert a single line of plain text to an ADF paragraph node."""
    return {
        "type": "paragraph",
        "content": [{"type": "text", "text": text}],
    }


def _parse_plain_attachment_id(ari: str) -> str:
    """Extract plain numeric attachment ID from an ARI.

    E.g. 'ari:cloud:attachments::att/12345:file' → '12345'
    """
    import re

    m = re.search(r"att(?:achment)?[/:]([\w-]+)", ari, re.IGNORECASE)
    return m.group(1) if m else ari


def sanitize_adf_node(node, media_id_mapping=None, target_content_id=""):
    """Recursively replace nodes that reference local Jira entities.

    Also strips all non-essential attrs to avoid cross-instance validation issues.
    Returns a new node (or list of nodes for expanded mediaGroup).
    """
    if media_id_mapping is None:
        media_id_mapping = {}

    if isinstance(node, list):
        result = []
        for n in node:
            sanitized = sanitize_adf_node(n, media_id_mapping, target_content_id)
            if isinstance(sanitized, list):
                result.extend(sanitized)
            else:
                result.append(sanitized)
        return result

    if not isinstance(node, dict):
        return node

    node_type = node.get("type", "")

    # --- Media nodes: update ID if synced, otherwise placeholder ---
    if node_type == "mediaSingle":
        old_id = ""
        for child in node.get("content", []):
            if child.get("type") == "media":
                ari = child.get("attrs", {}).get("id", "")
                old_id = _parse_plain_attachment_id(ari)
                break
        if old_id and old_id in media_id_mapping:
            new_id = media_id_mapping[old_id]
            return _update_media_ids(node, old_id, new_id, target_content_id)
        else:
            alt = _media_alt_text(node)
            return text_to_adf_paragraph(f"[{alt}]")

    if node_type == "media":
        ari = node.get("attrs", {}).get("id", "")
        old_id = _parse_plain_attachment_id(ari)
        if old_id and old_id in media_id_mapping:
            return _update_media_ids(
                node, old_id, media_id_mapping[old_id], target_content_id
            )
        else:
            alt = node.get("attrs", {}).get("alt", "") or "Image"
            return text_to_adf_paragraph(f"[{alt}]")

    if node_type == "mediaGroup":
        results = []
        for child in node.get("content", []):
            results.append(sanitize_adf_node(child, media_id_mapping, target_content_id))
        return results

    # Replace mention with text
    if node_type == "mention":
        display = node.get("attrs", {}).get("text", "@unknown")
        return {"type": "text", "text": display}

    # Replace extension / inlineExtension / inlineCard with text placeholders.
    # These are typically inline nodes; replacing them with a paragraph would
    # create nested paragraphs (invalid ADF) when they appear inside a paragraph.
    if node_type == "extension":
        return {"type": "text", "text": "[Embedded content]"}

    if node_type == "inlineExtension":
        return {"type": "text", "text": "[Embedded content]"}

    if node_type == "inlineCard":
        url = node.get("attrs", {}).get("url", "")
        label = f"[Link: {url}]" if url else "[Embedded link]"
        return {"type": "text", "text": label}

    # Pass through unchanged (only recursively process children)
    if "content" in node:
        new_node = dict(node)
        new_node["content"] = sanitize_adf_node(
            node["content"], media_id_mapping, target_content_id
        )
        return new_node
    return node


def _media_alt_text(media_single_node: dict) -> str:
    """Extract alt text from a mediaSingle node for fallback placeholder."""
    for child in media_single_node.get("content", []):
        if child.get("type") == "media":
            return child.get("attrs", {}).get("alt", "") or "Image"
    return "Image"


def _update_media_ids(node: dict, old_id: str, new_id: str,
                      target_content_id: str = "") -> dict:
    """Replace old attachment ID with new ID throughout a media node tree.

    Also updates collection and strips internal attrs (localId, occurrenceKey).
    """
    new_node = dict(node)
    node_type = node.get("type", "")

    if node_type == "media":
        attrs = dict(node.get("attrs", {}))
        current_id = _parse_plain_attachment_id(attrs.get("id", ""))
        if current_id == old_id:
            # Replace with the resolved media file UUID from target
            attrs["id"] = new_id
        new_node["attrs"] = attrs

    elif node_type == "mediaSingle":
        pass  # keep all attrs unchanged

    if "content" in node:
        new_node["content"] = [
            _update_media_ids(child, old_id, new_id, target_content_id)
            if isinstance(child, dict)
            else child
            for child in node["content"]
        ]

    return new_node


class JiraClient:
    """Thin wrapper around Jira Cloud REST API."""

    def __init__(self, url: str, email: str, api_token: str):
        self.base_url = url.rstrip("/")
        self._auth_header = self._build_auth_header(email, api_token)
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": self._auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    @staticmethod
    def _build_auth_header(email: str, api_token: str) -> str:
        credentials = f"{email}:{api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def test_connection(self) -> bool:
        """Verify the connection works by calling /myself."""
        resp = self._session.get(f"{self.base_url}/rest/api/3/myself")
        return resp.ok

    def get_issue_comments(self, issue_key: str) -> list[dict]:
        """Return all comments on an issue.

        Each comment dict:
          {id, author_display, author_email, body (plain text), body_adf (raw ADF),
           created, updated}
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment"
        comments = []

        start_at = 0
        max_results = 100
        while True:
            resp = self._session.get(
                url, params={"startAt": start_at, "maxResults": max_results}
            )
            resp.raise_for_status()
            data = resp.json()

            for c in data.get("comments", []):
                author = c.get("author", {})
                body_adf = c.get("body", {})
                comments.append({
                    "id": c["id"],
                    "author_display": author.get("displayName", "Unknown"),
                    "author_email": author.get("emailAddress", ""),
                    "body": extract_text_from_adf(body_adf).strip(),
                    "body_adf": body_adf,
                    "created": c.get("created", ""),
                    "updated": c.get("updated", ""),
                })

            total = data.get("total", 0)
            if total <= start_at + max_results:
                break
            start_at += max_results

        return comments

    def add_comment(self, issue_key: str, body_adf: dict,
                    attachments: list[tuple[str, bytes]] | None = None):
        """Add a comment, optionally with attachments linked via multipart."""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment"
        if attachments:
            import json as _json

            resp = self._session.post(
                url,
                data={"body": _json.dumps(body_adf)},
                files=[("file", (f, d)) for f, d in attachments],
                headers={
                    "X-Atlassian-Token": "no-check",
                    "Accept": "application/json",
                },
            )
        else:
            resp = self._session.post(url, json={"body": body_adf})
        if not resp.ok:
            detail = resp.text[:500] if resp.text else "(no body)"
            raise Exception(f"{resp.status_code} {resp.reason}: {detail}")
        return resp.json()

    def update_comment(self, issue_key: str, comment_id: str, body_adf: dict):
        """Update an existing comment's body."""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment/{comment_id}"
        payload = {"body": body_adf}
        resp = self._session.put(url, json=payload)
        if not resp.ok:
            detail = resp.text[:500] if resp.text else "(no body)"
            raise Exception(f"{resp.status_code} {resp.reason}: {detail}")
        return resp.json()

    def get_issue(self, issue_key: str) -> dict:
        """Return issue fields including description and summary.

        Returns dict: {id, key, summary, description (plain text), description_adf}
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        resp = self._session.get(url, params={"fields": "description,summary"})
        resp.raise_for_status()
        data = resp.json()
        fields = data.get("fields", {})
        description_adf = fields.get("description") or {}
        return {
            "id": data.get("id", ""),
            "key": data.get("key", issue_key),
            "summary": fields.get("summary", ""),
            "description": extract_text_from_adf(description_adf).strip(),
            "description_adf": description_adf,
        }

    def update_issue_description(self, issue_key: str, body_adf: dict):
        """Update issue description with the given ADF body."""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        payload = {"fields": {"description": body_adf}}
        resp = self._session.put(url, json=payload)
        if not resp.ok:
            detail = resp.text[:500] if resp.text else "(no body)"
            raise Exception(f"{resp.status_code} {resp.reason}: {detail}")
        # 204 No Content on success — no JSON body to parse
        return resp.status_code

    def get_issue_attachments(self, issue_key: str) -> list[dict]:
        """Return all attachments on an issue.

        Each dict: {id, filename, mimeType, size}
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        resp = self._session.get(url, params={"fields": "attachment"})
        resp.raise_for_status()
        attachments = resp.json().get("fields", {}).get("attachment", [])
        return [
            {
                "id": a["id"],
                "filename": a["filename"],
                "mimeType": a.get("mimeType", ""),
                "size": a.get("size", 0),
            }
            for a in attachments
        ]

    def download_attachment(self, attachment_id: str) -> tuple[str, bytes]:
        """Download an attachment by ID. Returns (filename, binary_data)."""
        url = f"{self.base_url}/rest/api/3/attachment/content/{attachment_id}"
        resp = self._session.get(url)
        resp.raise_for_status()
        disp = resp.headers.get("Content-Disposition", "")
        filename = "attachment"
        if "filename=" in disp:
            import re

            m = re.search(r'filename="?([^";\s]+)', disp)
            if m:
                filename = m.group(1)
        return filename, resp.content

    def upload_attachment(self, issue_key: str, filename: str, data: bytes) -> dict:
        """Upload a file as an attachment to an issue.

        Returns the attachment metadata dict from Jira (includes 'id').
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/attachments"
        resp = self._session.post(
            url,
            files={"file": (filename, data)},
            headers={
                "X-Atlassian-Token": "no-check",
                "Content-Type": None,
            },
        )
        resp.raise_for_status()
        return resp.json()[0]

    def resolve_media_uuid(self, attachment_id: str) -> str:
        """Resolve REST API attachment ID to the media file UUID used in ADF.

        Follows the 303 redirect from GET /attachment/content/{id} to extract
        the UUID from the api.media.atlassian.com Location header.
        """
        import re

        url = f"{self.base_url}/rest/api/3/attachment/content/{attachment_id}"
        resp = self._session.head(url, allow_redirects=False)
        if resp.status_code == 303:
            location = resp.headers.get("Location", "")
            m = re.search(r"/file/([a-f0-9-]+)/", location)
            if m:
                return m.group(1)
        # Fallback: try GET without following redirect, in case HEAD isn't supported
        resp2 = self._session.get(url, allow_redirects=False)
        if resp2.status_code == 303:
            location = resp2.headers.get("Location", "")
            m = re.search(r"/file/([a-f0-9-]+)/", location)
            if m:
                return m.group(1)
        return ""
