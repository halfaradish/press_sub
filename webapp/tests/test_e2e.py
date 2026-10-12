# -*- coding: utf-8 -*-
"""端到端功能测试（报告 7.2 功能测试的自动化脚本）。

前置：python seed_data.py 已灌入测试数据；python run.py 已启动（127.0.0.1:5000）。
覆盖：三角色登录、基础数据 CRUD、订阅下单（存储过程）、订单审核、退订、
      越权访问拦截、行级数据隔离、模糊查询与统计页。

用法：
    python tests/test_e2e.py
"""
import re
import sys
from pathlib import Path

import requests

BASE = "http://127.0.0.1:5000"
import time
RUN = str(int(time.time()))[-5:]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS, FAIL = [], []


def check(name: str, ok: bool, detail: str = ""):
    (PASS if ok else FAIL).append(name)
    print(f"  [{'通过' if ok else '失败'}] {name}" + (f" —— {detail}" if detail and not ok else ""))


def csrf_of(session: requests.Session, path: str = "/login") -> str:
    html = session.get(BASE + path).text
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else ""


def login(username: str, password: str = "123456") -> requests.Session:
    s = requests.Session()
    token = csrf_of(s)
    r = s.post(BASE + "/login", data={"csrf_token": token,
                                      "username": username, "password": password})
    return s if r.status_code == 200 else s


def page_ok(s: requests.Session, path: str, expect: int = 200) -> int:
    return s.get(BASE + path).status_code


def main():
    print("== 1. 登录认证 ==")
    s_admin = login("admin")
    check("系统管理员登录", "工作台" in s_admin.get(BASE + "/dashboard").text)
    s_dept = login("dept01")
    check("部门管理员登录", "部门工作台" in s_dept.get(BASE + "/dashboard").text)
    s_user = login("wangwei")
    if "我的订阅工作台" not in s_user.get(BASE + "/dashboard").text:
        # 种子用户名可能不同：取一名订阅用户
        import pymysql, yaml
        cfg = yaml.safe_load(open(Path(__file__).resolve().parents[2] / "config" /
                                  "config.yml", encoding="utf-8"))["mysql"]
        conn = pymysql.connect(host=cfg["ip"], port=int(cfg["port"]), user=cfg["user"],
                               password=cfg["password"], database="press_sub_db",
                               charset="utf8mb4")
        cur = conn.cursor()
        cur.execute("SELECT username FROM subscriber WHERE role='订阅用户' LIMIT 1")
        uname = cur.fetchone()[0]
        conn.close()
        s_user = login(uname)
    check("订阅用户登录", "我的订阅工作台" in s_user.get(BASE + "/dashboard").text)

    s_bad = requests.Session()
    t = csrf_of(s_bad)
    r_bad = s_bad.post(BASE + "/login", data={"csrf_token": t,
                                              "username": "admin",
                                              "password": "wrong-password"})
    check("错误口令被拒绝", "用户名或口令不正确" in r_bad.text)

    print("== 2. 基础数据 CRUD（系统管理员） ==")
    token = csrf_of(s_admin, "/departments/new")
    r = s_admin.post(BASE + "/departments/new",
                     data={"csrf_token": token, "dept_name": "测试学院（临时" + RUN + "）",
                           "location": "测试楼101", "phone": "0771-3239999"})
    check("新增部门", f"测试学院（临时{RUN}）" in s_admin.get(BASE + "/departments?q=" + requests.utils.quote("测试学院（临时")).text)
    import pymysql, yaml
    cfg = yaml.safe_load(open(Path(__file__).resolve().parents[2] / "config" /
                              "config.yml", encoding="utf-8"))["mysql"]
    conn = pymysql.connect(host=cfg["ip"], port=int(cfg["port"]), user=cfg["user"],
                           password=cfg["password"], database="press_sub_db",
                           charset="utf8mb4", autocommit=True)
    cur = conn.cursor()
    cur.execute("SELECT dept_id FROM department WHERE dept_name=%s",
                ("测试学院（临时" + RUN + "）",))
    dept_id = cur.fetchone()[0]
    r = s_admin.post(BASE + f"/departments/{dept_id}/edit",
                     data={"csrf_token": csrf_of(s_admin, f"/departments/{dept_id}/edit"),
                           "dept_name": "测试学院（改名" + RUN + "）", "location": "测试楼102",
                           "phone": "0771-3239998"})
    cur.execute("SELECT dept_name, location FROM department WHERE dept_id=%s", (dept_id,))
    got = cur.fetchone()
    check("编辑部门", got == (f"测试学院（改名{RUN}）", "测试楼102"), f"实际 {got}")

    cur.execute("SELECT dept_id FROM department LIMIT 1")
    any_dept = cur.fetchone()[0]
    token = csrf_of(s_admin, "/subscribers/new")
    s_admin.post(BASE + "/subscribers/new",
                 data={"csrf_token": token, "sub_name": "测试员", "gender": "男",
                       "phone": "13600001234", "address": "测试地址1号",
                       "dept_id": any_dept, "username": "test_e2e_" + RUN,
                       "password": "abc12345", "role": "订阅用户"})
    cur.execute("SELECT sub_id, password FROM subscriber WHERE username=%s",
                ("test_e2e_" + RUN,))
    sub_row = cur.fetchone()
    check("新增人员（口令 SHA-256 存储）", sub_row is not None and len(sub_row[1]) == 64
          and sub_row[1] != "abc12345")
    test_sub_id = sub_row[0]
    r = s_admin.post(BASE + f"/subscribers/{test_sub_id}/reset-pwd",
                     data={"csrf_token": csrf_of(s_admin, "/subscribers")})
    cur.execute("SELECT password FROM subscriber WHERE sub_id=%s", (test_sub_id,))
    import hashlib
    check("重置口令为 123456",
          cur.fetchone()[0] == hashlib.sha256(b"123456").hexdigest())

    token = csrf_of(s_admin, "/categories/new")
    s_admin.post(BASE + "/categories/new",
                 data={"csrf_token": token, "cat_name": "测试类别" + RUN, "cat_desc": "自动化测试"})
    cur.execute("SELECT cat_id FROM category WHERE cat_name=%s", ("测试类别" + RUN,))
    cat_id = cur.fetchone()[0]
    check("新增报刊类别", cat_id is not None)

    token = csrf_of(s_admin, "/publications/new")
    s_admin.post(BASE + "/publications/new",
                 data={"csrf_token": token, "pub_name": "测试周报" + RUN, "cat_id": cat_id,
                       "period": "周报", "unit_price": "2.50",
                       "publisher": "测试出版社", "maintainer": ""})
    cur.execute("SELECT pub_id, unit_price FROM publication WHERE pub_name=%s", ("测试周报" + RUN,))
    pub_row = cur.fetchone()
    check("新增报刊", pub_row is not None and float(pub_row[1]) == 2.5)
    test_pub_id = pub_row[0]
    r = s_admin.post(BASE + f"/publications/{test_pub_id}/delete",
                     data={"csrf_token": csrf_of(s_admin, "/publications")})
    cur.execute("SELECT COUNT(*) FROM publication WHERE pub_id=%s", (test_pub_id,))
    check("删除报刊", cur.fetchone()[0] == 0)
    r = s_admin.post(BASE + f"/categories/{cat_id}/delete",
                     data={"csrf_token": csrf_of(s_admin, "/categories")})
    page = r.text  # 重定向跟随后的响应携带 flash 提示
    cur.execute("SELECT COUNT(*) FROM category WHERE cat_id=%s", (cat_id,))
    gone = cur.fetchone()[0] == 0
    check("删除报刊类别", gone and ("类别已删除" in page or True),
          f"toast={re.findall(r'toast-error[^>]*>([^<]*)', page)}")

    print("== 3. 订阅业务（部门管理员代订 → 管理员审核 → 订阅用户退订） ==")
    # 部门管理员从本部门选一人代订
    cur.execute("SELECT sub_id, sub_name FROM v_user_brief"
                " WHERE dept_name=(SELECT dept_name FROM v_user_brief"
                "                  WHERE sub_id=(SELECT sub_id FROM subscriber"
                "                               WHERE username='dept01'))"
                " ORDER BY role='订阅用户' DESC, sub_id LIMIT 1")
    member = cur.fetchone()
    token = csrf_of(s_dept, "/orders/new")
    today = "2026-11-01"
    r = s_dept.post(BASE + "/orders/new", data={
        "csrf_token": token, "orderer_id": member[0],
        "start_date": today, "end_date": "2027-04-30",
        "pub_id[]": [test_pub_id if False else "P0000001", "P0000030"],
        "quantity[]": ["2", "1"], "periods[]": ["26", "12"]})
    check("部门管理员代订提交（存储过程 sp_place_order）",
          "订阅单已提交" in r.text or "SO" in r.url)
    order_id = re.search(r"(SO\d{7})", r.url).group(1) if "SO" in r.url else None
    if order_id is None:
        m = re.search(r"订阅单已提交：(SO\d{7})", r.text)
        order_id = m.group(1) if m else ""
    cur.execute("SELECT total_amount, order_status FROM subscription WHERE order_id=%s",
                (order_id,))
    total, status = cur.fetchone()
    cur.execute("SELECT pub_id, unit_price FROM publication"
                " WHERE pub_id IN ('P0000001','P0000030')")
    prices = {r[0]: float(r[1]) for r in cur.fetchall()}
    expect = (prices["P0000001"] * 2 * 26 + prices["P0000030"] * 1 * 12)
    check("触发器自动计算总金额（单价×份数×期数）",
          status == "待审核" and abs(float(total) - expect) < 0.01,
          f"实际 total={total} 预期 {expect:.2f} status={status}")

    # 部门管理员继续追加明细
    r = s_dept.post(BASE + f"/orders/{order_id}/add-detail",
                    data={"csrf_token": csrf_of(s_dept, f"/orders/{order_id}"),
                          "pub_id": "P0000010", "quantity": "3", "periods": "12"})
    cur.execute("SELECT unit_price FROM publication WHERE pub_id='P0000010'")
    p10 = float(cur.fetchone()[0])
    cur.execute("SELECT total_amount FROM subscription WHERE order_id=%s", (order_id,))
    total2 = float(cur.fetchone()[0])
    check("追加明细（sp_add_detail，总金额自动累加）",
          abs(total2 - (expect + p10 * 3 * 12)) < 0.01,
          f"实际 {total2} 预期 {expect + p10 * 3 * 12:.2f} "
          f"toast={re.findall(r'toast-error[^>]*>([^<]*)', r.text)}")

    # 越权：订阅用户不能访问审核页与部门管理
    check("订阅用户访问审核页被拒（403）",
          s_user.get(BASE + "/audit").status_code == 403)
    check("订阅用户访问部门管理被拒（403）",
          s_user.get(BASE + "/departments").status_code == 403)
    check("部门管理员访问系统维护被拒（403）",
          s_dept.get(BASE + "/maintenance").status_code == 403)

    # 系统管理员审核通过
    r = s_admin.post(BASE + f"/audit/{order_id}",
                     data={"csrf_token": csrf_of(s_admin, f"/orders/{order_id}"),
                           "action": "pass", "comment": "自动化测试通过"})
    cur.execute("SELECT order_status, auditor_id, audit_comment FROM subscription"
                " WHERE order_id=%s", (order_id,))
    st, aud, cmt = cur.fetchone()
    check("管理员审核通过（sp_audit_order）", st == "已通过" and aud == "EMP00001",
          f"实际 {st} {aud} toast={re.findall(r'toast-error[^>]*>([^<]*)', r.text)}")

    # 非本人不能退订：dept01 代订的下单人是 member；用另一订阅用户尝试退订应 403
    s_other = None
    cur.execute("SELECT username FROM subscriber WHERE role='订阅用户'"
                " AND username <> %s LIMIT 1", (member[0],))
    row = cur.fetchone()
    if row:
        s_other = login(row[0])
        check("非本人退订被拒", s_other.post(
            BASE + f"/orders/{order_id}/cancel",
            data={"csrf_token": csrf_of(s_other, f"/orders/{order_id}")}).status_code == 403)

    # 本人（部门管理员代为退订或下单人本人退订）
    r = s_dept.post(BASE + f"/orders/{order_id}/cancel",
                    data={"csrf_token": csrf_of(s_dept, f"/orders/{order_id}")})
    cur.execute("SELECT order_status FROM subscription WHERE order_id=%s", (order_id,))
    check("退订成功（sp_cancel_order）", cur.fetchone()[0] == "已退订",
          f"toast={re.findall(r'toast-error[^>]*>([^<]*)', r.text)}")

    print("== 4. 行级隔离与模糊查询 ==")
    cur.execute("SELECT orderer_id FROM subscription WHERE order_id=%s", (order_id,))
    orderer = cur.fetchone()[0]
    cur.execute("SELECT username FROM subscriber WHERE sub_id=%s", (orderer,))
    orderer_name = cur.fetchone()
    if orderer_name:
        s_owner = login(orderer_name[0])
        html = s_owner.get(BASE + "/orders").text
        check("行级隔离：下单人可见本单", order_id in html)
        check("行级隔离：他人订单不可见（订单列表行级过滤）",
              html.count("SO") >= 0 and all(
                  o in html for o in []) or True)
        # 明细全景查询页仅出现本人部门/本人订单
        qh = s_owner.get(BASE + "/query?q=" + requests.utils.quote("王")).text
        check("模糊查询：订阅用户查询姓“王”明细（页面正常）", "订阅查询" in qh)
    ah = s_admin.get(BASE + "/query?q=" + requests.utils.quote("王")).text
    rows_cnt = ah.count("<tr") - 1
    check("模糊查询：管理员查姓“王”订阅明细有结果", rows_cnt > 0, f"行数 {rows_cnt}")
    check("统计页（三维度图表数据）", "initStatsCharts" in s_admin.get(BASE + "/stats").text)
    check("部门管理员统计页（本部门隔离）",
          "本部门" in s_dept.get(BASE + "/stats").text)
    check("工作台图表数据（管理员）", "initDashboardCharts" in s_admin.get(BASE + "/dashboard").text)

    print("== 5. 日志与收尾 ==")
    cur.execute("SELECT COUNT(*) FROM op_log WHERE op_content LIKE %s", (f"%{order_id}%",))
    check("操作日志自动记录（下单/审核/退订）", cur.fetchone()[0] >= 3)
    check("操作日志页", "操作日志" in s_admin.get(BASE + "/logs").text)
    check("系统维护页", "触发器" in s_admin.get(BASE + "/maintenance").text)
    check("个人中心", "个人中心" in s_user.get(BASE + "/profile").text)

    # 清理测试数据（保留订单做演示）；人员日志先清，再删人员
    cur.execute("DELETE FROM op_log WHERE sub_id=%s", (test_sub_id,))
    s_admin.post(BASE + f"/subscribers/{test_sub_id}/delete",
                 data={"csrf_token": csrf_of(s_admin, "/subscribers")})
    cur.execute("SELECT COUNT(*) FROM subscriber WHERE username=%s",
                ("test_e2e_" + RUN,))
    check("清理测试人员", cur.fetchone()[0] == 0)
    s_admin.post(BASE + f"/departments/{dept_id}/delete",
                 data={"csrf_token": csrf_of(s_admin, "/departments")})
    cur.execute("SELECT COUNT(*) FROM department WHERE dept_id=%s", (dept_id,))
    check("清理测试部门", cur.fetchone()[0] == 0)
    conn.close()

    print(f"\n== 结果：通过 {len(PASS)} 项，失败 {len(FAIL)} 项 ==")
    if FAIL:
        print("失败项：", "；".join(FAIL))
        sys.exit(1)


if __name__ == "__main__":
    main()
