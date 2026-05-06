# Jira Sync

跨 Jira Cloud 实例的同步工具。支持在两个 Jira 项目之间同步工单描述和评论（可关键词筛选）。

纯 Python，全平台可用（Windows / macOS / Linux）。

## 安装

### 方式一：wheel 包安装（推荐）

```bash
pip install jira_sync-0.1.0-py3-none-any.whl
```

安装后直接使用 `jira-sync` 命令：

```bash
jira-sync --help
```

### 方式二：源码运行

无需安装，直接执行入口脚本：

```bash
python jira-sync.py --help
```

或：

```bash
python -m jira_sync --help
```

## 使用指南

### 1. 配置 Jira 连接

需要配置两个连接：**我方 Jira** 和 **客户方 Jira**。

```bash
# 配置我方 Jira
jira-sync configure \
    --name my \
    --url https://my-company.atlassian.net \
    --email your@email.com \
    --api-token YOUR_API_TOKEN

# 配置客户方 Jira
jira-sync configure \
    --name customer \
    --url https://customer.atlassian.net \
    --email your@email.com \
    --api-token YOUR_API_TOKEN
```

配置时会自动测试连接有效性。连接信息保存在 `~/.jira-sync/config.json`。

| 参数 | 说明 |
|------|------|
| `--name` | 连接名称，如 `my` / `customer` |
| `--url` | Jira 基础 URL，如 `https://xxx.atlassian.net` |
| `--email` | Jira 账号邮箱 |
| `--api-token` | [Jira API Token](https://id.atlassian.com/manage/api-tokens) |

### 2. 同步评论和描述

```bash
# 交互式同步（默认同步评论）
jira-sync sync

# 只同步描述
jira-sync sync --item description

# 评论和描述都同步
jira-sync sync --item both

# 先预览，不实际推送
jira-sync sync --item both --dry-run
```

同步流程：

1. 选择 **Source Jira**（数据来源）
2. 选择 **Target Jira**（数据目标）
3. 输入 **Source Issue Key**（如 `PROJ-123`）
4. 输入 **Target Issue Key**（如 `CUST-456`）
5. 选择同步内容（评论 / 描述 / 两者都同步）
6. 如果同步评论，输入**关键词**（逗号分隔，留空同步全部）
7. 确认后执行

### 其他命令

```bash
# 查看已保存的连接
jira-sync list

# 删除连接
jira-sync delete --name <名称>
```

## 关键词过滤

- 大小写不敏感
- 多个关键词用逗号分隔，任一匹配即可
- 示例：`login, payment, urgent` 匹配包含任一关键词的评论

## 功能特性

- **纯 Python，跨平台**：wheel 包 `py3-none-any`，无需编译，全平台可用
- **零额外依赖**（分发时）：pip 自动安装 `click` + `requests`
- **Jira Cloud REST API v3**：使用 Basic Auth + API Token
- **ADF 文本提取**：正确解析 Atlassian Document Format 中的纯文本
- **评论 + 描述同步**：可只同步评论、只同步描述，或两者都同步
- **自动去重**：基于内容指纹，避免重复推送
- **Dry-run 模式**：先预览再执行
- **来源标记**：同步的内容自动标注来源 Jira 名称、原始作者和时间

## 项目结构

```
jira_sync/
├── pyproject.toml          # 打包配置
├── jira-sync.py            # 源码入口
└── jira_sync/
    ├── __init__.py
    ├── __main__.py          # python -m 支持
    ├── config.py            # 连接配置管理 (~/.jira-sync/config.json)
    ├── client.py            # Jira REST API 客户端
    ├── syncer.py            # 同步核心逻辑 (评论+描述, 过滤/去重/格式化)
    └── sync.py              # CLI 命令定义 (click)
```

## 构建分发

```bash
# 安装构建工具
pip install build

# 构建 wheel 和源码包
python -m build

# 生成文件在 dist/ 目录
# dist/jira_sync-0.1.0-py3-none-any.whl
# dist/jira_sync-0.1.0.tar.gz
```
