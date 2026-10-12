# -*- coding: utf-8 -*-
"""应用配置：读取 config/config.yml（见 config/config.example.yml 模板）。"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]          # 仓库根目录
CONFIG_FILE = ROOT / "config" / "config.yml"

# Flask 会话签名密钥（课程演示环境使用固定值；生产环境应改为环境变量注入）
SECRET_KEY = "press-sub-db-2026-course-demo"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
PERMANENT_SESSION_LIFETIME = 60 * 60 * 2            # 登录保持 2 小时
MAX_CONTENT_LENGTH = 2 * 1024 * 1024

# 连接池参数
POOL_SIZE = 6                                       # 每个 MySQL 账号的最大连接数

# 数据库角色 → MySQL 应用账号（与 sql/06_permissions.sql 保持一致，
# 三个静态账号供命令行演示与脚本验证使用）
ROLE_ACCOUNTS = {
    "系统管理员": ("sys_admin_app", "Admin#2026"),
    "部门管理员": ("dept_admin_app", "Dept#2026"),
    "订阅用户":   ("sub_user_app", "Sub#2026"),
}
# 系统角色 → 数据库角色（动态账号授权用）
DB_ROLE_NAMES = {
    "系统管理员": "r_sys_admin",
    "部门管理员": "r_dept_admin",
    "订阅用户":   "r_sub_user",
}
# 动态同名账号：登录时为人员创建与其用户名同名的 MySQL 账号并授予对应角色，
# 行级安全视图 v_user_orders 依赖 CURRENT_USER() 匹配用户名生效
DYNAMIC_DB_ACCOUNTS = True
# 认证专用账号：仅授权 subscriber 表 5 个列的 SELECT 与 password 列的 UPDATE
AUTH_ACCOUNT = ("auth_app", "Auth#2026")


def mysql_base() -> dict:
    """从本地配置读取 MySQL 连接参数（root 账号仅供脚本维护使用）。"""
    cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))["mysql"]
    return {
        "host": cfg["ip"],
        "port": int(cfg["port"]),
        "user": cfg["user"],
        "password": cfg["password"],
        "charset": "utf8mb4",
        "autocommit": True,
    }
