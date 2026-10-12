# 报刊订阅管理系统

> 《数据库原理实践》课程设计 · 选题 32 · Python (Flask) + MySQL 8.0

面向高校/企事业单位的报刊订阅业务管理系统：统一办理部门与个人的报刊订阅、审核结算与统计分析。
系统包含**系统管理员、部门管理员、订阅用户**三种角色，数据库层实现触发器、函数、存储过程、视图、
权限控制与事务，应用层提供完整的 Web 界面与数据可视化。

## 技术栈

| 层 | 选型 |
|---|---|
| 数据库 | MySQL 8.0（InnoDB / utf8mb4），库名 `press_sub_db` |
| 后端 | Python 3.10+（开发环境 3.13）、Flask 3、Jinja2、pymysql |
| 前端 | 服务端渲染 HTML + 原生 JavaScript + ECharts 5（`static/vendor/` 离线引入，无外网依赖） |
| 图形 | 需求分析 DFD、概念设计 E-R 图均为 SVG/HTML 绘制，PNG 导出于 `docs/*-images/` |

## 功能一览

| 模块 | 系统管理员 | 部门管理员 | 订阅用户 |
|---|---|---|---|
| 部门 / 人员 / 类别 / 报刊管理（含模糊查询） | ✔ | — | — |
| 订单审核（存储过程 + 状态机触发器） | ✔ | — | — |
| 代订 / 自助订阅 / 追加明细 / 退订 | — | ✔ | ✔ |
| 订阅查询（姓名·报刊·部门·订单号模糊查询、打印导 PDF） | 全局 | 本部门 | 本人 |
| 统计分析（趋势、类别占比、报刊/部门/人员三维汇总） | 全局 | 本部门 | 报刊排行 + 个人汇总 |
| 操作日志 / 系统维护（对象清册、mysqldump 备份） | ✔ | — | — |
| 个人中心（改口令） | ✔ | ✔ | ✔ |

**数据库对象**：7 张表（全部 BCNF）· 7 个视图 · 2 个函数 · 4 个存储过程 · 7 个触发器 ·
3 个数据库角色 + 认证专用列级授权账号，见 [sql/](sql/)。

## 目录结构

```
database-practice/
├── sql/                        # 数据库脚本（按序执行 01→06）
│   ├── 01_create_database.sql  #   建库 + 7 张表（约束/索引）
│   ├── 02_views.sql            #   7 个视图（含行级安全视图 v_user_orders）
│   ├── 03_functions.sql        #   2 个函数
│   ├── 04_procedures.sql       #   4 个存储过程（下单/追加/审核/退订，显式事务）
│   ├── 05_triggers.sql         #   7 个触发器（金额、状态机、日志）
│   └── 06_permissions.sql      #   角色、应用账号、GRANT（列级授权）
├── webapp/                     # Web 应用
│   ├── run.py                  #   启动入口（http://127.0.0.1:5000）
│   ├── seed_data.py            #   测试数据加载（每表 ≥50 条，固定种子可复现）
│   ├── requirements.txt
│   ├── pressapp/               #   应用包：config / db 连接池 / auth / helpers / routes×5
│   │   └── templates/          #   23 个 Jinja2 模板
│   ├── static/                 #   设计系统 CSS、页面脚本、离线 ECharts
│   └── tests/                  #   test_e2e.py（34 项功能断言）、test_perf.py（性能测试）
├── config/
│   ├── config.example.yml      # 配置模板（复制为 config.yml 并填写数据库口令）
│   └── config.yml              # 本机实际配置（不入库）
├── docs/                       # 课程文档
│   ├── 需求分析.html            #   第二章底稿（DFD + 数据字典）
│   ├── 概念结构设计-ER图.html    #   第三章底稿（分 E-R + 总体 E-R）
│   ├── 逻辑结构设计.html        #   第四章底稿（关系模型/范式优化/视图）
│   ├── 物理设计与实施.html      #   第五章底稿（表结构/索引/函数/过程/触发器/事务/权限）
│   ├── 数据库测试.html          #   第七章底稿（数据加载/功能测试/性能测试）
│   ├── 待办清单.md              #   全流程进度与硬性指标对照
│   ├── report/                 #   报告生成脚本（build_docx.py）与交付说明
│   └── er-images/ dfd-images/ report-images/   # 各章插图 PNG
└── 报告-班级-姓名.docx          # 课程设计报告（Word，待填写姓名班级）
```

## 快速开始

**环境要求**：Python 3.10+、MySQL 8.0（本机 3306）、可选 MySQL 命令行客户端。

```bash
# 1. 安装依赖
pip install -r webapp/requirements.txt

# 2. 配置数据库连接：复制模板并填写本机 MySQL 账号口令
cp config/config.example.yml config/config.yml
#    编辑 config.yml: ip / port / user / password

# 3. 建库与数据库对象（01 会先 DROP 重建，可反复执行）
for f in sql/0*.sql; do mysql -uroot -p < "$f"; done
#    （或使用 MySQL Workbench 依次执行 sql/01 ~ 06）

# 4. 灌入测试数据（7 张表每表 ≥50 条，口令统一 123456）
python webapp/seed_data.py

# 5. 启动系统
python webapp/run.py        # 打开 http://127.0.0.1:5000
```

### 演示账号（口令均为 `123456`）

| 角色 | 账号 |
|---|---|
| 系统管理员 | `admin`（另有 `admin2`） |
| 部门管理员 | `dept01` ~ `dept52` |
| 订阅用户 | 姓名拼音，如 `denglei`（可用 `admin` 在人员管理中查询） |

## 测试

```bash
python webapp/tests/test_e2e.py     # 端到端功能测试：34 项断言（需系统已启动）
python webapp/tests/test_perf.py    # 性能测试：响应时间 / 并发查询 / 并发下单取号
```

实测结果（本机环境，见 [docs/perf-results.md](docs/perf-results.md)）：
页面平均响应 ≤ 22 ms、典型 SQL 均值 ≤ 2 ms、20 并发查询成功率 100%（约 230 req/s）、
10 线程并发下单订单号 10/10 唯一。

## 报告与文档

- 课程设计报告：[报告-班级-姓名.docx](报告-班级-姓名.docx)（45 页 / 正文约 1.7 万字 / 31 表 / 22 图）
- 报告重新生成：`python docs/report/build_docx.py`（改内容或截图后重跑即可）
- 提交前人工事项与产出说明：[docs/report/交付说明.md](docs/report/交付说明.md)

## 设计要点（阅读代码时可关注）

1. **三级权限防线**：路由装饰器（页面级）→ 数据库角色账号（数据级）→ 行级安全视图（行级）。
   登录时为人员动态创建**同名 MySQL 账号**并授予对应角色，会话内所有 SQL 都以该账号执行，
   数据库 GRANT 即应用功能的硬边界。
2. **行级安全视图** `v_user_orders`：DEFINER 视图内必须用 `USER()` 而非 `CURRENT_USER()`
   过滤登录人（后者返回定义者 root，视图会恒空——实测踩坑记录在提交历史与报告 7.3 节）。
3. **写操作全部经存储过程**：下单 `sp_place_order` 用命名锁 `GET_LOCK` 串行化取号
   （初版 `FOR UPDATE` 在 10 线程并发压测中触发间隙锁死锁 1213，已修复）；审核/退订在事务内校验状态机。
4. **金额一致性交给触发器**：小计 = 单价×份数×期数、总金额汇总均由触发器维护，应用层无法绕开。
5. **认证最小特权**：登录校验走专用账号 `auth_app`，仅被授予 `subscriber` 表 5 列 SELECT
   与 `password` 列 UPDATE（列级授权）。

## 说明

- `config/config.yml`、`local/` 与教师资料目录均在 `.gitignore` 中，含口令的配置不会进入版本库。
- `docs/report/preview/` 与 `报告预览.pdf` 为渲染产物，已忽略；需要时用 Word 从 docx 重新导出。
- 开发环境：Windows 11 + Python 3.13 + MySQL 8.0.40；代码约 5000 行（不含第三方库）。
