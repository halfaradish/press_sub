# -*- coding: utf-8 -*-
"""应用工厂：注册蓝图、模板全局量、请求钩子。"""
from datetime import datetime

from flask import Flask, g, redirect, request, session, url_for

from . import auth, db
from .helpers import dt, money, status_class


def create_app() -> Flask:
    app = Flask(__name__,
                static_folder="../static",        # webapp/static
                template_folder="templates")
    app.config.from_object("pressapp.config")

    # ---- 蓝图
    from .routes import admin, auth as auth_bp, dashboard, orders, stats
    app.register_blueprint(auth_bp.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(stats.bp)
    app.register_blueprint(admin.bp)

    # ---- 模板全局量与过滤器（session 在 Jinja2 中默认可见）
    weekday_cn = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
    app.jinja_env.globals.update(
        csrf_token=auth.csrf_token,
        now=datetime.now,
        weekday=lambda d: weekday_cn[d.weekday()],
    )
    app.jinja_env.filters.update(money=money, dt=dt, status_class=status_class)

    # ---- 请求钩子：会话角色 → 连接上下文
    @app.before_request
    def prepare():
        g.role = session.get("role")
        if "sub_id" in session and request.endpoint not in ("static",):
            if not request.path.startswith("/static"):
                pass

    @app.teardown_appcontext
    def teardown(exc):
        db.release_request_conn(exc)

    @app.errorhandler(404)
    def not_found(_e):
        from flask import render_template
        return render_template("error.html", code=404, title="页面不存在",
                               detail="请从左侧菜单进入相应功能。"), 404

    @app.errorhandler(500)
    def server_error(_e):
        from flask import render_template
        return render_template("error.html", code=500, title="服务器内部错误",
                               detail="操作未完成，请稍后重试或联系系统管理员。"), 500

    # 根路径按登录状态分发
    @app.route("/")
    def index():
        if "sub_id" not in session:
            return redirect(url_for("auth.login"))
        return redirect(url_for("dashboard.dashboard"))

    return app
