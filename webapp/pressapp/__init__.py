# -*- coding: utf-8 -*-
"""报刊订阅管理系统 · Web 应用包。

架构：Flask + Jinja2 服务端渲染 + pymysql。
权限模型：应用登录账号（subscriber 表）与数据库账号一一对应——
登录成功后，本次会话的所有数据库操作都通过该角色对应的 MySQL
应用账号执行，数据库层的 GRANT 即成为应用功能的硬性边界。
"""
from . import config
from .factory import create_app

__all__ = ["create_app", "config"]
