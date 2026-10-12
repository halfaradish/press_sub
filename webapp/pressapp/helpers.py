# -*- coding: utf-8 -*-
"""通用辅助：错误翻译、操作日志、分页、格式化。"""
import pymysql
from flask import flash, g, session

from . import db

# 常见 MySQL 错误码 → 面向用户的中文提示
_ERROR_TEXT = {
    1062: "唯一性冲突：{raw}",
    1451: "该记录已被其他数据引用（如存在订阅明细/人员/报刊），请先处理关联数据。",
    1452: "关联数据不存在（部门/人员/报刊编号有误）。",
    3819: "数据不符合完整性约束：{raw}",
    3888: "数据不符合完整性约束：{raw}",
    1264: "数值超出字段范围。",
    1406: "内容长度超出字段限制。",
    1048: "必填字段不能为空。",
}


def friendly_error(e: Exception) -> str:
    """把 pymysql 异常翻译成界面可读提示（SIGNAL 的业务提示原样透出）。"""
    if isinstance(e, pymysql.err.MySQLError):
        code = e.args[0] if e.args else 0
        raw = e.args[1] if len(e.args) > 1 else str(e)
        if code == 1644:                      # SIGNAL SQLSTATE '45000'
            return raw
        text = _ERROR_TEXT.get(code)
        if text:
            return text.format(raw=raw)
        return f"数据库操作失败（错误码 {code}）：{raw}"
    return str(e)


def flash_error(e: Exception):
    flash(friendly_error(e), "error")


def write_log(op_type: str, content: str):
    """写入操作日志（失败不阻断业务）。"""
    try:
        db.execute(
            "INSERT INTO op_log (sub_id, op_type, op_content) VALUES (%s, %s, %s)",
            (session.get("sub_id"), op_type, content[:200]))
    except Exception:
        pass


def page_args(per_page: int = 12) -> dict:
    """解析 page 参数并计算 LIMIT 偏移。"""
    try:
        page = max(1, int(request_page()))
    except (TypeError, ValueError):
        page = 1
    return {"page": page, "per_page": per_page, "offset": (page - 1) * per_page}


def request_page():
    from flask import request
    return request.args.get("page", 1)


def paginate(sql_body: str, count_sql: str, params: tuple, per_page: int = 12) -> dict:
    """统一分页查询：sql_body 以 ORDER BY 结尾，LIMIT 由本函数追加在末尾。"""
    pg = page_args(per_page)
    total = db.scalar(count_sql, params) or 0
    rows = db.query(sql_body + f" LIMIT {pg['per_page']} OFFSET {pg['offset']}", params)
    pages = max(1, -(-int(total) // per_page))
    pg["total"] = int(total)
    pg["pages"] = pages
    pg["rows"] = rows
    return pg


STATUS_CLASS = {"待审核": "st-wait", "已通过": "st-pass",
                "已驳回": "st-reject", "已退订": "st-cancelled"}


def status_class(status: str) -> str:
    return STATUS_CLASS.get(status, "st-wait")


def money(value) -> str:
    """金额格式化：千分位 + 两位小数。"""
    if value is None:
        return "0.00"
    return f"{float(value):,.2f}"


def dt(value, fmt: str = "%Y-%m-%d") -> str:
    return value.strftime(fmt) if value else "—"
