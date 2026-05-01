# Jira Sync User Manual

Version 0.1.0

## Table of Contents

1. [Overview](#1-overview)
2. [Quick Start](#2-quick-start)
3. [Installation](#3-installation)
4. [Configuring Jira Connections](#4-configuring-jira-connections)
5. [Syncing Comments](#5-syncing-comments)
6. [Command Reference](#6-command-reference)
7. [FAQ](#7-faq)
8. [Appendix: Getting a Jira API Token](#8-appendix-getting-a-jira-api-token)

---

## 1. Overview

Jira Sync is a CLI tool for syncing ticket comments between two Jira Cloud instances. Typical use case:

- You collaborate with a customer on a ticket in your Jira
- The customer has a corresponding ticket in their Jira instance
- You need to sync relevant comments from your ticket to the customer's ticket

The tool handles authentication, comment fetching, keyword filtering, deduplication, formatting, and posting.

### Glossary

| Term | Description |
|------|-------------|
| Source Jira | The Jira instance where comments originate |
| Target Jira | The Jira instance where comments are synced to |
| Issue Key | Jira ticket ID, e.g. `PROJ-123` |
| API Token | Jira Cloud API authentication token |
| ADF | Atlassian Document Format, Jira's internal text format |
| Dry-run | Preview mode — shows results without posting |

---

## 2. Quick Start

### 2.1 Install

```bash
pip install jira_sync-0.1.0-py3-none-any.whl
```

### 2.2 Configure two connections

```bash
# Configure your Jira
jira-sync configure \
    --name my \
    --url https://my-company.atlassian.net \
    --email alice@my-company.com \
    --api-token xxxxxxxxxxxxxxxx

# Configure customer's Jira
jira-sync configure \
    --name customer \
    --url https://customer.atlassian.net \
    --email alice@customer.com \
    --api-token yyyyyyyyyyyyyyyy
```

### 2.3 Sync comments

```bash
jira-sync sync
```

Follow the prompts to select connections, enter issue keys, and provide keywords.

---

## 3. Installation

### 3.1 Requirements

- Python 3.10 or later
- OS: Windows / macOS / Linux

### 3.2 Install via wheel (recommended)

Obtain the `.whl` file from the distributor, then:

```bash
pip install jira_sync-0.1.0-py3-none-any.whl
```

Verify the installation:

```bash
jira-sync --help
```

### 3.3 Run from source

You can also run the source directly without installing:

```bash
# Option 1
python jira-sync.py --help

# Option 2
python -m jira_sync --help
```

### 3.4 Upgrading

Install the new wheel over the old one:

```bash
pip install --upgrade jira_sync-<version>-py3-none-any.whl
```

---

## 4. Configuring Jira Connections

### 4.1 Command format

```bash
jira-sync configure --name <name> --url <URL> --email <email> --api-token <token>
```

### 4.2 Options

| Option | Required | Description |
|--------|----------|-------------|
| `--name` | Yes | Connection label, e.g. `my`, `customer`, `internal` |
| `--url` | Yes | Jira base URL, e.g. `https://my-company.atlassian.net` |
| `--email` | Yes | Jira account email |
| `--api-token` | Yes | Jira Cloud API token (see appendix) |

### 4.3 Examples

Single account (same email across both Jira instances):

```bash
jira-sync configure --name my \
    --url https://my-company.atlassian.net \
    --email me@gmail.com \
    --api-token xxxxx

jira-sync configure --name customer \
    --url https://customer.atlassian.net \
    --email me@gmail.com \
    --api-token xxxxx
```

Different accounts:

```bash
jira-sync configure --name my \
    --url https://my-company.atlassian.net \
    --email alice@my-company.com \
    --api-token xxxxx

jira-sync configure --name customer \
    --url https://customer.atlassian.net \
    --email bob@customer.com \
    --api-token yyyyy
```

> Note: API tokens are tied to accounts, not Jira instances. If you use the same email, you can use the same token.

### 4.4 Connection verification

On configure, the tool automatically tests the connection:

- Calls `GET /rest/api/3/myself` to verify credentials
- Shows `OK` (green) on success, `FAILED` (red) on failure
- Saves the config only if the test passes

### 4.5 Config file location

Connection profiles are stored in `~/.jira-sync/config.json`:

```json
{
  "connections": {
    "my": {
      "url": "https://my-company.atlassian.net",
      "email": "alice@my-company.com",
      "api_token": "xxxxxxxxxxxxxxxx"
    },
    "customer": {
      "url": "https://customer.atlassian.net",
      "email": "alice@customer.com",
      "api_token": "yyyyyyyyyyyyyyyy"
    }
  }
}
```

> ⚠️ API tokens are stored in plain text. Restrict access to this file.

### 4.6 Managing connections

List all saved connections:

```bash
jira-sync list
```

Example output:

```
Saved connections:
  • my       (https://my-company.atlassian.net / alice@my-company.com)
  • customer (https://customer.atlassian.net / alice@customer.com)
```

Delete a connection:

```bash
jira-sync delete --name customer
```

---

## 5. Syncing Comments

### 5.1 Basic workflow

```bash
jira-sync sync
```

The `sync` command is fully interactive. Here's the step-by-step flow:

#### Step 1: Select Source Jira

```
Select SOURCE Jira (where comments come from):
  1. my       (https://my-company.atlassian.net)
  2. customer (https://customer.atlassian.net)
Enter number:
```

Pick the Jira connection that has the comments you want to sync.

#### Step 2: Select Target Jira

```
Select TARGET Jira (where comments go to):
  1. my       (https://my-company.atlassian.net)
  2. customer (https://customer.atlassian.net)
Enter number:
```

Pick the Jira connection where comments should be posted.

#### Step 3: Enter issue keys

```
Source issue key: SUP-456
Target issue key: CUST-123
```

Enter the source and target ticket IDs.

#### Step 4: Enter filter keywords

```
Filter keywords (comma-separated, leave empty for all): bug, error, urgent
```

Enter keywords separated by commas. Leave empty to sync all comments.

#### Step 5: Confirm

```
==================================================
Sync Plan:
  Source:      my       →  SUP-456
  Target:      customer →  CUST-123
  Keywords:    bug, error, urgent
  Mode:        Dry run
==================================================
Proceed?
```

Review the plan and type `y` to continue.

#### Step 6: Results

```
Fetching comments from SUP-456 ...
  → 12 total comments
  → 4 comments match keyword filter
Fetching existing comments from CUST-123 ...
  → 3 existing comments

Comments to sync (3):
  1. [Alice Wang] We found a bug in the login flow when the session expires...
  2. [Bob Zhang] There's an error in the payment gateway timeout handling...
  3. [Alice Wang] This is urgent for the release next week...

Syncing 3 comments to CUST-123 ...
  ✓ Synced comment #12345
  ✓ Synced comment #12348
  ✓ Synced comment #12352

Done! 3/3 comments synced.
```

### 5.2 Dry-run mode

Preview results without posting:

```bash
jira-sync sync --dry-run
```

Dry-run executes the full flow up to confirmation and shows which comments would be synced, but never writes to the target Jira. Always dry-run before a real sync.

### 5.3 Keyword filter rules

- **Case insensitive**: `Bug` and `bug` behave the same
- **Multi-keyword OR logic**: `bug, error` matches comments containing **either** `bug` **or** `error`
- **Partial match**: `pay` matches `payment`, `payroll`, `repay`, etc.
- **Empty keywords**: Syncs all comments

### 5.4 Sync format

Comments posted to the target Jira include a source attribution header:

```
[Synced from my Jira]
Author: Alice Wang
Date: 2024-06-15T10:30:00.000+0800

<original comment body>
```

### 5.5 Deduplication

Running sync multiple times will not create duplicate comments. The dedup logic:

1. Fetch existing comments from the target ticket
2. Compute a fingerprint (first 100 chars SHA256 prefix) for each pending comment
3. Skip if a matching fingerprint already exists

```
⏭  Skipping (duplicate): comment #12345 by Alice Wang
```

### 5.6 Full example

```bash
$ jira-sync sync --dry-run

Select SOURCE Jira:
  1. my
  2. customer
Enter number: 1

Select TARGET Jira:
  1. my
  2. customer
Enter number: 2

Source issue key: SUP-456
Target issue key: CUST-123
Filter keywords (comma-separated, leave empty for all): bug, error

==================================================
Sync Plan:
  Source:      my       →  SUP-456
  Target:      customer →  CUST-123
  Keywords:    bug, error
  Mode:        Dry run
==================================================
Proceed? [y/N]: y

Fetching comments from SUP-456 ...
  → 12 total comments
  → 3 comments match keyword filter
Fetching existing comments from CUST-123 ...
  → 2 existing comments
  ⏭  Skipping (duplicate): comment #12345 by Alice Wang

Comments to sync (2):
  1. [Bob Zhang] There's an error in the payment gateway...
  2. [Alice Wang] Bug fix for session timeout...

[Dry run] No comments were posted.
```

---

## 6. Command Reference

### 6.1 Global

```bash
jira-sync --help
```

Show all available commands.

### 6.2 configure

Save a Jira connection profile.

```bash
jira-sync configure --name <name> --url <URL> --email <email> --api-token <token>
```

| Option | Description |
|--------|-------------|
| `--name` | Connection name (required) |
| `--url` | Jira base URL (required) |
| `--email` | Account email (required) |
| `--api-token` | API token (required) |

### 6.3 sync

Execute sync.

```bash
jira-sync sync [--dry-run]
```

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview only — no data is written |

### 6.4 list

List all saved connections.

```bash
jira-sync list
```

### 6.5 delete

Delete a saved connection.

```bash
jira-sync delete --name <name>
```

| Option | Description |
|--------|-------------|
| `--name` | Connection name to delete (required) |

---

## 7. FAQ

### 7.1 Connection test failed

```
Testing connection 'my' ... FAILED
```

Possible causes:

1. **Wrong URL**: Confirm it's a Jira Cloud URL like `https://xxx.atlassian.net`
2. **Invalid API token**: Regenerate the token, ensure no extra spaces when copying
3. **Wrong email**: Double-check the login email
4. **Network issue**: Check if you can reach the Jira URL (corporate proxy / VPN)

### 7.2 Failed to fetch comments

```
Fetching comments from PROJ-123 ...
requests.exceptions.HTTPError: 404 Client Error
```

- Verify the issue key is correct (case-sensitive: `PROJ-123`, not `proj-123`)
- Confirm the account has permission to view the ticket

### 7.3 Failed to post comments

```
✗ Failed to comment #12345: 403 Client Error
```

- Confirm the target account has "Add Comment" permission on the target ticket
- Check if the target ticket is closed or restricted

### 7.4 Duplicate comments

If dedup fails to catch a duplicate, possible reasons:

- The target comment was manually edited (fingerprint changed, treated as new)
- Different sync sessions used different keywords (e.g., `bug` in one run, `error` in another)

This is expected behavior. Clean up extra comments manually in the target Jira.

### 7.5 Lost configuration

Config file location: `~/.jira-sync/config.json`. To migrate:

1. Check saved connections: `jira-sync list`
2. Copy `~/.jira-sync/config.json` to the new machine
3. Verify: `jira-sync list`

### 7.6 Proxy configuration

Set environment variables if behind a corporate proxy:

```bash
# HTTP proxy
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080

# Windows PowerShell
$env:HTTPS_PROXY="http://proxy.company.com:8080"

# Then run
jira-sync sync
```

---

## 8. Appendix: Getting a Jira API Token

Jira Cloud uses API tokens instead of passwords for programmatic access.

### Steps

1. Log in at https://id.atlassian.com/manage/api-tokens
2. Click **Create API token**
3. Enter a label (e.g., `jira-sync-tool`)
4. Click **Create**
5. **Copy the token** (it's only shown once)

> ⚠️ If you lose the token, delete it and create a new one.

### Security tips

- Treat API tokens like passwords — never share them
- Do **not** commit tokens to Git repositories
- Rotate tokens periodically (e.g., every 90 days)
- Create separate tokens for different tools for independent revocation
