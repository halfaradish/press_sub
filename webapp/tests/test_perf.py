# -*- coding: utf-8 -*-
"""性能测试脚本（报告 7.3 性能测试，选做加分项）。

测试环境：本机 MySQL 8.0.40 + Flask 开发服务器（127.0.0.1:5000）。
测试内容：
  A. 典型页面响应时间（HTTP 层，各 30 次取样：均值 / P95）
  B. 数据库层典型 SQL 响应时间（各 50 次取样）
  C. 并发查询（20 线程 × 5 请求）成功率与吞吐
  D. 并发下单（10 线程同时调用 sp_place_order）取号唯一性验证

用法：先启动 python run.py，再运行 python tests/test_perf.py
"""
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymysql
import requests
import re
import yaml

BASE = "http://127.0.0.1:5000"
ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def pct(values, p):
    vals = sorted(values)
    idx = min(len(vals) - 1, int(round(p / 100 * (len(vals) - 1))))
    return vals[idx]


def bench(fn, n, warmup=3):
    for _ in range(warmup):
        fn()
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000)
    return {"avg": statistics.mean(ts), "p95": pct(ts, 95),
            "min": min(ts), "max": max(ts)}


def login_session(username="admin", password="123456"):
    s = requests.Session()
    html = s.get(BASE + "/login").text
    token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    s.post(BASE + "/login", data={"csrf_token": token, "username": username,
                                  "password": password})
    return s


def http_tests():
    s = login_session()
    pages = {
        "登录页 GET /login": lambda: requests.get(BASE + "/login"),
        "工作台 GET /dashboard": lambda: s.get(BASE + "/dashboard"),
        "订阅查询(模糊'王') GET /query?q=王": lambda: s.get(BASE + "/query?q=王"),
        "统计分析 GET /stats": lambda: s.get(BASE + "/stats"),
        "订单列表 GET /orders": lambda: s.get(BASE + "/orders"),
        "人员管理 GET /subscribers": lambda: s.get(BASE + "/subscribers"),
    }
    rows = []
    for name, fn in pages.items():
        r = bench(fn, 30)
        rows.append((name, r))
    return rows


def db_conn():
    cfg = yaml.safe_load(open(ROOT / "config" / "config.yml",
                              encoding="utf-8"))["mysql"]
    return pymysql.connect(host=cfg["ip"], port=int(cfg["port"]),
                           user=cfg["user"], password=cfg["password"],
                           database="press_sub_db", charset="utf8mb4")


def db_tests():
    conn = db_conn()
    cur = conn.cursor()
    sqls = [
        ("订单明细全景视图 v_order_detail（5 表连接）",
         "SELECT COUNT(*) FROM v_order_detail"),
        ("模糊查询：王姓订阅人明细",
         "SELECT * FROM v_order_detail WHERE sub_name LIKE '王%'"),
        ("模糊查询：报刊名称含'报'",
         "SELECT * FROM v_order_detail WHERE pub_name LIKE '%报%'"),
        ("按部门统计视图 v_dept_stat",
         "SELECT * FROM v_dept_stat ORDER BY total_amount DESC"),
        ("按报刊统计视图 v_pub_stat",
         "SELECT * FROM v_pub_stat ORDER BY total_amount DESC LIMIT 10"),
        ("12 个月订阅趋势（分组聚合）",
         "SELECT DATE_FORMAT(sub_date,'%Y-%m') ym, SUM(subtotal) FROM"
         " v_order_detail WHERE order_status='已通过' GROUP BY ym"),
        ("函数 fn_person_total_amount",
         "SELECT fn_person_total_amount('EMP00001')"),
    ]
    rows = []
    for name, sql in sqls:
        r = bench(lambda: cur.execute(sql) or cur.fetchall(), 50)
        rows.append((name, r))
    conn.close()
    return rows


def concurrent_query_tests():
    """20 线程 × 5 次订阅查询，统计成功率与吞吐。"""
    sessions = [login_session() for _ in range(20)]

    def worker(s):
        ok, t0 = 0, time.perf_counter()
        for _ in range(5):
            r = s.get(BASE + "/query?q=王")
            if r.status_code == 200:
                ok += 1
        return ok, time.perf_counter() - t0

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(worker, sessions))
    wall = time.perf_counter() - t0
    total_ok = sum(r[0] for r in results)
    return {"threads": 20, "requests": 100, "ok": total_ok,
            "fail": 100 - total_ok, "wall": wall,
            "tps": 100 / wall}


def concurrent_order_tests():
    """10 线程并发下单：验证 FOR UPDATE 取号的唯一性与事务正确性。"""
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT sub_id FROM subscriber WHERE role='订阅用户' LIMIT 1")
    sub_id = cur.fetchone()[0]
    conn.close()

    def worker(i):
        c = db_conn()
        c2 = c.cursor()
        try:
            c2.execute("CALL sp_place_order(%s,%s,%s,%s,%s,%s)",
                       (sub_id, "2026-11-01", "2027-04-30", "P0000001", 1, 12))
            # 结果集依次为 RELEASE_LOCK 标志、订单号——遍历取以 SO 开头的结果
            while True:
                rows = c2.fetchall()
                if rows and str(rows[0][0]).startswith("SO"):
                    return rows[0][0]
                if not c2.nextset():
                    return None
        finally:
            c.close()

    with ThreadPoolExecutor(max_workers=10) as ex:
        order_ids = list(ex.map(worker, range(10)))
    unique = len(set(order_ids))
    return {"count": len(order_ids), "unique": unique,
            "ids": order_ids[:3] + ["..."]}


def main():
    print("== A. 页面响应时间（30 次取样） ==")
    http_rows = http_tests()
    for name, r in http_rows:
        print(f"  {name:<38} 均值 {r['avg']:7.1f} ms   P95 {r['p95']:7.1f} ms")

    print("== B. 数据库层 SQL 响应时间（50 次取样） ==")
    db_rows = db_tests()
    for name, r in db_rows:
        print(f"  {name:<38} 均值 {r['avg']:7.2f} ms   P95 {r['p95']:7.2f} ms")

    print("== C. 并发查询（20 线程 × 5 请求） ==")
    cq = concurrent_query_tests()
    print(f"  成功 {cq['ok']}/{cq['requests']}  失败 {cq['fail']}  "
          f"耗时 {cq['wall']:.2f}s  吞吐 {cq['tps']:.1f} req/s")

    print("== D. 并发下单（10 线程同时提交） ==")
    co = concurrent_order_tests()
    print(f"  成功生成 {co['count']} 张订阅单，订单号唯一 {co['unique']}/{co['count']}"
          f"  示例 {co['ids']}")

    # 结果写入 docs/perf-results.md 供报告引用
    lines = ["# 性能测试原始结果", "",
             f"_执行时间：{time.strftime('%Y-%m-%d %H:%M:%S')}_", "",
             "## A. 页面响应时间（HTTP，30 次取样）", "",
             "| 页面 | 均值(ms) | P95(ms) | 最小(ms) | 最大(ms) |",
             "|---|---|---|---|---|"]
    for name, r in http_rows:
        lines.append(f"| {name} | {r['avg']:.1f} | {r['p95']:.1f} | "
                     f"{r['min']:.1f} | {r['max']:.1f} |")
    lines += ["", "## B. 数据库层 SQL 响应时间（50 次取样）", "",
              "| SQL | 均值(ms) | P95(ms) | 最小(ms) | 最大(ms) |",
              "|---|---|---|---|---|"]
    for name, r in db_rows:
        lines.append(f"| {name} | {r['avg']:.2f} | {r['p95']:.2f} | "
                     f"{r['min']:.2f} | {r['max']:.2f} |")
    lines += ["", "## C. 并发查询",
              "",
              f"- 20 线程 × 5 请求 = 100 次请求：成功 {cq['ok']}，失败 {cq['fail']}",
              f"- 总耗时 {cq['wall']:.2f} s，吞吐约 {cq['tps']:.1f} req/s",
              "", "## D. 并发下单取号唯一性",
              "",
              f"- 10 线程同时调用 sp_place_order：生成 {co['count']} 张订阅单，"
              f"订单号唯一 {co['unique']}/{co['count']}"]
    out = ROOT / "docs" / "perf-results.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n结果已写入 {out}")


if __name__ == "__main__":
    main()
