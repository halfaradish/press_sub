# -*- coding: utf-8 -*-
"""登录、退出、修改口令。"""
from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)

from .. import auth, db
from ..helpers import write_log

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        guard = auth.check_csrf()
        if guard:
            return guard
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = auth.verify(username, password) if username and password else None
        if not user:
            flash("用户名或口令不正确。", "error")
            return render_template("login.html", username=username), 401
        auth.load_session(user)
        g.role = user["role"]
        write_log("登录", f"{user['sub_name']}（{user['role']}）登录系统")
        return redirect(url_for("dashboard.dashboard"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    if "sub_id" in session:
        write_log("登录", f"{session.get('sub_name')} 退出系统")
    auth.logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/profile")
@auth.login_required
def profile():
    me = db.query(
        "SELECT * FROM v_user_brief WHERE sub_id = %s",
        (session["sub_id"],), one=True)
    total = db.query("SELECT fn_person_total_amount(%s) AS t",
                     (session["sub_id"],), one=True)["t"]
    return render_template("profile.html", me=me, total=total)


@bp.route("/password", methods=["GET", "POST"])
@auth.login_required
def password():
    if request.method == "POST":
        guard = auth.check_csrf()
        if guard:
            return guard
        old = request.form.get("old_password", "")
        new1 = request.form.get("new_password", "")
        new2 = request.form.get("new_password2", "")
        if not (old and new1 and new2):
            flash("请填写完整三项口令。", "error")
        elif auth.verify(session["username"], old) is None:
            flash("原口令不正确。", "error")
        elif len(new1) < 6:
            flash("新口令至少 6 位。", "error")
        elif new1 != new2:
            flash("两次输入的新口令不一致。", "error")
        else:
            # 口令更新走认证专用账号：其仅被授权 UPDATE subscriber.password 一列
            conn = db.auth_conn()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE subscriber SET password = %s WHERE username = %s",
                            (auth.digest(new1), session["username"]))
                cur.close()
            finally:
                conn.close()
            write_log("维护", "修改登录口令")
            flash("口令修改成功，下次登录请使用新口令。", "ok")
            return redirect(url_for("auth.password"))
    return render_template("profile.html")
