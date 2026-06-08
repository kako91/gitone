流程就是：把 publish.config.json 放到目标项目根目录 → 从任意位置用 --project 指向它 → 一键发布。

# 发布其他目录的项目（配置文件放在目标项目里）
python g:\now\workspace\p6\publish.py --project g:\now\workspace\p2

# 手动指定配置文件路径（覆盖默认）
python publish.py --config g:\now\workspace\p2\publish.config.json

# 预览将执行的操作
python publish.py --dry-run

# 一键发布
python publish.py

# 带自定义提交信息
python publish.py --commit "feat: initial commit"