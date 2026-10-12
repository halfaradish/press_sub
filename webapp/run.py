# -*- coding: utf-8 -*-
"""报刊订阅管理系统 · Web 应用启动入口。

用法：
    python run.py              # 开发模式，http://127.0.0.1:5000
"""
from pressapp import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
