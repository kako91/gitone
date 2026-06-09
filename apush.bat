@echo off
chcp 65001 >nul
set /p commit_msg="请输入 commit 消息: "
python G:\now\workspace\p6\publish.py --project "." --owner kako91 --commit "%commit_msg%" --repo ^
gitone
pause