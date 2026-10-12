# -*- coding: utf-8 -*-
"""登录认证与访问控制。

1. 身份认证：username + SHA-256 口令摘要比对（auth_app 列级授权账号完成）；
2. 会话：Flask signed session 保存 sub_id / role / dept_name；
3. 授权：login_required + role_required 装饰器做页面级控制，
   数据库账号的 GRANT 做数据级兜底（应用层与数据库层双重防线）。
"""
import functools
import hashlib
import secrets

from flask import (flash, g, redirect, render_template, request, session,
                   url_for)

from . import config, db

SESSION_KEYS = ("sub_id", "sub_name", "username", "role", "dept_name")


def digest(password: str) -> str:
    """口令摘要：SHA-256 十六进制（64 位，与 password VARCHAR(64) 对应）。"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify(username: str, password: str) -> dict | None:
    """用认证专用账号校验登录，成功返回人员信息。"""
    conn = db.auth_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT sub_id, username, password, role, sub_name"
            " FROM subscriber WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
    finally:
        conn.close()
    if row and row[2] == digest(password):
        return {"sub_id": row[0], "username": row[1],
                "role": row[3], "sub_name": row[4]}
    return None


def ensure_db_account(username: str, role: str):
    """登录时确保该人员拥有同名 MySQL 账号并已授予对应角色（动态账号）。

    口令由“服务端密钥 + 用户名”推导（db.dynamic_pwd），不在任何地方存储；
    每次登录幂等地执行 CREATE USER IF NOT EXISTS / ALTER USER / GRANT。
    该设计使行级安全视图 v_user_orders 的 CURRENT_USER() 过滤在 Web 场景下生效。
    """
    if not config.DYNAMIC_DB_ACCOUNTS:
        return
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9_]{2,20}", username):
        raise ValueError("用户名仅限字母、数字与下划线（2~20 位）")
    role_name = config.DB_ROLE_NAMES.get(role)
    if role_name is None:
        raise ValueError(f"未知的系统角色：{role}")
    quoted = f"'{username}'@'localhost'"
    conn = db.root_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE USER IF NOT EXISTS {quoted} IDENTIFIED BY %s",
                    (db.dynamic_pwd(username),))
        cur.execute(f"ALTER USER {quoted} IDENTIFIED BY %s",
                    (db.dynamic_pwd(username),))
        cur.execute(f"GRANT '{role_name}' TO {quoted}")
        cur.execute(f"SET DEFAULT ROLE ALL TO {quoted}")
        cur.close()
    finally:
        conn.close()


def load_session(user: dict):
    """登录成功：写入会话，并查询本人部门用于部门管理员的数据隔离。"""
    ensure_db_account(user["username"], user["role"])
    session.permanent = True
    session["sub_id"] = user["sub_id"]
    session["sub_name"] = user["sub_name"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    dept = db.query(
        "SELECT dept_name FROM v_user_brief WHERE sub_id = %s",
        (user["sub_id"],), one=True)
    session["dept_name"] = dept["dept_name"] if dept else None


def logout_user():
    for key in SESSION_KEYS:
        session.pop(key, None)


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if "sub_id" not in session:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """限定页面可访问的角色，未授权返回 403 页面。"""
    def decorator(view):
        @functools.wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                return render_template("error.html",
                                       code=403, title="没有访问权限",
                                       detail=f"该页面仅限 {'、'.join(roles)} 使用。"), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ------------------------------------------------------------------ CSRF 防护
def csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def check_csrf():
    token = request.form.get("csrf_token", "")
    if not token or token != session.get("_csrf"):
        return render_template("error.html", code=403, title="表单校验失败",
                               detail="页面凭证已过期，请返回刷新后重新提交。"), 403
    return None
