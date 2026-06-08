# 一键发布项目到 GitHub 开发文档

## 1. 背景

用户希望通过一个预先填写好的配置文件，实现“一键发布项目到 GitHub”。

使用时用户不需要临时判断项目状态、不需要手动输入多条 Git/GitHub 命令，只需要执行一个发布命令。工具根据配置自动完成以下两种场景之一：

1. 将一个还没有 Git 管理的新项目初始化并推送到 GitHub。
2. 将一个已经由 Git 管理的项目提交并推送到 GitHub。

对于已经 Git 管理的项目，工具允许用户在发布时填写或传入 commit message；如果用户不填写，则使用配置文件里的默认提交信息。

## 2. 目标

开发一个本地命令行工具，支持读取配置文件并一键完成项目发布。

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

## 3. 推荐技术方案

优先使用 Python 开发命令行工具。

理由：

- 适合做本地自动化脚本。
- 跨平台能力较好。
- 读写配置文件方便。
- 调用 Git 和 GitHub CLI 简单。
- 用户学习和修改成本低。

依赖建议：

- Python 3.10+
- Git
- GitHub CLI `gh`
- Python 标准库优先，不强制引入第三方库

如需更友好的命令行参数，可选用：

- `argparse`，Python 标准库

配置文件格式建议使用 JSON 或 YAML。为了减少依赖，默认使用 JSON。

## 4. 使用方式

用户在项目根目录准备配置文件：

```text
publish.config.json
```

然后执行：

```bash
python publish.py
```

或者带提交信息：

```bash
python publish.py --commit "feat: initial publish"
```

工具完成后输出 GitHub 仓库地址。

## 5. 配置文件设计

配置文件名：

```text
publish.config.json
```

示例：

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
    "requireCleanRemote": true,
    "confirmBeforeForcePush": true,
    "ignorePatterns": [
      ".env",
      "node_modules/",
      "__pycache__/",
      ".DS_Store"
    ]
  }
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
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
| `safety.requireCleanRemote` | boolean | 否 | 推送前是否检查远程分支冲突，默认 true |
| `safety.confirmBeforeForcePush` | boolean | 否 | force push 前是否要求确认，默认 true |
| `safety.ignorePatterns` | array | 否 | 自动追加到 `.gitignore` 的规则 |

## 6. 命令行参数设计

基础命令：

```bash
python publish.py
```

参数：

| 参数 | 示例 | 说明 |
| --- | --- | --- |
| `--config` | `--config publish.config.json` | 指定配置文件路径 |
| `--commit` | `--commit "feat: update"` | 本次提交信息 |
| `--dry-run` | `--dry-run` | 只展示将执行的步骤，不真正执行 |
| `--yes` | `--yes` | 自动确认非危险操作 |
| `--verbose` | `--verbose` | 输出详细日志 |

优先级：

1. 命令行参数优先。
2. 配置文件次之。
3. 程序默认值最后。

例如 commit message 的取值顺序：

1. `--commit` 传入的内容。
2. `git.defaultCommitMessage`。
3. 如果两者都没有，则使用 `chore: publish project`。

## 7. 主要流程

### 7.1 启动检查

工具启动后执行：

1. 读取配置文件。
2. 校验必填字段。
3. 解析项目绝对路径。
4. 检查项目路径是否存在。
5. 检查 Git 是否可用。
6. 检查 GitHub CLI `gh` 是否可用。
7. 检查 `gh auth status`，确认用户已经登录 GitHub。

如果 GitHub CLI 未登录，提示用户先执行：

```bash
gh auth login
```

### 7.2 判断项目 Git 状态

进入 `projectPath` 后执行：

```bash
git rev-parse --is-inside-work-tree
```

如果成功，说明项目已被 Git 管理。

如果失败，说明这是新项目，需要执行：

```bash
git init
```

然后设置默认分支：

```bash
git branch -M main
```

分支名使用配置里的 `git.defaultBranch`。

### 7.3 处理 `.gitignore`

如果配置里存在 `safety.ignorePatterns`：

1. 检查项目根目录是否存在 `.gitignore`。
2. 不存在则创建。
3. 存在则追加缺失的忽略规则。
4. 已存在的规则不重复追加。

默认至少建议保护：

```text
.env
node_modules/
__pycache__/
.DS_Store
```

### 7.4 创建或确认 GitHub 仓库

目标仓库地址：

```text
https://github.com/{owner}/{repo}
```

先检查仓库是否存在：

```bash
gh repo view owner/repo
```

如果存在：

- 继续发布。

如果不存在：

- 如果 `github.createIfMissing` 为 true，执行创建：

```bash
gh repo create owner/repo --private --description "Project description"
```

或 public：

```bash
gh repo create owner/repo --public --description "Project description"
```

- 如果 `github.createIfMissing` 为 false，停止并提示用户远程仓库不存在。

### 7.5 设置远程仓库

检查本地 remote：

```bash
git remote get-url origin
```

如果不存在 remote：

```bash
git remote add origin https://github.com/owner/repo.git
```

如果 remote 已存在：

- 如果 URL 与配置目标一致，继续。
- 如果 URL 不一致，停止并提示用户。
- 不自动覆盖已有 remote，除非后续新增配置项 `overwriteRemote: true`。

### 7.6 提交代码

如果 `publish.autoCommit` 为 true：

添加文件：

```bash
git add .
```

如果 `publish.includeUntracked` 为 false，则只添加已跟踪文件的修改：

```bash
git add -u
```

检查是否有可提交变更：

```bash
git status --porcelain
```

如果有变更：

```bash
git commit -m "commit message"
```

如果无变更：

- `git.allowEmptyCommit` 为 false：跳过 commit。
- `git.allowEmptyCommit` 为 true：执行空提交：

```bash
git commit --allow-empty -m "commit message"
```

### 7.7 推送到 GitHub

普通推送：

```bash
git push -u origin main
```

如果 `publish.forcePush` 为 true：

```bash
git push -u origin main --force-with-lease
```

要求：

- 禁止使用 `--force`。
- 如需强推，只允许 `--force-with-lease`。
- 如果 `safety.confirmBeforeForcePush` 为 true，必须要求用户确认，除非命令行提供 `--yes`。

如果 `git.pushTags` 为 true：

```bash
git push origin --tags
```

## 8. 两种核心场景

### 场景 A：新项目首次发布

条件：

- 项目目录存在。
- 项目目录不是 Git 仓库。
- GitHub 仓库不存在或已存在。

流程：

1. 读取配置。
2. 检查 Git 和 GitHub CLI。
3. `git init`。
4. 设置默认分支。
5. 处理 `.gitignore`。
6. 创建 GitHub 仓库或确认仓库存在。
7. 添加 remote。
8. `git add .`。
9. `git commit -m "..."`
10. `git push -u origin main`。
11. 输出 GitHub 地址。

### 场景 B：已有 Git 项目推送

条件：

- 项目目录存在。
- 项目目录已经是 Git 仓库。

流程：

1. 读取配置。
2. 检查 Git 和 GitHub CLI。
3. 处理 `.gitignore`。
4. 创建 GitHub 仓库或确认仓库存在。
5. 检查 remote。
6. 如 remote 不存在则添加。
7. 如 remote 与目标不一致则停止并提示。
8. 根据配置和参数生成 commit message。
9. 自动 add 和 commit。
10. push 到配置分支。
11. 输出 GitHub 地址。

## 9. 错误处理

必须处理以下错误：

| 错误 | 处理方式 |
| --- | --- |
| 配置文件不存在 | 输出配置文件路径，提示创建 |
| JSON 格式错误 | 输出解析失败位置或原始错误 |
| 必填字段缺失 | 明确提示缺失字段名 |
| 项目路径不存在 | 停止，提示路径错误 |
| Git 不存在 | 停止，提示安装 Git |
| GitHub CLI 不存在 | 停止，提示安装 `gh` |
| GitHub CLI 未登录 | 停止，提示执行 `gh auth login` |
| 远程仓库不存在且禁止创建 | 停止，提示打开 `createIfMissing` 或手动创建 |
| remote URL 不一致 | 停止，显示当前 URL 和目标 URL |
| commit 无变更 | 根据 `allowEmptyCommit` 决定跳过或空提交 |
| push 失败 | 输出 Git 原始错误，并提示可能需要 pull/rebase |
| 分支不存在 | 自动创建或切换到配置分支 |
| force push 未确认 | 停止，不执行强推 |

错误提示应简单直接，例如：

```text
发布失败：当前 origin 指向 https://github.com/old/repo.git，但配置目标是 https://github.com/new/repo.git。
为避免误推送，程序已停止。
```

## 10. 安全要求

1. 不自动覆盖已有 remote。
2. 不默认 force push。
3. force push 只能使用 `--force-with-lease`。
4. 默认创建 private 仓库。
5. 默认把 `.env` 加入 `.gitignore`。
6. dry-run 模式不能执行任何写操作。
7. 输出日志中不要打印 token、密码、密钥。
8. 不自动删除用户文件。
9. 不自动执行 `git reset --hard`。
10. 不自动执行 `git clean -fd`。

## 11. dry-run 模式

执行：

```bash
python publish.py --dry-run
```

只输出计划执行的动作，例如：

```text
[dry-run] 读取配置 publish.config.json
[dry-run] 项目路径 C:\demo\my-project
[dry-run] 检测到项目不是 Git 仓库，将执行 git init
[dry-run] 将创建 GitHub 仓库 your-name/my-project
[dry-run] 将添加 remote origin
[dry-run] 将提交：chore: publish project
[dry-run] 将推送到 origin/main
```

dry-run 下禁止：

- 创建 GitHub 仓库
- 修改 `.gitignore`
- 执行 `git init`
- 执行 `git add`
- 执行 `git commit`
- 执行 `git push`

## 12. 输出设计

成功输出：

```text
发布成功
仓库：https://github.com/owner/repo
分支：main
提交：chore: publish project
```

无变更但推送成功：

```text
没有检测到新的本地变更，已跳过 commit。
推送完成。
仓库：https://github.com/owner/repo
```

失败输出：

```text
发布失败：GitHub CLI 未登录。
请先执行：gh auth login
```

## 13. 文件结构建议

最小实现：

```text
project/
  publish.py
  publish.config.json
```

更清晰的实现：

```text
project/
  publish.py
  publish.config.json
  README.md
```

如果后续扩展为可安装工具：

```text
one-click-github-publish/
  src/
    github_publish/
      __init__.py
      cli.py
      config.py
      git_ops.py
      github_ops.py
  tests/
  pyproject.toml
  README.md
```

当前需求建议先做最小实现，方便用户直接复制到任何项目根目录使用。

## 14. 开发任务拆分

### 任务 1：实现配置读取

要求：

- 默认读取 `publish.config.json`。
- 支持 `--config` 指定路径。
- 校验 JSON 格式。
- 合并默认值。
- 校验必填字段。

### 任务 2：实现命令执行封装

要求：

- 使用 Python `subprocess.run`。
- 支持指定工作目录。
- 捕获 stdout、stderr。
- 命令失败时返回清晰错误。
- dry-run 下只打印命令，不执行。

### 任务 3：实现环境检查

要求：

- 检查 `git --version`。
- 检查 `gh --version`。
- 检查 `gh auth status`。

### 任务 4：实现 Git 状态识别

要求：

- 判断是否在 Git 仓库中。
- 新项目自动 `git init`。
- 设置默认分支。
- 获取当前分支。
- 必要时切换或创建配置分支。

### 任务 5：实现 `.gitignore` 处理

要求：

- 读取配置中的 ignorePatterns。
- 创建或追加 `.gitignore`。
- 不重复追加已有规则。

### 任务 6：实现 GitHub 仓库处理

要求：

- 使用 `gh repo view owner/repo` 检查仓库。
- 不存在时根据配置决定是否创建。
- 创建时支持 public/private。
- 支持 description。
- 输出最终仓库 URL。

### 任务 7：实现 remote 处理

要求：

- 检查 remote 是否存在。
- 不存在则添加。
- 存在但 URL 不一致则停止。
- 存在且一致则继续。

### 任务 8：实现 add/commit/push

要求：

- 根据配置决定 `git add .` 或 `git add -u`。
- 检查是否有变更。
- 有变更时 commit。
- 无变更时按配置决定是否空提交。
- push 到默认分支。
- 可选推送 tags。

### 任务 9：实现命令行参数

要求：

- `--config`
- `--commit`
- `--dry-run`
- `--yes`
- `--verbose`

### 任务 10：补充 README

要求：

- 写清安装前置条件。
- 写清配置示例。
- 写清新项目发布方式。
- 写清已有 Git 项目发布方式。
- 写清 dry-run。
- 写清常见错误。

## 15. 验收标准

### 基础验收

- 在一个非 Git 项目中运行后，可以自动初始化 Git 并推送到 GitHub。
- 在一个已有 Git 项目中运行后，可以自动提交并推送到 GitHub。
- 可以通过 `--commit` 覆盖默认提交信息。
- 无变更时不会报错。
- 远程仓库不存在时，可以自动创建。
- 配置为 private 时创建 private 仓库。
- 配置为 public 时创建 public 仓库。

### 安全验收

- remote URL 不一致时必须停止。
- 默认不允许 force push。
- dry-run 不产生任何实际改动。
- `.env` 会被加入 `.gitignore`。
- 未登录 GitHub CLI 时不会继续执行。

### 用户体验验收

- 成功时输出 GitHub 仓库链接。
- 失败时能看懂失败原因。
- 只需要一条命令即可完成发布。
- 配置文件字段足够清晰，用户可自行修改。

## 16. 推荐实现伪代码

```python
def main():
    args = parse_args()
    config = load_config(args.config)
    config = merge_defaults(config)
    validate_config(config)

    project_path = resolve_project_path(config["projectPath"])
    check_environment()

    is_git_repo = check_is_git_repo(project_path)
    if not is_git_repo:
        git_init(project_path)
        set_branch(project_path, config["git"]["defaultBranch"])

    ensure_gitignore(project_path, config["safety"]["ignorePatterns"])

    ensure_github_repo(config["github"])
    ensure_remote(project_path, config)

    commit_message = args.commit or config["git"]["defaultCommitMessage"]

    if config["publish"]["autoCommit"]:
        git_add(project_path, include_untracked=config["publish"]["includeUntracked"])
        if has_changes(project_path):
            git_commit(project_path, commit_message)
        elif config["git"]["allowEmptyCommit"]:
            git_empty_commit(project_path, commit_message)
        else:
            print("没有检测到新的本地变更，已跳过 commit。")

    git_push(project_path, config)

    if config["git"]["pushTags"]:
        git_push_tags(project_path, config)

    print_success(config)
```

## 17. 后续可选扩展

当前版本不必实现，但可以预留：

- 支持 SSH remote。
- 支持 GitLab、Gitee。
- 支持多环境配置。
- 支持交互式生成配置文件。
- 支持加密保存敏感配置。
- 支持发布前运行测试命令。
- 支持发布前自动生成 README。
- 支持选择 commit 类型。
- 支持 GUI 界面。

## 18. 给开发 agent 的最终指令

请根据本文档实现一个 Python 命令行工具，目标是让用户通过配置文件一键发布项目到 GitHub。

优先实现最小可用版本：

- `publish.py`
- `publish.config.json`
- `README.md`

必须完整支持：

- 新项目初始化并推送到 GitHub。
- 已有 Git 项目提交并推送到 GitHub。
- 读取配置文件。
- 可选 commit message。
- 自动创建 GitHub 仓库。
- remote 安全检查。
- dry-run。
- 清晰错误提示。

实现时优先使用 Python 标准库。不要引入不必要的复杂框架。工具必须适合普通用户复制到项目根目录后直接使用。
