# -*- coding: utf-8 -*-
"""工作台（按角色区分的首页仪表板）。

KPI 与图表数据均在服务端按角色隔离后查询，模板经 tojson 内嵌给 ECharts。
数据口径：订阅用户走行级安全视图 v_user_orders（视图自身过滤本人数据）；
部门管理员走 v_order_detail 按本部门过滤；系统管理员看全局。
"""
from datetime import date, timedelta

from flask import Blueprint, render_template, session

from .. import auth, db

bp = Blueprint("dashboard", __name__)


def _trend(view: str, where: str, params: tuple, months: int = 6):
    """近 N 个月订阅金额趋势（仅统计已通过订单）。"""
    cutoff = date.today().replace(day=1)
    for _ in range(months - 1):
        cutoff = (cutoff - timedelta(days=1)).replace(day=1)
    rows = db.query(
        f"SELECT DATE_FORMAT(sub_date, '%%Y-%%m') AS ym, SUM(subtotal) AS amt"
        f" FROM {view}"
        f" WHERE order_status = '已通过' AND sub_date >= %s {where}"
        f" GROUP BY ym ORDER BY ym",
        (cutoff, *params))
    buckets = {r["ym"]: float(r["amt"] or 0) for r in rows}
    labels, amts = [], []
    y, m = date.today().year, date.today().month
    for _ in range(months):
        labels.append(f"{m}月")
        amts.append(buckets.get(f"{y}-{m:02d}", 0.0))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(labels)), list(reversed(amts))


def _status_dist(view: str, where: str, params: tuple):
    rows = db.query(
        f"SELECT order_status, COUNT(DISTINCT order_id) AS cnt"
        f" FROM {view} WHERE 1=1 {where} GROUP BY order_status", params)
    dist = {r["order_status"]: int(r["cnt"]) for r in rows}
    return [[s, dist.get(s, 0)] for s in ["待审核", "已通过", "已驳回", "已退订"]]


def _top_pubs(where: str, params: tuple, limit: int = 8):
    rows = db.query(
        "SELECT pub_name, SUM(quantity) AS qty, SUM(subtotal) AS amt"
        " FROM v_order_detail WHERE order_status = '已通过' " + where +
        " GROUP BY pub_name ORDER BY amt DESC LIMIT %s",
        (*params, limit))
    return [[r["pub_name"], int(r["qty"] or 0), float(r["amt"] or 0)] for r in rows]


def _top_pubs_global(limit: int = 8):
    """报刊排行（基于 v_pub_stat，订阅用户角色可用）。"""
    rows = db.query(
        "SELECT pub_name, total_qty, total_amount FROM v_pub_stat"
        " ORDER BY total_amount DESC LIMIT %s", (limit,))
    return [[r["pub_name"], int(r["total_qty"] or 0), float(r["total_amount"] or 0)]
            for r in rows]


def _cat_pie(limit: int = 9):
    rows = db.query(
        "SELECT cat_name, SUM(total_amount) AS amt FROM v_pub_stat"
        " GROUP BY cat_name ORDER BY amt DESC")
    top, rest = rows[:limit], rows[limit:]
    data = [[r["cat_name"], float(r["amt"] or 0)] for r in top]
    if rest:
        data.append(["其他类别", round(sum(float(r["amt"] or 0) for r in rest), 2)])
    return data


@bp.route("/dashboard")
@auth.login_required
def dashboard():
    role = session["role"]
    month_start = date.today().replace(day=1)

    if role == "系统管理员":
        kpi = {
            "month_orders": db.scalar(
                "SELECT COUNT(DISTINCT order_id) FROM v_order_detail WHERE sub_date >= %s",
                (month_start,)),
            "month_amount": db.scalar(
                "SELECT IFNULL(SUM(subtotal),0) FROM v_order_detail"
                " WHERE order_status='已通过' AND sub_date >= %s", (month_start,)),
            "pending": db.scalar("SELECT COUNT(*) FROM v_pending_orders"),
            "pubs": db.scalar("SELECT COUNT(*) FROM publication"),
            "subs": db.scalar("SELECT COUNT(*) FROM subscriber"),
            "depts": db.scalar("SELECT COUNT(*) FROM department"),
        }
        labels, amts = _trend("v_order_detail", "", ())
        charts = {
            "trend": {"labels": labels, "amts": amts},
            "cat": _cat_pie(),
            "top": _top_pubs("", ()),
            "status": _status_dist("v_order_detail", "", ()),
        }
        recent = db.query(
            "SELECT order_id, MAX(sub_date) AS sub_date,"
            " MIN(order_status) AS order_status, MAX(total_amount) AS total_amount,"
            " SUBSTRING_INDEX(GROUP_CONCAT(sub_name), ',', 1) AS sub_name,"
            " SUBSTRING_INDEX(GROUP_CONCAT(dept_name), ',', 1) AS dept_name,"
            " COUNT(*) AS det_cnt"
            " FROM v_order_detail GROUP BY order_id"
            " ORDER BY sub_date DESC, order_id DESC LIMIT 8")
        pending = db.query("SELECT * FROM v_pending_orders ORDER BY sub_date LIMIT 6")
        return render_template("dashboard.html", kpi=kpi, charts=charts,
                               recent=recent, pending=pending, scope="admin")

    if role == "部门管理员":
        mine = session["dept_name"]
        where = " AND dept_name = %s"
        kpi = {
            "month_orders": db.scalar(
                "SELECT COUNT(DISTINCT order_id) FROM v_order_detail"
                " WHERE sub_date >= %s" + where, (month_start, mine)),
            "month_amount": db.scalar(
                "SELECT IFNULL(SUM(subtotal),0) FROM v_order_detail"
                " WHERE order_status='已通过' AND sub_date >= %s" + where,
                (month_start, mine)),
            "pending": db.scalar(
                "SELECT COUNT(DISTINCT order_id) FROM v_order_detail"
                " WHERE dept_name = %s AND order_status = '待审核'", (mine,)),
            "members": db.scalar(
                "SELECT COUNT(*) FROM v_user_brief WHERE dept_name = %s", (mine,)),
        }
        labels, amts = _trend("v_order_detail", where, (mine,))
        charts = {
            "trend": {"labels": labels, "amts": amts},
            "top": _top_pubs(where, (mine,)),
            "status": _status_dist("v_order_detail", where, (mine,)),
        }
        recent = db.query(
            "SELECT order_id, MAX(sub_date) AS sub_date,"
            " MIN(order_status) AS order_status, MAX(total_amount) AS total_amount,"
            " SUBSTRING_INDEX(GROUP_CONCAT(sub_name), ',', 1) AS sub_name,"
            " COUNT(*) AS det_cnt"
            " FROM v_order_detail WHERE dept_name = %s"
            " GROUP BY order_id ORDER BY sub_date DESC, order_id DESC LIMIT 8",
            (mine,))
        return render_template("dashboard.html", kpi=kpi, charts=charts,
                               recent=recent, scope="dept")

    # 订阅用户：一切经 v_user_orders（行级安全视图），只能见到本人数据
    kpi = {
        "orders": db.scalar("SELECT COUNT(DISTINCT order_id) FROM v_user_orders"),
        "total_amount": db.query(
            "SELECT fn_person_total_amount(%s) AS t",
            (session["sub_id"],), one=True)["t"],
        "pending": db.scalar(
            "SELECT COUNT(DISTINCT order_id) FROM v_user_orders"
            " WHERE order_status = '待审核'"),
        "pubs": db.scalar("SELECT COUNT(*) FROM publication"),
    }
    labels, amts = _trend("v_user_orders", "", ())
    charts = {
        "trend": {"labels": labels, "amts": amts},
        "top": _top_pubs_global(),
        "status": _status_dist("v_user_orders", "", ()),
    }
    recent = db.query(
        "SELECT order_id, MAX(sub_date) AS sub_date,"
        " MIN(order_status) AS order_status, MAX(total_amount) AS total_amount,"
        " SUBSTRING_INDEX(GROUP_CONCAT(pub_name), ',', 1) AS pub_name,"
        " COUNT(*) AS det_cnt"
        " FROM v_user_orders GROUP BY order_id"
        " ORDER BY sub_date DESC, order_id DESC LIMIT 8")
    return render_template("dashboard.html", kpi=kpi, charts=charts,
                           recent=recent, scope="user")
