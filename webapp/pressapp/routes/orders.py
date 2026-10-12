# -*- coding: utf-8 -*-
"""订阅业务：新建订阅单、追加明细、我的订单、订单审核、退订。

写操作全部经由存储过程完成（内部显式事务）：
  sp_place_order   创建订阅单（订单号加锁取号）
  sp_add_detail    向待审核订阅单追加明细
  sp_audit_order   系统管理员审核
  sp_cancel_order  本人退订
触发器在明细插入/订单状态变化时自动计算小计、汇总总金额并写操作日志。
"""
from datetime import date, datetime

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, session, url_for)

from .. import auth, db
from ..helpers import flash_error, paginate, write_log

bp = Blueprint("orders", __name__)

ORDER_STATUSES = ["待审核", "已通过", "已驳回", "已退订"]


def _order_scope(where_sub_of_order: str = "d.sub_id") -> tuple:
    """按登录角色返回订单数据的过滤条件（应用层行级隔离）。"""
    role = session["role"]
    if role == "系统管理员":
        return "", ()
    if role == "部门管理员":
        return " AND d.dept_name = %s", (session["dept_name"],)
    return f" AND {where_sub_of_order} = %s", (session["sub_id"],)


def _order_view() -> str:
    """订单数据源视图：订阅用户走行级安全视图 v_user_orders（视图自身
    过滤本人订单），其余角色走明细全景视图 v_order_detail（应用层按
    部门/全局过滤）。任何角色的订单展示都不直接读基表。"""
    return "v_user_orders" if session["role"] == "订阅用户" else "v_order_detail"


def _order_level_rows(extra: str, args: tuple, per_page=10):
    """从明细级视图聚合出订单级列表（含状态/关键字筛选）。"""
    view = _order_view()
    cond, scope_args = _order_scope("sub_id")
    name_col = "pub_name" if view == "v_user_orders" else "sub_name"
    dept_col = (", SUBSTRING_INDEX(GROUP_CONCAT(dept_name), ',', 1) AS dept_name"
                if view == "v_order_detail" else "")
    pg = paginate(
        f"SELECT order_id, MAX(sub_date) AS sub_date, MAX(end_date) AS end_date,"
        f" MIN(order_status) AS order_status, MAX(total_amount) AS total_amount,"
        f" SUBSTRING_INDEX(GROUP_CONCAT({name_col}), ',', 1) AS {name_col},"
        f" COUNT(*) AS det_cnt, SUM(quantity) AS total_qty" + dept_col +
        f" FROM {view} WHERE 1=1" + cond + extra +
        " GROUP BY order_id ORDER BY MAX(sub_date) DESC, order_id DESC",
        f"SELECT COUNT(DISTINCT order_id) FROM {view} WHERE 1=1" + cond + extra,
        (*scope_args, *args), per_page=per_page)
    return pg


def _order_head(order_id: str):
    """按角色取订单头（明细级视图聚合为订单级）；不可见返回 None。"""
    view = _order_view()
    head = db.query(
        f"SELECT order_id, MAX(sub_date) AS sub_date, MAX(start_date) AS start_date,"
        f" MAX(end_date) AS end_date, MIN(order_status) AS order_status,"
        f" MAX(total_amount) AS total_amount, MAX(auditor_id) AS auditor_id,"
        f" MAX(audit_time) AS audit_time, MAX(audit_comment) AS audit_comment,"
        f" SUBSTRING_INDEX(GROUP_CONCAT(sub_name), ',', 1) AS sub_name,"
        f" SUBSTRING_INDEX(GROUP_CONCAT(dept_name), ',', 1) AS dept_name,"
        + ("MAX(sub_id) AS orderer_id, " if view == "v_order_detail" else "") +
        f" COUNT(*) AS det_cnt"
        f" FROM {view} WHERE order_id = %s GROUP BY order_id",
        (order_id,), one=True)
    if head is None:
        return None
    if session["role"] == "部门管理员" and head["dept_name"] != session["dept_name"]:
        return None
    return head


def _order_details(order_id: str):
    """按角色取订单明细行（来自有权访问的视图，不读基表）。"""
    view = _order_view()
    return db.query(
        f"SELECT pub_id, pub_name, period, unit_price, quantity, periods, subtotal"
        f" FROM {view} WHERE order_id = %s ORDER BY pub_id", (order_id,))


# ------------------------------------------------------------------ 订单列表
@bp.route("/orders")
@auth.login_required
def order_list():
    status = request.args.get("status", "").strip()
    kw = request.args.get("q", "").strip()
    extra, args = "", []
    if status:
        extra += " AND order_status = %s"
        args.append(status)
    if kw:
        view = _order_view()
        extra += (f" AND order_id IN (SELECT order_id FROM {view} d2"
                  "  WHERE d2.order_id LIKE %s OR d2.pub_name LIKE %s"
                  "  OR d2." + ("pub_name" if view == "v_user_orders" else "sub_name") +
                  " LIKE %s)")
        args += [f"%{kw}%"] * 3
    pg = _order_level_rows(extra, tuple(args))
    return render_template("orders.html", pg=pg, statuses=ORDER_STATUSES,
                           f_status=status, q=kw)


# ------------------------------------------------------------------ 新建订阅单
@bp.route("/orders/new", methods=["GET", "POST"])
@auth.role_required("订阅用户", "部门管理员")
def order_new():
    role = session["role"]
    pubs = db.query(
        "SELECT p.pub_id, p.pub_name, p.period, p.unit_price, c.cat_name"
        " FROM publication p JOIN category c ON c.cat_id = p.cat_id"
        " ORDER BY c.cat_id, p.pub_name")

    members = None
    if role == "部门管理员":
        members = db.query(
            "SELECT sub_id, sub_name, role FROM v_user_brief"
            " WHERE dept_name = %s ORDER BY role, sub_name", (session["dept_name"],))

    if request.method == "POST":
        guard = auth.check_csrf()
        if guard:
            return guard
        # 1. 确定下单人
        if role == "部门管理员":
            orderer = request.form.get("orderer_id", "").strip()
            if not members or not any(m["sub_id"] == orderer for m in members):
                flash("请选择本部门下单人员。", "error")
                return render_template("order_new.html", pubs=pubs, members=members,
                                       form=request.form, today=date.today())
        else:
            orderer = session["sub_id"]
        # 2. 日期校验（CHECK 约束要求 start >= sub_date 且 end > start）
        try:
            start = datetime.strptime(request.form["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            flash("请填写正确的起订/截止日期。", "error")
            return render_template("order_new.html", pubs=pubs, members=members,
                                   form=request.form, today=date.today())
        if start < date.today():
            flash("起订日期不能早于今天。", "error")
            return render_template("order_new.html", pubs=pubs, members=members,
                                   form=request.form, today=date.today())
        if end <= start:
            flash("截止日期必须晚于起订日期。", "error")
            return render_template("order_new.html", pubs=pubs, members=members,
                                   form=request.form, today=date.today())
        # 3. 明细行解析（同一报刊自动合并：份数累加、期数取后者）
        pub_ids = request.form.getlist("pub_id[]")
        qtys = request.form.getlist("quantity[]")
        periods = request.form.getlist("periods[]")
        merged = {}
        for pid, q, n in zip(pub_ids, qtys, periods):
            if not pid or not q or not n:
                continue
            try:
                qq, nn = int(q), int(n)
            except ValueError:
                continue
            if not (1 <= qq <= 999 and nn >= 1):
                continue
            if pid in merged:
                merged[pid]["quantity"] += qq      # 份数累加，期数取后者
                merged[pid]["periods"] = nn
            else:
                merged[pid] = {"quantity": qq, "periods": nn}
        if not merged:
            flash("请至少填写一行有效的订阅明细（选择报刊、份数、期数）。", "error")
            return render_template("order_new.html", pubs=pubs, members=members,
                                   form=request.form, today=date.today())
        # 4. 调用存储过程创建订阅单（事务 + 触发器自动计算金额）
        price_of = {p["pub_id"]: float(p["unit_price"]) for p in pubs}
        first = next(iter(merged))
        try:
            rows = db.call_proc("sp_place_order",
                                (orderer, start, end, first,
                                 merged[first]["quantity"], merged[first]["periods"]))
            order_id = rows[0][0]
            for pid, it in merged.items():
                if pid == first:
                    continue
                db.call_proc("sp_add_detail", (order_id, pid,
                                               it["quantity"], it["periods"]))
            est = sum(price_of.get(pid, 0) * it["quantity"] * it["periods"]
                      for pid, it in merged.items())
            write_log("下单", f"提交订阅单 {order_id}，{len(merged)} 种报刊，"
                              f"预计金额 {est:.2f} 元")
            flash(f"订阅单已提交：{order_id}（待系统管理员审核）。", "ok")
            return redirect(url_for("orders.order_detail", order_id=order_id))
        except Exception as e:
            flash_error(e)
    return render_template("order_new.html", pubs=pubs, members=members,
                           form={}, today=date.today())


# ------------------------------------------------------------------ 订单详情
@bp.route("/orders/<order_id>")
@auth.login_required
def order_detail(order_id):
    head = _order_head(order_id)
    if head is None:
        abort(403)
    details = _order_details(order_id)
    role = session["role"]
    own = (head.get("orderer_id") or session["sub_id"]) == session["sub_id"]
    is_dept_scope = (role == "部门管理员"
                     and head["dept_name"] == session["dept_name"])
    can_audit = (role == "系统管理员" and head["order_status"] == "待审核")
    can_cancel = (head["order_status"] == "已通过" and (own or is_dept_scope))
    can_add = (head["order_status"] == "待审核"
               and role in ("订阅用户", "部门管理员")
               and (own or is_dept_scope))
    pubs = db.query(
        "SELECT p.pub_id, p.pub_name, p.unit_price, p.period, c.cat_name"
        " FROM publication p JOIN category c ON c.cat_id=p.cat_id ORDER BY c.cat_id, p.pub_name")
    return render_template("order_detail.html", head=head, details=details,
                           can_audit=can_audit, can_cancel=can_cancel,
                           can_add=can_add, pubs=pubs)


# ------------------------------------------------------------------ 追加明细
@bp.route("/orders/<order_id>/add-detail", methods=["POST"])
@auth.role_required("订阅用户", "部门管理员")
def add_detail(order_id):
    guard = auth.check_csrf()
    if guard:
        return guard
    pub_id = request.form.get("pub_id", "")
    try:
        qty = int(request.form.get("quantity", "0"))
        periods = int(request.form.get("periods", "0"))
    except ValueError:
        flash("份数与期数必须为整数。", "error")
        return redirect(url_for("orders.order_detail", order_id=order_id))
    try:
        db.call_proc("sp_add_detail", (order_id, pub_id, qty, periods))
        write_log("下单", f"向订阅单 {order_id} 追加报刊 {pub_id}×{qty} 份×{periods} 期")
        flash("订阅明细已追加，金额已自动更新。", "ok")
    except Exception as e:
        flash_error(e)
    return redirect(url_for("orders.order_detail", order_id=order_id))


# ------------------------------------------------------------------ 退订
@bp.route("/orders/<order_id>/cancel", methods=["POST"])
@auth.role_required("订阅用户", "部门管理员")
def cancel(order_id):
    guard = auth.check_csrf()
    if guard:
        return guard
    head = _order_head(order_id)
    if head is None:
        abort(403)
    own = (head.get("orderer_id") or session["sub_id"]) == session["sub_id"]
    dept_scope = (session["role"] == "部门管理员"
                  and head["dept_name"] == session["dept_name"])
    if not (own or dept_scope):
        abort(403)
    orderer = head.get("orderer_id") or session["sub_id"]
    try:
        db.call_proc("sp_cancel_order", (order_id, orderer))
        write_log("退订", f"订阅单 {order_id} 已退订")
        flash(f"订阅单 {order_id} 已退订，历史记录保留。", "ok")
    except Exception as e:
        flash_error(e)
    return redirect(url_for("orders.order_detail", order_id=order_id))


# ------------------------------------------------------------------ 审核（系统管理员）
@bp.route("/audit")
@auth.role_required("系统管理员")
def audit_list():
    pg = paginate(
        "SELECT p.*, (SELECT COUNT(*) FROM subscription_detail det"
        "             WHERE det.order_id = p.order_id) AS items"
        " FROM v_pending_orders p ORDER BY p.sub_date, p.order_id",
        "SELECT COUNT(*) FROM v_pending_orders", (), per_page=10)
    return render_template("audit.html", pg=pg)


@bp.route("/audit/<order_id>", methods=["POST"])
@auth.role_required("系统管理员")
def audit(order_id):
    guard = auth.check_csrf()
    if guard:
        return guard
    action = request.form.get("action", "")
    comment = request.form.get("comment", "").strip()[:100]
    if action not in ("pass", "reject"):
        abort(400)
    try:
        db.call_proc("sp_audit_order",
                     (order_id, session["sub_id"], 1 if action == "pass" else 0,
                      comment or ("同意订阅" if action == "pass" else "不符合要求，驳回")))
        write_log("审核", f"订阅单 {order_id} {'审核通过' if action == 'pass' else '已驳回'}")
        flash(f"订阅单 {order_id} 已{'通过' if action == 'pass' else '驳回'}。", "ok")
    except Exception as e:
        flash_error(e)
    return redirect(url_for("orders.audit_list"))
