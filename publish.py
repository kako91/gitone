#!/usr/bin/env python3
"""
一键发布项目到 GitHub
用法: python publish.py [--config FILE] [--commit MSG] [--dry-run] [--yes] [--verbose]
"""

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
import pdb

# ─── 网络错误关键词 ───────────────────────────────────────────────
NETWORK_ERROR_KEYWORDS = [
    "timeout", "timed out",
    "could not resolve host", "name or service not known",
    "connection refused", "connection reset",
    "failed to connect", "unable to access",
    "ssl", "certificate",
    "network is unreachable",
    "no route to host",
    "temporary failure",
    "errno 10060",
    "errno 10061",
]

# ─── 默认配置 ─────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "projectPath": ".",
    "github": {
        "owner": "",
        "repo": "",
        "visibility": "private",
        "description": "",
        "homepage": "",
        "createIfMissing": True,
    },
    "git": {
        "defaultBranch": "main",
        "remoteName": "origin",
        "defaultCommitMessage": "chore: publish project",
        "allowEmptyCommit": False,
        "pushTags": False,
    },
    "publish": {
        "includeUntracked": True,
        "autoCommit": True,
        "forcePush": False,
        "openAfterPublish": False,
    },
    "safety": {
        "requireCleanRemote": False,
        "confirmBeforeForcePush": True,
        "ignorePatterns": [
            ".env",
            "node_modules/",
            "__pycache__/",
        ]
    }
}


# ─── 工具函数 ─────────────────────────────────────────────────────
def is_network_error(stderr: str) -> bool:
    """判断 stderr 是否包含网络相关错误关键词"""
    lower = stderr.lower()
    return any(kw in lower for kw in NETWORK_ERROR_KEYWORDS)


def print_network_help():
    """输出网络排查提示"""
    print("\n请检查：")
    print("  1. 网络连接是否正常，能否访问 github.com")
    print("  2. 是否需要配置代理（git config --global http.proxy ...）")
    print("  3. GitHub 服务状态：https://www.githubstatus.com")
    print("网络恢复后重新运行发布命令。")


def deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典，override 覆盖 base"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def run_cmd(cmd: list[str], cwd: str | None = None, dry_run: bool = False,
            verbose: bool = False, check: bool = True) -> subprocess.CompletedProcess | None:
    """执行命令，dry_run 模式下只打印不执行"""
    cmd_str = " ".join(cmd)
    if dry_run:
        print(f"[dry-run] 将执行: {cmd_str}")
        return None
    if verbose:
        print(f"  → {cmd_str}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=120)
    if check and result.returncode != 0:
        return result
    return result


def fail(msg: str, code: int = 1):
    """输出错误信息并退出"""
    print(f"发布失败：{msg}")
    sys.exit(code)


# ─── 配置读取 ─────────────────────────────────────────────────────
def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        #fail(f"配置文件不存在：{path.absolute()}\n请在项目根目录创建 publish.config.json")
        # 没有配置文件时使用默认值（CLI 参数已注入 DEFAULT_CONFIG）
        return DEFAULT_CONFIG

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        fail(f"配置文件 JSON 格式错误：{e}")

    config = deep_merge(DEFAULT_CONFIG, raw)
    return config


def validate_config(config: dict):
    required = [
        ("github.owner", config["github"]["owner"]),
        ("github.repo", config["github"]["repo"]),
    ]
    missing = [name for name, val in required if not val]
    if missing:
        fail(f"配置文件缺少必填字段：{', '.join(missing)}")


def resolve_project_path(project_path: str, base_dir: str | None = None) -> str:
    if base_dir:
        resolved = (Path(base_dir) / project_path).resolve()
    else:
        resolved = Path(project_path).resolve()
    if not resolved.exists():
        fail(f"项目路径不存在：{resolved}")
    if not resolved.is_dir():
        fail(f"项目路径不是目录：{resolved}")
    return str(resolved)


# ─── 环境检查 ─────────────────────────────────────────────────────
def check_git():
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            fail("未检测到 Git，请先安装 Git：https://git-scm.com/downloads")
    except FileNotFoundError:
        fail("未检测到 Git，请先安装 Git：https://git-scm.com/downloads")


def check_gh():
    try:
        result = subprocess.run(["gh", "--version"], capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            fail("未检测到 GitHub CLI (gh)，请先安装：https://cli.github.com/")
    except FileNotFoundError:
        fail("未检测到 GitHub CLI (gh)，请先安装：https://cli.github.com/"
             "\n安装后在终端运行：gh auth login")


def check_gh_auth():
    try:
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            print("发布失败：GitHub CLI 未登录。")
            print("请按以下步骤操作：")
            print("  1. 在终端运行：gh auth login")
            print("  2. 按提示选择 GitHub.com → HTTPS → 浏览器登录")
            print("  3. 登录完成后，重新运行：python publish.py")
            sys.exit(1)
    except FileNotFoundError:
        fail("未检测到 GitHub CLI (gh)，请先安装：https://cli.github.com/")


# ─── Git 操作 ─────────────────────────────────────────────────────
def is_git_repo(project_path: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_path, capture_output=True, text=True, encoding="utf-8"
    )
    return result.returncode == 0


def git_init(project_path: str, branch: str, dry_run: bool, verbose: bool):
    if dry_run:
        print(f"[dry-run] 检测到项目不是 Git 仓库，将执行 git init")
        print(f"[dry-run] 将设置默认分支为 {branch}")
        return
    run_cmd(["git", "init"], cwd=project_path, verbose=verbose)
    run_cmd(["git", "branch", "-M", branch], cwd=project_path, verbose=verbose)
    print(f"已初始化 Git 仓库，默认分支：{branch}")


def ensure_branch(project_path: str, branch: str, dry_run: bool, verbose: bool):
    """确保当前在目标分支上，不存在则创建并切换"""
    if dry_run:
        print(f"[dry-run] 将确保分支 {branch} 存在并切换")
        return

    result = subprocess.run(
        ["git", "branch", "--list", branch],
        cwd=project_path, capture_output=True, text=True, encoding="utf-8"
    )
    branch_exists = branch.strip() in result.stdout

    current = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=project_path, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()

    if current == branch:
        return

    if branch_exists:
        run_cmd(["git", "checkout", branch], cwd=project_path, verbose=verbose)
    else:
        run_cmd(["git", "checkout", "-b", branch], cwd=project_path, verbose=verbose)
    print(f"已切换到分支：{branch}")


# ─── .gitignore 处理 ─────────────────────────────────────────────
def ensure_gitignore(project_path: str, patterns: list[str], dry_run: bool, verbose: bool):
    if not patterns:
        return

    gitignore_path = Path(project_path) / ".gitignore"

    if dry_run:
        print(f"[dry-run] 将处理 .gitignore，追加 {len(patterns)} 条忽略规则")
        return

    existing_lines = set()
    if gitignore_path.exists():
        existing_lines = set(gitignore_path.read_text(encoding="utf-8").splitlines())

    new_patterns = [p for p in patterns if p not in existing_lines]
    if not new_patterns:
        if verbose:
            print("  .gitignore 已包含所有规则，无需更新")
        return

    with open(gitignore_path, "a", encoding="utf-8") as f:
        if existing_lines and not existing_lines.intersection({""}):
            f.write("\n")
        for pattern in new_patterns:
            f.write(f"{pattern}\n")

    print(f"已更新 .gitignore，追加了 {len(new_patterns)} 条规则")


# ─── GitHub 仓库处理 ─────────────────────────────────────────────
def ensure_github_repo(github_config: dict, dry_run: bool, verbose: bool):
    owner = github_config["owner"]
    repo = github_config["repo"]
    full_name = f"{owner}/{repo}"
    visibility = github_config.get("visibility", "private")
    description = github_config.get("description", "")
    create_if_missing = github_config.get("createIfMissing", True)

    if dry_run:
        print(f"[dry-run] 将检查/创建 GitHub 仓库 {full_name}")
        return

    # 检查仓库是否存在
    result = subprocess.run(
        ["gh", "repo", "view", full_name],
        capture_output=True, text=True, encoding="utf-8"
    )

    if result.returncode == 0:
        if verbose:
            print(f"  GitHub 仓库 {full_name} 已存在")
        return

    # 判断是否为网络错误
    if is_network_error(result.stderr):
        print(f"发布失败：无法连接 GitHub，可能是网络问题。")
        print_network_help()
        sys.exit(1)

    # 仓库不存在
    if not create_if_missing:
        fail(f"GitHub 仓库 {full_name} 不存在，且 createIfMissing 为 false。\n"
             f"请手动创建仓库或将 createIfMissing 设为 true。")

    # 创建仓库
    cmd = ["gh", "repo", "create", full_name, f"--{visibility}"]
    if description:
        cmd.extend(["--description", description])

    create_result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if create_result.returncode != 0:
        if is_network_error(create_result.stderr):
            print(f"发布失败：创建仓库时无法连接 GitHub，可能是网络问题。")
            print_network_help()
            sys.exit(1)
        fail(f"创建 GitHub 仓库失败：{create_result.stderr.strip()}")

    print(f"已创建 GitHub 仓库：{full_name}（{visibility}）")


# ─── Remote 处理 ──────────────────────────────────────────────────
def ensure_remote(project_path: str, config: dict, dry_run: bool, verbose: bool):
    remote_name = config["git"]["remoteName"]
    owner = config["github"]["owner"]
    repo = config["github"]["repo"]
    target_url = f"https://github.com/{owner}/{repo}.git"

    if dry_run:
        print(f"[dry-run] 将检查/添加 remote {remote_name} → {target_url}")
        return

    result = subprocess.run(
        ["git", "remote", "get-url", remote_name],
        cwd=project_path, capture_output=True, text=True, encoding="utf-8"
    )

    if result.returncode != 0:
        # remote 不存在，添加
        run_cmd(["git", "remote", "add", remote_name, target_url],
                cwd=project_path, verbose=verbose)
        print(f"已添加 remote {remote_name} → {target_url}")
        return

    # remote 存在，检查 URL
    current_url = result.stdout.strip()
    # 规范化 URL 比较（去掉尾部 .git）
    norm_current = current_url.rstrip("/").removesuffix(".git")
    norm_target = target_url.rstrip("/").removesuffix(".git")

    if norm_current != norm_target:
        fail(f"当前 {remote_name} 指向 {current_url}，但配置目标是 {target_url}。\n"
             f"为避免误推送，程序已停止。")

    if verbose:
        print(f"  remote {remote_name} 已指向正确地址")


# ─── 网络预检 ─────────────────────────────────────────────────────
def check_network(project_path: str, remote_name: str, dry_run: bool, verbose: bool):
    """推送前用 git ls-remote 测试网络连通性"""
    if dry_run:
        print(f"[dry-run] 将测试与 {remote_name} 的网络连通性")
        return

    if verbose:
        print(f"  正在测试与 {remote_name} 的网络连通性...")

    result = subprocess.run(
        ["git", "ls-remote", remote_name],
        cwd=project_path, capture_output=True, text=True, encoding="utf-8", timeout=30
    )
    if result.returncode != 0 and is_network_error(result.stderr):
        print("发布失败：无法连接到远程仓库，可能是网络问题。")
        print_network_help()
        sys.exit(1)


# ─── Add / Commit / Push ─────────────────────────────────────────
def git_add_and_commit(project_path: str, config: dict, commit_message: str,
                       dry_run: bool, verbose: bool) -> bool:
    """执行 add + commit，返回是否有提交发生"""
    if not config["publish"]["autoCommit"]:
        if dry_run:
            print("[dry-run] autoCommit 为 false，将跳过 add/commit")
        return False

    # git add
    if config["publish"]["includeUntracked"]:
        if dry_run:
            print("[dry-run] 将执行: git add .")
        else:
            run_cmd(["git", "add", "."], cwd=project_path, verbose=verbose)
    else:
        if dry_run:
            print("[dry-run] 将执行: git add -u")
        else:
            run_cmd(["git", "add", "-u"], cwd=project_path, verbose=verbose)

    # 检查是否有变更
    if dry_run:
        print(f"[dry-run] 将提交：{commit_message}")
        return True

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_path, capture_output=True, text=True, encoding="utf-8"
    )
    has_changes = bool(status.stdout.strip())

    if has_changes:
        if dry_run:
            print(f"[dry-run] 将提交：{commit_message}")
            return True
        run_cmd(["git", "commit", "-m", commit_message],
                cwd=project_path, verbose=verbose)
        print(f"已提交：{commit_message}")
        return True
    else:
        if config["git"]["allowEmptyCommit"]:
            if dry_run:
                print(f"[dry-run] 将执行空提交：{commit_message}")
                return True
            run_cmd(["git", "commit", "--allow-empty", "-m", commit_message],
                    cwd=project_path, verbose=verbose)
            print(f"已空提交：{commit_message}")
            return True
        else:
            print("没有检测到新的本地变更，已跳过 commit。")
            return False


def git_push(project_path: str, config: dict, dry_run: bool, verbose: bool, auto_yes: bool):
    remote_name = config["git"]["remoteName"]
    branch = config["git"]["defaultBranch"]
    force_push = config["publish"]["forcePush"]
    confirm_force = config["safety"]["confirmBeforeForcePush"]

    if force_push:
        if confirm_force and not auto_yes:
            answer = input(f"\n⚠ 即将对 {remote_name}/{branch} 执行 force push，是否继续？(y/N): ").strip().lower()
            if answer != "y":
                print("已取消 force push。")
                sys.exit(0)

    if dry_run:
        mode = "force push (--force-with-lease)" if force_push else "push"
        print(f"[dry-run] 将{mode}到 {remote_name}/{branch}")
        return

    cmd = ["git", "push", "-u", remote_name, branch]
    if force_push:
        cmd.append("--force-with-lease")

    result = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True, encoding="utf-8", timeout=120)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if is_network_error(stderr):
            print("发布失败：推送时网络连接异常。")
            print(f"Git 原始错误：{stderr}")
            print_network_help()
        else:
            print("发布失败：推送被拒绝。")
            print(f"Git 原始错误：{stderr}")
            print(f"可能原因：远程仓库有本地没有的提交。")
            print(f"建议执行：git pull --rebase {remote_name} {branch}，然后重新发布。")
        sys.exit(1)

    if verbose:
        print(f"  push 输出：{result.stderr.strip()}")

    # 推送 tags
    if config["git"]["pushTags"]:
        if dry_run:
            print(f"[dry-run] 将推送 tags 到 {remote_name}")
        else:
            tag_result = subprocess.run(
                ["git", "push", remote_name, "--tags"],
                cwd=project_path, capture_output=True, text=True, encoding="utf-8", timeout=60
            )
            if tag_result.returncode != 0:
                print(f"警告：推送 tags 失败：{tag_result.stderr.strip()}")
            else:
                print("已推送 tags。")


# ─── 输出 ─────────────────────────────────────────────────────────
def print_success(config: dict, commit_message: str | None, committed: bool):
    owner = config["github"]["owner"]
    repo = config["github"]["repo"]
    branch = config["git"]["defaultBranch"]
    url = f"https://github.com/{owner}/{repo}"

    print()
    if committed:
        print("发布成功")
    else:
        print("推送完成。")
    print(f"仓库：{url}")
    print(f"分支：{branch}")
    if committed and commit_message:
        print(f"提交：{commit_message}")

    if config["publish"]["openAfterPublish"]:
        webbrowser.open(url)


# ─── 参数解析 ─────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(description="一键发布项目到 GitHub")
    parser.add_argument("--project", default=None, help="项目根目录路径（配置文件从此目录查找）")
    parser.add_argument("--config", default=None, help="配置文件路径（默认 {project}/publish.config.json）")
    parser.add_argument("--commit", default=None, help="本次提交信息")
    parser.add_argument("--dry-run", action="store_true", help="只展示将执行的步骤")
    parser.add_argument("--yes", action="store_true", help="自动确认非危险操作")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")
    parser.add_argument("--owner", default=None, help="GitHub 用户名")
    parser.add_argument("--repo", default=None, help="GitHub 仓库名")
    return parser.parse_args()


# ─── 主流程 ───────────────────────────────────────────────────────
def main():
    args = parse_args()
    dry_run = args.dry_run
    verbose = args.verbose

    # 0. 确定基准目录
    base_dir = args.project  # --project 指定的项目根目录，或 None
    # 加载配置之前：
    if args.owner:
        DEFAULT_CONFIG["github"]["owner"] = args.owner
    if args.repo:
        DEFAULT_CONFIG["github"]["repo"] = args.repo
    if args.project:
        DEFAULT_CONFIG["projectPath"] = args.project

    # 1. 确定配置文件路径
    if args.config:
        config_path = args.config
    elif base_dir:
        config_path = str(Path(base_dir) / "publish.config.json")
    else:
        config_path = "publish.config.json"

    # 读取配置
    if dry_run:
        print(f"[dry-run] 读取配置 {config_path}")
    config = load_config(config_path)
    validate_config(config)
    project_path = resolve_project_path(config["projectPath"], base_dir=base_dir)

    if dry_run:
        print(f"[dry-run] 项目路径 {project_path}")

    # 2. 环境检查
    if not dry_run:
        check_git()
        check_gh()
        check_gh_auth()
    else:
        print("[dry-run] 将检查 Git、GitHub CLI 和登录状态")

    # 3. Git 状态
    if not dry_run:
        if not is_git_repo(project_path):
            git_init(project_path, config["git"]["defaultBranch"], dry_run, verbose)
        else:
            ensure_branch(project_path, config["git"]["defaultBranch"], dry_run, verbose)
    else:
        is_repo = is_git_repo(project_path)
        if not is_repo:
            print(f"[dry-run] 检测到项目不是 Git 仓库，将执行 git init")
        else:
            print(f"[dry-run] 检测到项目已是 Git 仓库，将确保分支为 {config['git']['defaultBranch']}")

    # 4. .gitignore（必须在 git add 之前）
    ensure_gitignore(project_path, config["safety"]["ignorePatterns"], dry_run, verbose)

    # 5. GitHub 仓库
    ensure_github_repo(config["github"], dry_run, verbose)

    # 6. Remote
    ensure_remote(project_path, config, dry_run, verbose)

    # 7. 网络预检
    if not dry_run:
        check_network(project_path, config["git"]["remoteName"], dry_run, verbose)
    else:
        print(f"[dry-run] 将测试与 {config['git']['remoteName']} 的网络连通性")

    # 8. Add + Commit
    commit_message = args.commit or config["git"]["defaultCommitMessage"]
    committed = git_add_and_commit(project_path, config, commit_message, dry_run, verbose)

    # 9. Push
    git_push(project_path, config, dry_run, verbose, args.yes)

    # 10. 完成输出
    if not dry_run:
        print_success(config, commit_message, committed)
    else:
        print(f"[dry-run] 将输出 GitHub 仓库地址")


if __name__ == "__main__":
    main()
