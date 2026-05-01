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

    def add_comment(self, issue_key: str, body: str):
        """Add a text comment to an issue (plain text wrapped in ADF)."""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment"
        payload = {"body": {
            "type": "doc",
            "version": 1,
            "content": [{
                "type": "paragraph",
                "content": [{"type": "text", "text": body}],
            }],
        }}
        resp = self._session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
