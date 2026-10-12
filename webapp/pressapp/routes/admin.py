# -*- coding: utf-8 -*-
"""基础数据管理（系统管理员）：部门 / 人员 / 类别 / 报刊 的增删改查，
以及操作日志查看与系统维护。所有列表页均含模糊查询。"""
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, session, url_for)

from .. import auth, db
from ..helpers import flash_error, friendly_error, paginate, write_log

bp = Blueprint("admin", __name__)


# ===================================================================== 部门
@bp.route("/departments")
@auth.role_required("系统管理员")
def departments():
    kw = request.args.get("q", "").strip()
    where, args = "", []
    if kw:
        where = " AND (d.dept_name LIKE %s OR d.location LIKE %s)"
        args = [f"%{kw}%"] * 2
    pg = paginate(
        "SELECT d.*, (SELECT COUNT(*) FROM subscriber s WHERE s.dept_id = d.dept_id)"
        " AS member_cnt FROM department d WHERE 1=1" + where + " ORDER BY d.dept_id",
        "SELECT COUNT(*) FROM department d WHERE 1=1" + where, tuple(args))
    return render_template("departments.html", pg=pg, q=kw)


@bp.route("/departments/new", methods=["GET", "POST"])
@auth.role_required("系统管理员")
def department_new():
    if request.method == "POST":
        guard = auth.check_csrf()
        if guard:
            return guard
        name = request.form.get("dept_name", "").strip()
        if not name:
            flash("部门名称不能为空。", "error")
        else:
            try:
                nxt = db.scalar(
                    "SELECT IFNULL(MAX(CAST(SUBSTRING(dept_id, 2) AS UNSIGNED)), 0) + 1"
                    " FROM department")
                dept_id = f"D{int(nxt):05d}"
                db.execute(
                    "INSERT INTO department (dept_id, dept_name, location, phone)"
                    " VALUES (%s, %s, %s, %s)",
                    (dept_id, name,
                     request.form.get("location", "").strip() or None,
                     request.form.get("phone", "").strip() or None))
                write_log("维护", f"新增部门 {dept_id} {name}")
                flash(f"部门已创建：{dept_id} {name}", "ok")
                return redirect(url_for("admin.departments"))
            except Exception as e:
                flash_error(e)
    return render_template("dept_form.html", dept=None)


@bp.route("/departments/<dept_id>/edit", methods=["GET", "POST"])
@auth.role_required("系统管理员")
def department_edit(dept_id):
    dept = db.query("SELECT * FROM department WHERE dept_id = %s", (dept_id,), one=True)
    if dept is None:
        abort(404)
    if request.method == "POST":
        guard = auth.check_csrf()
        if guard:
            return guard
        name = request.form.get("dept_name", "").strip()
        if not name:
            flash("部门名称不能为空。", "error")
        else:
            try:
                db.execute(
                    "UPDATE department SET dept_name=%s, location=%s, phone=%s"
                    " WHERE dept_id=%s",
                    (name, request.form.get("location", "").strip() or None,
                     request.form.get("phone", "").strip() or None, dept_id))
                write_log("维护", f"修改部门 {dept_id} {name}")
                flash("部门信息已保存。", "ok")
                return redirect(url_for("admin.departments"))
            except Exception as e:
                flash_error(e)
    return render_template("dept_form.html", dept=dept)


@bp.route("/departments/<dept_id>/delete", methods=["POST"])
@auth.role_required("系统管理员")
def department_delete(dept_id):
    guard = auth.check_csrf()
    if guard:
        return guard
    try:
        db.execute("DELETE FROM department WHERE dept_id = %s", (dept_id,))
        write_log("维护", f"删除部门 {dept_id}")
        flash("部门已删除。", "ok")
    except Exception as e:
        flash_error(e)
    return redirect(url_for("admin.departments"))


# ===================================================================== 人员
@bp.route("/subscribers")
@auth.role_required("系统管理员")
def subscribers():
    kw = request.args.get("q", "").strip()
    dept = request.args.get("dept", "").strip()
    role = request.args.get("role", "").strip()
    where, args = "", []
    if kw:
        where += " AND (s.sub_name LIKE %s OR s.username LIKE %s OR s.phone LIKE %s)"
        args += [f"%{kw}%"] * 3
    if dept:
        where += " AND d.dept_id = %s"
        args.append(dept)
    if role:
        where += " AND s.role = %s"
        args.append(role)
    pg = paginate(
        "SELECT s.*, d.dept_name FROM subscriber s JOIN department d"
        " ON d.dept_id = s.dept_id WHERE 1=1 " + where +
        " ORDER BY s.sub_id",
        "SELECT COUNT(*) FROM subscriber s JOIN department d"
        " ON d.dept_id = s.dept_id WHERE 1=1 " + where,
        tuple(args))
    depts = db.query("SELECT dept_id, dept_name FROM department ORDER BY dept_id")
    return render_template("subscribers.html", pg=pg, depts=depts,
                           q=kw, f_dept=dept, f_role=role)


@bp.route("/subscribers/new", methods=["GET", "POST"])
@auth.role_required("系统管理员")
def subscriber_new():
    depts = db.query("SELECT dept_id, dept_name FROM department ORDER BY dept_id")
    if request.method == "POST":
        guard = auth.check_csrf()
        if guard:
            return guard
        f = {k: request.form.get(k, "").strip() for k in
             ("sub_name", "gender", "phone", "address", "dept_id", "username",
              "password", "role")}
        if not (f["sub_name"] and f["dept_id"] and f["username"]):
            flash("姓名、部门、用户名为必填项。", "error")
        elif not re.fullmatch(r"[A-Za-z0-9_]{2,20}", f["username"]):
            flash("用户名仅限字母、数字与下划线（2~20 位）。", "error")
        else:
            try:
                from .. import auth as _auth
                nxt = db.scalar(
                    "SELECT IFNULL(MAX(CAST(SUBSTRING(sub_id, 4) AS UNSIGNED)), 0) + 1"
                    " FROM subscriber")
                sub_id = f"EMP{int(nxt):05d}"
                pwd = _auth.digest(f["password"] or "123456")
                db.execute(
                    "INSERT INTO subscriber (sub_id, sub_name, gender, phone, address,"
                    " dept_id, username, password, role)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (sub_id, f["sub_name"], f["gender"] or None, f["phone"] or None,
                     f["address"] or None, f["dept_id"], f["username"], pwd,
                     f["role"] or "订阅用户"))
                write_log("维护", f"新增人员 {sub_id} {f['sub_name']}（{f['role']}）")
                flash(f"人员已创建：{sub_id} {f['sub_name']}，初始口令 "
                      f"{f['password'] or '123456'}", "ok")
                return redirect(url_for("admin.subscribers"))
            except Exception as e:
                flash_error(e)
    return render_template("sub_form.html", sub=None, depts=depts)


@bp.route("/subscribers/<sub_id>/edit", methods=["GET", "POST"])
@auth.role_required("系统管理员")
def subscriber_edit(sub_id):
    sub = db.query("SELECT * FROM subscriber WHERE sub_id = %s", (sub_id,), one=True)
    if sub is None:
        abort(404)
    depts = db.query("SELECT dept_id, dept_name FROM department ORDER BY dept_id")
    if request.method == "POST":
        guard = auth.check_csrf()
        if guard:
            return guard
        try:
            db.execute(
                "UPDATE subscriber SET sub_name=%s, gender=%s, phone=%s, address=%s,"
                " dept_id=%s, username=%s, role=%s WHERE sub_id=%s",
                (request.form.get("sub_name", "").strip(),
                 request.form.get("gender") or None,
                 request.form.get("phone", "").strip() or None,
                 request.form.get("address", "").strip() or None,
                 request.form.get("dept_id"),
                 request.form.get("username", "").strip(),
                 request.form.get("role", "订阅用户"), sub_id))
            write_log("维护", f"修改人员 {sub_id}")
            flash("人员信息已保存。", "ok")
            return redirect(url_for("admin.subscribers"))
        except Exception as e:
            flash_error(e)
    return render_template("sub_form.html", sub=sub, depts=depts)


@bp.route("/subscribers/<sub_id>/reset-pwd", methods=["POST"])
@auth.role_required("系统管理员")
def subscriber_reset(sub_id):
    guard = auth.check_csrf()
    if guard:
        return guard
    try:
        from .. import auth as _auth
        db.execute("UPDATE subscriber SET password = %s WHERE sub_id = %s",
                   (_auth.digest("123456"), sub_id))
        write_log("维护", f"重置人员 {sub_id} 登录口令")
        flash(f"口令已重置为 123456（{sub_id}）。", "ok")
    except Exception as e:
        flash_error(e)
    return redirect(url_for("admin.subscribers"))


@bp.route("/subscribers/<sub_id>/delete", methods=["POST"])
@auth.role_required("系统管理员")
def subscriber_delete(sub_id):
    guard = auth.check_csrf()
    if guard:
        return guard
    try:
        db.execute("DELETE FROM subscriber WHERE sub_id = %s", (sub_id,))
        write_log("维护", f"删除人员 {sub_id}")
        flash("人员已删除。", "ok")
    except Exception as e:
        flash_error(e)
    return redirect(url_for("admin.subscribers"))


# ===================================================================== 类别
@bp.route("/categories")
@auth.role_required("系统管理员")
def categories():
    kw = request.args.get("q", "").strip()
    where, args = "", []
    if kw:
        where = " AND (c.cat_name LIKE %s OR c.cat_desc LIKE %s)"
        args = [f"%{kw}%"] * 2
    pg = paginate(
        "SELECT c.*, (SELECT COUNT(*) FROM publication p WHERE p.cat_id = c.cat_id)"
        " AS pub_cnt FROM category c WHERE 1=1" + where + " ORDER BY c.cat_id",
        "SELECT COUNT(*) FROM category c WHERE 1=1" + where, tuple(args))
    return render_template("categories.html", pg=pg, q=kw)


def _category_save(cat=None):
    name = request.form.get("cat_name", "").strip()
    desc = request.form.get("cat_desc", "").strip() or None
    if not name:
        flash("类别名称不能为空。", "error")
        return False
    try:
        if cat:
            db.execute("UPDATE category SET cat_name=%s, cat_desc=%s WHERE cat_id=%s",
                       (name, desc, cat["cat_id"]))
            write_log("维护", f"修改报刊类别 {cat['cat_id']} {name}")
        else:
            nxt = db.scalar(
                "SELECT IFNULL(MAX(CAST(SUBSTRING(cat_id, 2) AS UNSIGNED)), 0) + 1"
                " FROM category")
            cat_id = f"C{int(nxt):03d}"
            db.execute("INSERT INTO category VALUES (%s,%s,%s)", (cat_id, name, desc))
            write_log("维护", f"新增报刊类别 {cat_id} {name}")
        flash("类别已保存。", "ok")
        return True
    except Exception as e:
        flash_error(e)
        return False


@bp.route("/categories/new", methods=["GET", "POST"])
@auth.role_required("系统管理员")
def category_new():
    if request.method == "POST":
        guard = auth.check_csrf()
        if guard:
            return guard
        if _category_save():
            return redirect(url_for("admin.categories"))
    return render_template("cat_form.html", cat=None)


@bp.route("/categories/<cat_id>/edit", methods=["GET", "POST"])
@auth.role_required("系统管理员")
def category_edit(cat_id):
    cat = db.query("SELECT * FROM category WHERE cat_id=%s", (cat_id,), one=True)
    if cat is None:
        abort(404)
    if request.method == "POST":
        guard = auth.check_csrf()
        if guard:
            return guard
        if _category_save(cat):
            return redirect(url_for("admin.categories"))
    return render_template("cat_form.html", cat=cat)


@bp.route("/categories/<cat_id>/delete", methods=["POST"])
@auth.role_required("系统管理员")
def category_delete(cat_id):
    guard = auth.check_csrf()
    if guard:
        return guard
    try:
        db.execute("DELETE FROM category WHERE cat_id = %s", (cat_id,))
        write_log("维护", f"删除报刊类别 {cat_id}")
        flash("类别已删除。", "ok")
    except Exception as e:
        flash_error(e)
    return redirect(url_for("admin.categories"))


# ===================================================================== 报刊
@bp.route("/publications")
@auth.role_required("系统管理员", "部门管理员", "订阅用户")
def publications():
    kw = request.args.get("q", "").strip()
    cat = request.args.get("cat", "").strip()
    period = request.args.get("period", "").strip()
    where, args = "", []
    if kw:
        where += " AND (p.pub_name LIKE %s OR p.publisher LIKE %s)"
        args += [f"%{kw}%"] * 2
    if cat:
        where += " AND p.cat_id = %s"
        args.append(cat)
    if period:
        where += " AND p.period = %s"
        args.append(period)
    pg = paginate(
        "SELECT p.*, c.cat_name, s.sub_name AS maintainer_name"
        " FROM publication p JOIN category c ON c.cat_id = p.cat_id"
        " LEFT JOIN subscriber s ON s.sub_id = p.maintainer"
        " WHERE 1=1" + where + " ORDER BY p.pub_id",
        "SELECT COUNT(*) FROM publication p WHERE 1=1" + where, tuple(args))
    cats = db.query("SELECT cat_id, cat_name FROM category ORDER BY cat_id")
    return render_template("publications.html", pg=pg, cats=cats,
                           q=kw, f_cat=cat, f_period=period,
                           is_admin=session["role"] == "系统管理员")


def _publication_save(pub=None):
    f = {k: request.form.get(k, "").strip() for k in
         ("pub_name", "cat_id", "period", "unit_price", "publisher", "maintainer")}
    if not (f["pub_name"] and f["cat_id"] and f["period"] and f["unit_price"]):
        flash("报刊名称、类别、刊期、单价为必填项。", "error")
        return
    try:
        price = float(f["unit_price"])
        if price <= 0:
            raise ValueError
    except ValueError:
        flash("单价必须为正数。", "error")
        return
    try:
        if pub:
            db.execute(
                "UPDATE publication SET pub_name=%s, cat_id=%s, period=%s,"
                " unit_price=%s, publisher=%s, maintainer=%s WHERE pub_id=%s",
                (f["pub_name"], f["cat_id"], f["period"], price,
                 f["publisher"] or None, f["maintainer"] or None, pub["pub_id"]))
            write_log("维护", f"修改报刊 {pub['pub_id']} {f['pub_name']}")
        else:
            nxt = db.scalar(
                "SELECT IFNULL(MAX(CAST(SUBSTRING(pub_id, 2) AS UNSIGNED)), 0) + 1"
                " FROM publication")
            pub_id = f"P{int(nxt):07d}"
            db.execute(
                "INSERT INTO publication (pub_id, pub_name, cat_id, period,"
                " unit_price, publisher, maintainer) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (pub_id, f["pub_name"], f["cat_id"], f["period"], price,
                 f["publisher"] or None, f["maintainer"] or None))
            write_log("维护", f"新增报刊 {pub_id} {f['pub_name']}")
        flash("报刊信息已保存。", "ok")
    except Exception as e:
        flash_error(e)


@bp.route("/publications/new", methods=["GET", "POST"])
@auth.role_required("系统管理员")
def publication_new():
    if request.method == "POST":
        guard = auth.check_csrf()
        if guard:
            return guard
        _publication_save()
        return redirect(url_for("admin.publications"))
    cats = db.query("SELECT cat_id, cat_name FROM category ORDER BY cat_id")
    admins = db.query(
        "SELECT sub_id, sub_name FROM subscriber WHERE role='系统管理员' ORDER BY sub_id")
    return render_template("pub_form.html", pub=None, cats=cats, admins=admins)


@bp.route("/publications/<pub_id>/edit", methods=["GET", "POST"])
@auth.role_required("系统管理员")
def publication_edit(pub_id):
    pub = db.query("SELECT * FROM publication WHERE pub_id=%s", (pub_id,), one=True)
    if pub is None:
        abort(404)
    if request.method == "POST":
        guard = auth.check_csrf()
        if guard:
            return guard
        _publication_save(pub)
        return redirect(url_for("admin.publications"))
    cats = db.query("SELECT cat_id, cat_name FROM category ORDER BY cat_id")
    admins = db.query(
        "SELECT sub_id, sub_name FROM subscriber WHERE role='系统管理员' ORDER BY sub_id")
    return render_template("pub_form.html", pub=pub, cats=cats, admins=admins)


@bp.route("/publications/<pub_id>/delete", methods=["POST"])
@auth.role_required("系统管理员")
def publication_delete(pub_id):
    guard = auth.check_csrf()
    if guard:
        return guard
    try:
        db.execute("DELETE FROM publication WHERE pub_id = %s", (pub_id,))
        write_log("维护", f"删除报刊 {pub_id}")
        flash("报刊已删除。", "ok")
    except Exception as e:
        flash_error(e)
    return redirect(url_for("admin.publications"))


# ===================================================================== 日志
@bp.route("/members")
@auth.role_required("部门管理员")
def members():
    """本部门人员名册（只读，来自 v_user_brief，不暴露登录凭据）。"""
    mine = session["dept_name"]
    kw = request.args.get("q", "").strip()
    where, args = " WHERE dept_name = %s", [mine]
    if kw:
        where += " AND (sub_name LIKE %s OR phone LIKE %s)"
        args += [f"%{kw}%"] * 2
    pg = paginate(
        "SELECT * FROM v_user_brief" + where + " ORDER BY role, sub_id",
        "SELECT COUNT(*) FROM v_user_brief" + where, tuple(args))
    total_amount = db.scalar(
        "SELECT COUNT(*) FROM v_user_brief WHERE dept_name = %s", (mine,))
    return render_template("members.html", pg=pg, q=kw, mine=mine, cnt=total_amount)


@bp.route("/logs")
@auth.role_required("系统管理员")
def logs():
    kw = request.args.get("q", "").strip()
    op = request.args.get("op", "").strip()
    day = request.args.get("day", "").strip()
    where, args = "", []
    if kw:
        where += " AND (l.op_content LIKE %s OR s.sub_name LIKE %s)"
        args += [f"%{kw}%"] * 2
    if op:
        where += " AND l.op_type = %s"
        args.append(op)
    if day:
        where += " AND DATE(l.op_time) = %s"
        args.append(day)
    pg = paginate(
        "SELECT l.*, s.sub_name FROM op_log l"
        " LEFT JOIN subscriber s ON s.sub_id = l.sub_id"
        " WHERE 1=1" + where + " ORDER BY l.op_time DESC, l.log_id DESC",
        "SELECT COUNT(*) FROM op_log l LEFT JOIN subscriber s ON s.sub_id = l.sub_id"
        " WHERE 1=1" + where, tuple(args), per_page=15)
    return render_template("logs.html", pg=pg, q=kw, f_op=op, f_day=day)


# ===================================================================== 系统维护
@bp.route("/maintenance")
@auth.role_required("系统管理员")
def maintenance():
    info = {
        "version": db.scalar("SELECT VERSION()"),
        "tables": db.query(
            "SELECT table_name AS tname, table_rows AS trows,"
            " ROUND(data_length/1024) AS kb, table_comment AS tcomment"
            " FROM information_schema.tables"
            " WHERE table_schema = 'press_sub_db' ORDER BY table_name"),
        "views": [r["v"] for r in db.query(
            "SELECT table_name AS v FROM information_schema.views"
            " WHERE table_schema='press_sub_db' ORDER BY 1")],
        "routines": db.query(
            "SELECT routine_name AS rname, routine_type AS rtype"
            " FROM information_schema.routines"
            " WHERE routine_schema='press_sub_db' ORDER BY routine_type, routine_name"),
        "triggers": db.query(
            "SELECT trigger_name AS tname, event_object_table AS ttable,"
            " action_timing AS timing, event_manipulation AS event"
            " FROM information_schema.triggers"
            " WHERE trigger_schema='press_sub_db' ORDER BY trigger_name"),
    }
    info["user"] = db.query("SELECT CURRENT_USER() AS u", one=True)["u"]
    return render_template("maintenance.html", info=info)


@bp.route("/maintenance/backup", methods=["POST"])
@auth.role_required("系统管理员")
def backup():
    guard = auth.check_csrf()
    if guard:
        return guard
    backup_dir = Path(__file__).resolve().parents[2] / "backups"
    backup_dir.mkdir(exist_ok=True)
    dump = shutil.which("mysqldump")
    if not dump:
        flash("未找到 mysqldump 命令。请在 MySQL bin 目录下执行："
              "mysqldump -uroot -p press_sub_db > press_sub_db_backup.sql", "error")
        return redirect(url_for("admin.maintenance"))
    target = backup_dir / f"press_sub_db_{datetime.now():%Y%m%d_%H%M%S}.sql"
    from .. import config
    cfg = config.mysql_base()
    cmd = [dump, f"-h{cfg['host']}", f"-P{cfg['port']}", f"-u{cfg['user']}",
           f"-p{cfg['password']}", "--default-character-set=utf8mb4", "press_sub_db"]
    try:
        with open(target, "w", encoding="utf-8") as fh:
            subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE,
                           timeout=120, check=True)
        write_log("维护", f"执行数据库备份 {target.name}")
        flash(f"备份完成：backups/{target.name}", "ok")
    except Exception as e:
        flash(f"备份失败：{friendly_error(e)}", "error")
    return redirect(url_for("admin.maintenance"))
