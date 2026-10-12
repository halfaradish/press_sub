# -*- coding: utf-8 -*-
"""数据库连接层。

设计要点：
1. 按账号缓存连接池（SimplePool），登录用户的角色决定使用哪个 MySQL 账号；
2. 每个请求从池中取一条连接、请求结束归还，避免频繁握手；
3. autocommit 打开：单条 CRUD 即时提交；多语句原子性一律交给
   存储过程内部的显式事务（BEGIN/COMMIT/ROLLBACK）保证。
"""
import queue
import threading

import pymysql
from flask import g, has_request_context

from . import config

_local = threading.local()
_pools: dict = {}
_pools_lock = threading.Lock()


class SimplePool:
    """极简连接池：按需创建、上限控制、取出时 ping 保活。"""

    def __init__(self, account: tuple, database: str | None, max_size: int):
        self._user, self._password = account
        self._database = database
        self._max = max_size
        self._free: queue.Queue = queue.Queue()
        self._created = 0
        self._lock = threading.Lock()

    def _connect(self):
        base = config.mysql_base()
        base.update(user=self._user, password=self._password,
                    database=self._database, autocommit=True)
        return pymysql.connect(**base)

    def acquire(self):
        while True:
            try:
                conn = self._free.get_nowait()
            except queue.Empty:
                with self._lock:
                    if self._created < self._max:
                        self._created += 1
                        return self._connect()
                return self._connect()          # 超上限时直连，用后即弃
            try:
                conn.ping(reconnect=True)
                return conn
            except pymysql.err.Error:
                with self._lock:
                    self._created -= 1
                continue

    def release(self, conn):
        if conn is None:
            return
        try:
            conn.ping(reconnect=False)
            self._free.put_nowait(conn)
        except (pymysql.err.Error, queue.Full):
            try:
                conn.close()
            except Exception:
                pass


def pool_for(account: tuple, database: str | None = "press_sub_db") -> SimplePool:
    key = account[0]
    with _pools_lock:
        if key not in _pools:
            _pools[key] = SimplePool(account, database, config.POOL_SIZE)
        return _pools[key]


def role_conn():
    """当前请求会话对应的数据库连接（惰性创建，缓存于 flask.g）。

    DYNAMIC_DB_ACCOUNTS 开启时以登录人同名账号连接，
    行级安全视图 v_user_orders 依赖 CURRENT_USER() 过滤本人订单。
    """
    if "db" not in g:
        g.db = pool_for(session_account()).acquire()
    return g.db


def session_account() -> tuple:
    from flask import session
    if config.DYNAMIC_DB_ACCOUNTS:
        username = session["username"]
        return (username, dynamic_pwd(username))
    return config.ROLE_ACCOUNTS[session["role"]]


def dynamic_pwd(username: str) -> str:
    """动态账号口令：由用户名 + 服务端密钥推导，不落盘、不入会话。"""
    import hashlib
    return hashlib.sha256(
        f"{config.SECRET_KEY}::db-account::{username}".encode("utf-8")).hexdigest()


def root_conn():
    """维护专用 root 连接（仅用于登录时创建动态账号等管理操作）。"""
    base = config.mysql_base()
    return pool_for((base["user"], base["password"]), None).acquire()


def release_request_conn(_exc=None):
    if has_request_context() and "db" in g:
        pool_for(session_account()).release(g.db)
        g.pop("db", None)


def auth_conn():
    """认证专用连接（列级最小授权账号）。"""
    return pool_for(config.AUTH_ACCOUNT).acquire()


def release_request_conn(_exc=None):
    if has_request_context() and "db" in g:
        pool_for(config.ROLE_ACCOUNTS[g.role]).release(g.db)
        g.pop("db", None)


# ------------------------------------------------------------------ 查询工具
def query(sql: str, params: tuple | list = (), one: bool = False):
    """执行 SELECT，返回 list[dict]（one=True 时返回单条或 None）。"""
    cur = role_conn().cursor(pymysql.cursors.DictCursor)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql: str, params: tuple | list = ()) -> int:
    """执行 INSERT/UPDATE/DELETE，返回受影响行数。"""
    with role_conn().cursor() as cur:
        return cur.execute(sql, params)


def call_proc(name: str, args: tuple | list):
    """调用存储过程，返回其最后一个非空结果集（list[tuple]，无结果集时为 []）。

    说明：不使用 callproc——以显式 CALL 语句执行，SIGNAL 抛出的业务
    异常会原样转为 pymysql 异常，由调用方翻译成界面提示。
    sp_place_order 会先后产生两个结果集（RELEASE_LOCK 标志、订单号），
    故遍历全部结果集并取最后一个非空者，即过程的最终输出。
    """
    with role_conn().cursor() as cur:
        cur.execute(f"CALL {name}({', '.join(['%s'] * len(args))})", tuple(args))
        last = []
        while True:
            try:
                rows = cur.fetchall()
                if rows:
                    last = rows
            except Exception:
                pass
            if not cur.nextset():
                break
    return last


def scalar(sql: str, params: tuple | list = ()):
    """取单值（COUNT/SUM 等聚合结果）。"""
    with role_conn().cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return row[0] if row else None
