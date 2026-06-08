# 一键发布项目到 GitHub — 开发文档 v2

## 1. 背景

用户希望通过一个预先填写好的配置文件，实现"一键发布项目到 GitHub"。

使用时用户不需要临时判断项目状态、不需要手动输入多条 Git/GitHub 命令，只需要执行一个发布命令。工具根据配置自动完成以下两种场景之一：

1. 将一个还没有 Git 管理的新项目初始化并推送到 GitHub。
2. 将一个已经由 Git 管理的项目提交并推送到 GitHub。

**使用场景**：个人单用户，几乎只做 push，极少 pull，仓库通常为 private。

## 2. 目标

核心目标：

- 用户提前写好配置文件。
- 发布时只执行一个命令。
- 自动识别项目是否已经是 Git 仓库。
- 自动创建或复用 GitHub 远程仓库。
- 自动完成 add、commit、branch、remote、push。
- 支持新项目首次发布到 GitHub。
- 支持已有 Git 项目继续 push 到 GitHub。
- 支持可选 commit message 输入。
- 出错时给出清晰提示，避免误操作。
- 网络异常时给出明确的网络排查提示。

## 3. 技术方案

- Python 3.10+
- 仅使用标准库（`argparse`、`subprocess`、`json`、`os`、`sys`、`pathlib`）
- 依赖外部工具：Git、GitHub CLI (`gh`)
- 配置文件格式：JSON

## 4. 使用方式

在项目根目录准备配置文件 `publish.config.json`，然后执行：

```bash
python publish.py
```

带提交信息：

```bash
python publish.py --commit "feat: initial publish"
```

## 5. 配置文件设计

配置文件名：`publish.config.json`

```json
{
  "projectPath": ".",
  "github": {
    "owner": "your-github-name",
    "repo": "your-repo-name",
    "visibility": "private",
    "description": "Project description",
    "homepage": "",
    "createIfMissing": true
  },
  "git": {
    "defaultBranch": "main",
    "remoteName": "origin",
    "defaultCommitMessage": "chore: publish project",
    "allowEmptyCommit": false,
    "pushTags": false
  },
  "publish": {
    "includeUntracked": true,
    "autoCommit": true,
    "forcePush": false,
    "openAfterPublish": false
  },
  "safety": {
    "requireCleanRemote": false,
    "confirmBeforeForcePush": true,
    "ignorePatterns": [
      ".env",
      "node_modules/",
      "__pycache__/",
      ".DS_Store",
      "publish.config.json"
    ]
  }
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `projectPath` | string | 是 | 要发布的项目路径，`.` 表示当前目录 |
| `github.owner` | string | 是 | GitHub 用户名或组织名 |
| `github.repo` | string | 是 | GitHub 仓库名 |
| `github.visibility` | string | 否 | `public` 或 `private`，默认 `private` |
| `github.description` | string | 否 | 仓库描述 |
| `github.homepage` | string | 否 | 仓库主页 |
| `github.createIfMissing` | boolean | 否 | 远程仓库不存在时是否自动创建，默认 true |
| `git.defaultBranch` | string | 否 | 默认分支名，默认 `main` |
| `git.remoteName` | string | 否 | 远程名，默认 `origin` |
| `git.defaultCommitMessage` | string | 否 | 默认提交信息 |
| `git.allowEmptyCommit` | boolean | 否 | 无变更时是否允许空提交，默认 false |
| `git.pushTags` | boolean | 否 | 是否推送 tags，默认 false |
| `publish.includeUntracked` | boolean | 否 | 是否添加未跟踪文件，默认 true |
| `publish.autoCommit` | boolean | 否 | 是否自动 commit，默认 true |
| `publish.forcePush` | boolean | 否 | 是否强制推送，默认 false |
| `publish.openAfterPublish` | boolean | 否 | 发布后是否打开 GitHub 页面，默认 false |
| `safety.requireCleanRemote` | boolean | 否 | 推送前是否检查远程分支冲突，默认 **false**（单人使用无需开启） |
| `safety.confirmBeforeForcePush` | boolean | 否 | force push 前是否要求确认，默认 true |
| `safety.ignorePatterns` | array | 否 | 自动追加到 `.gitignore` 的规则，默认包含 `publish.config.json` |

## 6. 命令行参数

| 参数 | 示例 | 说明 |
|---|---|---|
| `--config` | `--config publish.config.json` | 指定配置文件路径 |
| `--commit` | `--commit "feat: update"` | 本次提交信息 |
| `--dry-run` | `--dry-run` | 只展示将执行的步骤，不真正执行 |
| `--yes` | `--yes` | 自动确认非危险操作（force push 始终需要手动确认） |
| `--verbose` | `--verbose` | 输出详细日志 |

优先级：命令行参数 > 配置文件 > 程序默认值。

## 7. 主要流程

### 7.1 启动检查

1. 读取配置文件。
2. 校验必填字段（`projectPath`、`github.owner`、`github.repo`）。
3. 解析项目绝对路径。
4. 检查项目路径是否存在。
5. 检查 Git 是否可用（`git --version`）。
6. 检查 GitHub CLI 是否可用（`gh --version`）。
7. 检查 `gh auth status`，确认用户已登录。

**如果 GitHub CLI 未登录**，输出以下引导并退出：

```text
发布失败：GitHub CLI 未登录。
请按以下步骤操作：
  1. 在终端运行：gh auth login
  2. 按提示选择 GitHub.com → HTTPS → 浏览器登录
  3. 登录完成后，重新运行：python publish.py
```

### 7.2 判断项目 Git 状态

进入 `projectPath` 后执行 `git rev-parse --is-inside-work-tree`。

- 成功：已是 Git 仓库，继续。
- 失败：执行 `git init`，然后 `git branch -M {defaultBranch}`。

**注意**：对于已有 Git 项目，如果当前分支不是配置中的 `defaultBranch`，自动切换到配置分支（不存在则创建）。

### 7.3 处理 `.gitignore`

> **重要时序**：此步骤必须在 `git add` 之前完成，否则敏感文件可能被提交。

1. 检查项目根目录是否存在 `.gitignore`，不存在则创建。
2. 读取 `safety.ignorePatterns`，逐条检查是否已存在。
3. 已存在的规则不重复追加，缺失的追加到文件末尾。

### 7.4 创建或确认 GitHub 仓库

> **前提**：此步骤依赖 7.1 的登录检查已通过，`gh` 命令需要认证才能操作远程仓库。

检查仓库是否存在：`gh repo view {owner}/{repo}`

- 存在：继续。
- 不存在且 `createIfMissing` 为 true：执行 `gh repo create {owner}/{repo} --private --description "..."`。
- 不存在且 `createIfMissing` 为 false：停止并提示。

**网络异常处理**：如果 `gh repo view` 或 `gh repo create` 因网络问题失败（超时、连接拒绝、DNS 解析失败等），输出：

```text
发布失败：无法连接 GitHub，可能是网络问题。
请检查：
  1. 网络连接是否正常
  2. 是否需要代理（可尝试设置 https_proxy 环境变量）
  3. GitHub 服务状态：https://www.githubstatus.com
确认后重新运行发布命令。
```

### 7.5 设置远程仓库

检查本地 remote：`git remote get-url {remoteName}`

- 不存在：`git remote add {remoteName} https://github.com/{owner}/{repo}.git`
- 存在且 URL 一致：继续。
- 存在但 URL 不一致：**停止**，显示当前 URL 和目标 URL，不自动覆盖。

### 7.6 提交代码

如果 `publish.autoCommit` 为 true：

1. 根据 `includeUntracked` 决定 `git add .` 或 `git add -u`。
2. 执行 `git status --porcelain` 检查是否有变更。
3. 有变更：`git commit -m "{message}"`。
4. 无变更且 `allowEmptyCommit` 为 false：跳过 commit，输出"没有检测到新的本地变更，已跳过 commit。"。
5. 无变更且 `allowEmptyCommit` 为 true：`git commit --allow-empty -m "{message}"`。

### 7.7 推送到 GitHub

**推送前网络预检**：先执行 `git ls-remote {remoteName}` 测试网络连通性。如果失败，提前给出网络提示（同 7.4 的网络异常提示），避免 push 失败后才发现问题。

正常推送：`git push -u {remoteName} {defaultBranch}`（`-u` 用于首次推送时设置上游追踪分支）。

force push：`git push -u {remoteName} {defaultBranch} --force-with-lease`（禁止使用 `--force`）。如果 `confirmBeforeForcePush` 为 true，必须在终端要求用户输入 `y` 确认，除非提供 `--yes`。

如果 `pushTags` 为 true：`git push {remoteName} --tags`。

**push 失败时的网络判断**：检查 git 输出的 stderr，如果包含以下关键词则判定为网络问题：`timeout`、`could not resolve`、`connection refused`、`connection reset`、`SSL`、`unable to access`、`failed to connect`、`timed out`。输出：

```text
发布失败：推送时网络连接异常。
Git 原始错误：{stderr}
请检查：
  1. 网络连接是否正常，能否访问 github.com
  2. 是否需要配置代理（git config --global http.proxy ...）
  3. GitHub 服务状态：https://www.githubstatus.com
网络恢复后重新运行发布命令。
```

如果是非网络原因的 push 失败（如 non-fast-forward），输出：

```text
发布失败：推送被拒绝。
Git 原始错误：{stderr}
可能原因：远程仓库有本地没有的提交。
建议执行：git pull --rebase origin {branch}，然后重新发布。
```

### 7.8 完成后输出

成功：

```text
发布成功
仓库：https://github.com/{owner}/{repo}
分支：{branch}
提交：{commit_message}
```

无变更但推送成功：

```text
没有检测到新的本地变更，已跳过 commit。
推送完成。
仓库：https://github.com/{owner}/{repo}
```

## 8. 两种核心场景

### 场景 A：新项目首次发布

1. 读取配置 → 2. 检查环境 → 3. `git init` → 4. 设置分支 → 5. 处理 `.gitignore` → 6. 创建/确认 GitHub 仓库 → 7. 添加 remote → 8. `git add .` → 9. `git commit` → 10. `git push -u origin main` → 11. 输出地址

### 场景 B：已有 Git 项目推送

1. 读取配置 → 2. 检查环境 → 3. 处理 `.gitignore` → 4. 创建/确认 GitHub 仓库 → 5. 检查/设置 remote → 6. 必要时切换分支 → 7. add + commit → 8. push → 9. 输出地址

## 9. 错误处理汇总

| 错误 | 处理方式 |
|---|---|
| 配置文件不存在 | 输出路径，提示创建 |
| JSON 格式错误 | 输出解析错误信息 |
| 必填字段缺失 | 明确提示缺失字段名 |
| 项目路径不存在 | 停止，提示路径错误 |
| Git 不存在 | 停止，提示安装 Git |
| GitHub CLI 不存在 | 停止，提示安装 `gh` |
| GitHub CLI 未登录 | 停止，输出 3 步登录引导 |
| 远程仓库不存在且禁止创建 | 停止，提示打开 `createIfMissing` |
| remote URL 不一致 | 停止，显示当前 URL 和目标 URL |
| commit 无变更 | 根据 `allowEmptyCommit` 跳过或空提交 |
| push 失败（网络原因） | 输出网络排查 3 步指引 |
| push 失败（non-fast-forward） | 提示先 `git pull --rebase` |
| force push 未确认 | 停止，不执行强推 |
| `gh`/`git` 命令超时或连接失败 | 统一输出网络排查提示 |

## 10. 网络问题识别规则

工具在调用 `gh` 或 `git` 命令失败时，检查 stderr 中是否包含以下关键词来判断是否为网络问题：

```python
NETWORK_ERROR_KEYWORDS = [
    "timeout", "timed out",
    "could not resolve", "name or service not known",
    "connection refused", "connection reset",
    "failed to connect", "unable to access",
    "ssl", "certificate",
    "network is unreachable",
    "no route to host",
    "temporary failure",
    "errno 10060",  # Windows 连接超时
    "errno 10061",  # Windows 连接被拒绝
]
```

匹配到任意一个关键词，则归类为网络问题并输出网络排查提示。

## 11. 安全要求

1. 不自动覆盖已有 remote。
2. 不默认 force push。
3. force push 只能使用 `--force-with-lease`。
4. 默认创建 private 仓库。
5. 默认把 `.env` 和 `publish.config.json` 加入 `.gitignore`。
6. dry-run 模式不执行任何写操作。
7. 输出日志中不打印 token、密码、密钥。
8. 不自动删除用户文件。
9. 不自动执行 `git reset --hard` 或 `git clean -fd`。

## 12. dry-run 模式

只输出计划执行的动作，禁止所有写操作：

```text
[dry-run] 读取配置 publish.config.json
[dry-run] 项目路径 C:\demo\my-project
[dry-run] 检测到项目不是 Git 仓库，将执行 git init
[dry-run] 将创建 GitHub 仓库 your-name/my-project
[dry-run] 将添加 remote origin
[dry-run] 将提交：chore: publish project
[dry-run] 将推送到 origin/main
```

## 13. 文件结构

```text
project/
  publish.py              # 主程序（单文件）
  publish.config.json     # 配置文件
```

## 14. 主程序伪代码

```python
NETWORK_ERROR_KEYWORDS = ["timeout", "timed out", "could not resolve", ...]

def is_network_error(stderr: str) -> bool:
    lower = stderr.lower()
    return any(kw in lower for kw in NETWORK_ERROR_KEYWORDS)

def run_cmd(cmd, cwd, dry_run, verbose) -> Result:
    if dry_run:
        print(f"[dry-run] 将执行: {' '.join(cmd)}")
        return Result(success=True, dry_run=True)
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return Result(success=result.returncode == 0, stdout=..., stderr=...)

def main():
    args = parse_args()
    config = load_and_validate_config(args.config)
    project_path = resolve_project_path(config["projectPath"])
    
    # 环境检查
    check_git()
    check_gh()
    check_gh_auth()  # 未登录 → 输出3步引导并退出
    
    # Git 状态
    if not is_git_repo(project_path):
        git_init(project_path, config["git"]["defaultBranch"])
    else:
        ensure_branch(project_path, config["git"]["defaultBranch"])
    
    # .gitignore（必须在 git add 之前）
    ensure_gitignore(project_path, config["safety"]["ignorePatterns"])
    
    # GitHub 仓库（网络异常时给出排查提示）
    ensure_github_repo(config["github"])
    
    # Remote
    ensure_remote(project_path, config)
    
    # 推送前网络预检
    check_network_connectivity(remote_url)
    
    # Commit + Push
    commit_message = args.commit or config["git"]["defaultCommitMessage"]
    git_add_and_commit(project_path, config, commit_message)
    git_push(project_path, config)  # 失败时判断网络/非网络原因
    
    print_success(config)
```
