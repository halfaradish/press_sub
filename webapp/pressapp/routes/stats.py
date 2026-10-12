# -*- coding: utf-8 -*-
"""查询与统计：订阅明细模糊查询（可打印）、三维度统计图表、个人中心。

统计口径统一为“已通过”订单；图表数据由服务端查询后经 tojson 内嵌。
"""
from datetime import date, timedelta

from flask import Blueprint, render_template, request, session

from .. import auth, db
from ..helpers import paginate

bp = Blueprint("stats", __name__)


# ------------------------------------------------------------------ 订阅明细查询
@bp.route("/query")
@auth.login_required
def query():
    kw = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    dept = request.args.get("dept", "").strip()
    d1, d2 = request.args.get("d1", "").strip(), request.args.get("d2", "").strip()
    role = session["role"]

    # 数据源按角色区分：订阅用户走行级安全视图（无 sub_name/dept_name 列），
    # 其余角色走明细全景视图并由应用层限定部门/全局范围
    user_view = role == "订阅用户"
    rows_view = "v_user_orders d" if user_view else "v_order_detail d"

    where, args = "", []
    if kw:
        if user_view:
            where += " AND (d.order_id LIKE %s OR d.pub_name LIKE %s)"
            args += [f"%{kw}%"] * 2
        else:
            where += (" AND (d.sub_name LIKE %s OR d.pub_name LIKE %s"
                      " OR d.dept_name LIKE %s OR d.order_id LIKE %s)")
            args += [f"%{kw}%"] * 4
    if status:
        where += " AND d.order_status = %s"
        args.append(status)
    if d1:
        where += " AND d.sub_date >= %s"
        args.append(d1)
    if d2:
        where += " AND d.sub_date <= %s"
        args.append(d2)
    if role == "部门管理员":
        where += " AND d.dept_name = %s"
        args.append(session["dept_name"])
    elif role == "系统管理员" and dept:
        where += " AND d.dept_name = %s"
        args.append(dept)

    pg = paginate(
        "SELECT d.* FROM " + rows_view + " WHERE 1=1" + where +
        " ORDER BY d.sub_date DESC, d.order_id DESC, d.pub_id",
        "SELECT COUNT(*) FROM " + rows_view + " WHERE 1=1" + where,
        tuple(args), per_page=15)
    depts = db.query("SELECT dept_id, dept_name FROM department ORDER BY dept_id") \
        if role == "系统管理员" else []
    return render_template("query.html", pg=pg, q=kw, f_status=status,
                           f_dept=dept, d1=d1, d2=d2, depts=depts,
                           user_view=user_view)


# ------------------------------------------------------------------ 统计分析
@bp.route("/stats")
@auth.login_required
def stats():
    role = session["role"]
    kw = request.args.get("q", "").strip()

    # ① 按报刊统计（全局，所有角色可见）
    pub_rows = db.query(
        "SELECT * FROM v_pub_stat ORDER BY total_amount DESC")
    pub_top = [[r["pub_name"], int(r["total_qty"] or 0), float(r["total_amount"] or 0)]
               for r in pub_rows[:12]]
    pub_pie = _pie_top(pub_rows, "cat_name", "total_amount")

    # ② 近 12 个月订阅趋势（按角色隔离）
    cutoff = _months_ago(12)
    if role == "订阅用户":
        trend_rows = db.query(
            "SELECT DATE_FORMAT(sub_date, '%%Y-%%m') AS ym, SUM(subtotal) AS amt"
            " FROM v_user_orders WHERE order_status='已通过' AND sub_date >= %s"
            " GROUP BY ym ORDER BY ym", (cutoff,))
        person_pg = None
        dept_rows = []
        mine = db.query(
            "SELECT sub_id, sub_name FROM v_user_brief WHERE sub_id = %s",
            (session["sub_id"],), one=True)
        my_total = db.query("SELECT fn_person_total_amount(%s) AS t",
                            (session["sub_id"],), one=True)["t"]
    else:
        scope, sargs = ("", ()) if role == "系统管理员" else \
            (" AND dept_name = %s", (session["dept_name"],))
        trend_rows = db.query(
            "SELECT DATE_FORMAT(sub_date, '%%Y-%%m') AS ym, SUM(subtotal) AS amt"
            " FROM v_order_detail WHERE order_status='已通过' AND sub_date >= %s" + scope +
            " GROUP BY ym ORDER BY ym", (cutoff, *sargs))
        # ③ 按人员统计（可模糊查询姓名，支持分页）
        extra, extra_args = "", []
        if kw:
            extra = " AND sub_name LIKE %s"
            extra_args = [f"%{kw}%"]
        if role == "部门管理员":
            extra += " AND dept_name = %s"
            extra_args.append(session["dept_name"])
        person_pg = paginate(
            "SELECT * FROM v_person_stat WHERE 1=1" + extra +
            " ORDER BY total_amount DESC",
            "SELECT COUNT(*) FROM v_person_stat WHERE 1=1" + extra,
            tuple(extra_args), per_page=12)
        dept_rows = db.query("SELECT * FROM v_dept_stat ORDER BY total_amount DESC") \
            if role == "系统管理员" else []
        mine, my_total = None, None

    trend_map = {r["ym"]: float(r["amt"] or 0) for r in trend_rows}
    labels, amts = [], []
    y, m = date.today().year, date.today().month
    for _ in range(12):
        labels.append(f"{y}-{m:02d}")
        amts.append(trend_map.get(f"{y}-{m:02d}", 0.0))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    trend = {"labels": list(reversed(labels)), "amts": list(reversed(amts))}

    dept_top = [[r["dept_name"], float(r["total_amount"] or 0), int(r["order_cnt"] or 0)]
                for r in dept_rows[:12]]
    return render_template("stats.html", pub_top=pub_top, pub_pie=pub_pie,
                           trend=trend, person_pg=person_pg, dept_top=dept_top,
                           q=kw, mine=mine, my_total=my_total, role=role)


def _pie_top(rows, key: str, value: str, limit: int = 8):
    agg = {}
    for r in rows:
        agg[r[key]] = agg.get(r[key], 0) + float(r[value] or 0)
    items = sorted(agg.items(), key=lambda kv: -kv[1])
    top = [[k, round(v, 2)] for k, v in items[:limit]]
    if len(items) > limit:
        top.append(["其他", round(sum(v for _, v in items[limit:]), 2)])
    return top


def _months_ago(n: int):
    d = date.today().replace(day=1)
    for _ in range(n - 1):
        d = (d - timedelta(days=1)).replace(day=1)
    return d
