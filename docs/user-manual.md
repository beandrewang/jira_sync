# Jira Sync 用户手册

版本 0.1.0

## 目录

1. [概述](#1-概述)
2. [快速开始](#2-快速开始)
3. [安装说明](#3-安装说明)
4. [配置 Jira 连接](#4-配置-jira-连接)
5. [同步评论](#5-同步评论)
6. [命令参考](#6-命令参考)
7. [常见问题](#7-常见问题)
8. [附录：获取 Jira API Token](#8-附录获取-jira-api-token)

---

## 1. 概述

Jira Sync 是一个命令行工具，用于在两个 Jira Cloud 实例之间同步工单评论。典型场景：

- 你方在 Jira 中与客户协作一个工单
- 客户在另一个 Jira 实例中有对应的工单
- 你需要把你方工单中与客户相关的评论同步过去

工具自动处理：认证、评论获取、关键词筛选、去重、格式化和推送。

### 名词解释

| 术语 | 说明 |
|------|------|
| Source Jira | 评论的来源 Jira 实例 |
| Target Jira | 评论的目标 Jira 实例 |
| Issue Key | Jira 工单号，格式如 `PROJ-123` |
| API Token | Jira Cloud 的 API 认证令牌 |
| ADF | Atlassian Document Format，Jira 存储文本的格式 |
| Dry-run | 预览模式，只展示结果不实际推送 |

---

## 2. 快速开始

### 2.1 安装

```bash
pip install jira_sync-0.1.0-py3-none-any.whl
```

### 2.2 配置两个连接

```bash
# 配置我方 Jira
jira-sync configure \
    --name my \
    --url https://my-company.atlassian.net \
    --email alice@my-company.com \
    --api-token xxxxxxxxxxxxxxxx

# 配置客户方 Jira
jira-sync configure \
    --name customer \
    --url https://customer.atlassian.net \
    --email alice@customer.com \
    --api-token yyyyyyyyyyyyyyyy
```

### 2.3 同步评论

```bash
jira-sync sync
```

按提示选择连接、输入工单号和关键词即可。

---

## 3. 安装说明

### 3.1 环境要求

- Python 3.10 或更高版本
- 操作系统：Windows / macOS / Linux

### 3.2 通过 wheel 包安装（推荐）

从分发者获取 `.whl` 文件后：

```bash
pip install jira_sync-0.1.0-py3-none-any.whl
```

验证安装：

```bash
jira-sync --help
```

如看到帮助信息，说明安装成功。

### 3.3 直接运行源码

如不想安装，也可以直接运行源码：

```bash
# 方式一
python jira-sync.py --help

# 方式二
python -m jira_sync --help
```

### 3.4 升级

重新安装新版本的 wheel 即可覆盖旧版本：

```bash
pip install --upgrade jira_sync-新版本-py3-none-any.whl
```

---

## 4. 配置 Jira 连接

### 4.1 命令格式

```bash
jira-sync configure --name <名称> --url <URL> --email <邮箱> --api-token <Token>
```

### 4.2 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `--name` | 是 | 连接名称，自定义标识。如 `my`、`customer`、`internal` |
| `--url` | 是 | Jira 实例的基础 URL。如 `https://my-company.atlassian.net` |
| `--email` | 是 | 登录 Jira 的邮箱地址 |
| `--api-token` | 是 | Jira Cloud API Token，见附录获取方式 |

### 4.3 配置示例

单账号场景（用同一个邮箱登录两边 Jira）：

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

多账号场景（两边用不同账号）：

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

> 注意：Jira API Token 与账号绑定，不是与 Jira 实例绑定。如果两边用同一个邮箱，可以用同一个 Token。

### 4.4 连接验证

配置时工具会自动测试连接：

- 调用 Jira REST API `/rest/api/3/myself` 验证认证信息
- 成功显示 `OK`（绿色），失败显示 `FAILED`（红色）
- 验证通过后自动保存配置

### 4.5 配置文件位置

连接信息保存在 `~/.jira-sync/config.json`。示例：

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

> ⚠️ API Token 以明文存储。请确保此文件的访问权限仅限你自己。

### 4.6 管理连接

查看所有已保存的连接：

```bash
jira-sync list
```

输出示例：

```
Saved connections:
  • my       (https://my-company.atlassian.net / alice@my-company.com)
  • customer (https://customer.atlassian.net / alice@customer.com)
```

删除连接：

```bash
jira-sync delete --name customer
```

---

## 5. 同步评论

### 5.1 基本流程

```bash
jira-sync sync
```

「jira-sync sync」是完全交互式的，按以下步骤执行：

#### 步骤 1：选择 Source Jira

```
Select SOURCE Jira (where comments come from):
  1. my       (https://my-company.atlassian.net)
  2. customer (https://customer.atlassian.net)
Enter number:
```

输入数字选择评论来源的 Jira 连接。

#### 步骤 2：选择 Target Jira

```
Select TARGET Jira (where comments go to):
  1. my       (https://my-company.atlassian.net)
  2. customer (https://customer.atlassian.net)
Enter number:
```

输入数字选择评论目标的 Jira 连接。

#### 步骤 3：输入工单号

```
Source issue key: SUP-456
Target issue key: CUST-123
```

分别输入来源工单和目标工单的编号。

#### 步骤 4：输入关键词过滤

```
Filter keywords (comma-separated, leave empty for all): bug, error, urgent
```

输入关键词，多个词用逗号分隔。留空则同步所有评论。

#### 步骤 5：确认

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

确认无误后输入 `y` 继续。

#### 步骤 6：执行结果

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

### 5.2 Dry-run 模式

先预览结果，不实际推送：

```bash
jira-sync sync --dry-run
```

Dry-run 会完整执行到「确认」步骤，并显示有多少条评论会被推送、但不会实际调用 Jira API 写入。建议每次同步前先 dry-run 确认内容无误。

### 5.3 关键词过滤规则

- **大小写不敏感**：`Bug` 和 `bug` 效果相同
- **多关键词 OR 逻辑**：`bug, error` 匹配包含 `bug` **或** `error` 的评论
- **部分匹配**：`pay` 匹配包含 `payment`、`payroll`、`repay` 的评论
- **空关键词**：同步所有评论

### 5.4 同步格式

同步到目标 Jira 的评论会自动添加来源标记：

```
[Synced from my Jira]
Author: Alice Wang
Date: 2024-06-15T10:30:00.000+0800

<原始评论内容>
```

### 5.5 去重机制

如果多次运行同步，不会产生重复评论。去重逻辑：

1. 从目标工单获取已有评论的纯文本
2. 对每个待同步的评论计算内容指纹（前 100 字符的 SHA256 前缀）
3. 指纹匹配则跳过

```
⏭  Skipping (duplicate): comment #12345 by Alice Wang
```

### 5.6 完整运行示例

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

## 6. 命令参考

### 6.1 全局

```bash
jira-sync --help
```

显示所有可用命令。

### 6.2 configure

配置 Jira 连接。

```bash
jira-sync configure --name <名称> --url <URL> --email <邮箱> --api-token <Token>
```

选项：

| 选项 | 说明 |
|------|------|
| `--name` | 连接名称（必填） |
| `--url` | Jira 基础 URL（必填） |
| `--email` | 登录邮箱（必填） |
| `--api-token` | API Token（必填） |

### 6.3 sync

执行同步。

```bash
jira-sync sync [--dry-run]
```

选项：

| 选项 | 说明 |
|------|------|
| `--dry-run` | 预览模式，不实际推送 |

### 6.4 list

列出所有已保存的连接。

```bash
jira-sync list
```

### 6.5 delete

删除已保存的连接。

```bash
jira-sync delete --name <名称>
```

选项：

| 选项 | 说明 |
|------|------|
| `--name` | 要删除的连接名称（必填） |

---

## 7. 常见问题

### 7.1 连接测试失败

```
Testing connection 'my' ... FAILED
```

可能原因：

1. **URL 错误**：确认是 Jira Cloud URL，格式如 `https://xxx.atlassian.net`
2. **API Token 错误**：重新生成 Token，确认复制时没有多余空格
3. **邮箱错误**：确认登录邮箱正确
4. **网络问题**：检查是否能访问 Jira URL（公司代理或 VPN）

### 7.2 获取评论失败

```
Fetching comments from PROJ-123 ...
requests.exceptions.HTTPError: 404 Client Error
```

- 确认工单号正确（大小写敏感，如 `PROJ-123` 不是 `proj-123`）
- 确认该账号有访问工单的权限

### 7.3 推送评论失败

```
✗ Failed to comment #12345: 403 Client Error
```

- 确认目标 Jira 账号对目标工单有 `添加评论` 权限
- 确认目标工单没有被关闭或限制编辑

### 7.4 重复评论

如果去重失效，可能原因：

- 目标工单的评论被人为修改过（指纹变了，视为新评论）
- 多次同步时关键词不同（上次用 `bug`，这次用 `error`，同步了不同评论）

这是预期行为。手动清理目标工单的多余评论即可。

### 7.5 配置信息丢失

配置文件位于 `~/.jira-sync/config.json`。如需迁移到另一台机器：

1. 在旧机器查看配置：`jira-sync list`
2. 复制 `~/.jira-sync/config.json` 到新机器同目录
3. 验证：`jira-sync list`

### 7.6 代理配置

如果公司网络需要代理，通过环境变量配置：

```bash
# HTTP 代理
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080

# Windows PowerShell
$env:HTTPS_PROXY="http://proxy.company.com:8080"

# 然后运行
jira-sync sync
```

---

## 8. 附录：获取 Jira API Token

Jira Cloud 使用 API Token 进行认证，不是用密码。

### 步骤

1. 登录 https://id.atlassian.com/manage/api-tokens
2. 点击 **Create API token**
3. 输入名称（如 `jira-sync-tool`）
4. 点击 **Create**
5. **复制 Token**（关闭弹窗后无法再次查看）

> ⚠️ Token 只在创建时显示一次。如丢失，删除后重新创建。

### 安全建议

- Token 相当于你的密码，不要分享给他人
- 不要将 Token 提交到 Git 仓库
- 定期轮换 Token（如每 90 天）
- 为不同工具创建不同的 Token，方便单独撤销
