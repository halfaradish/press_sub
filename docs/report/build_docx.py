# -*- coding: utf-8 -*-
"""生成《数据库原理实践》课程设计报告 Word 文档。

格式要点（老师模板要求）：
  正文宋体小四、英文 Times New Roman、多倍行距 1.25、首行缩进 2 字符；
  三线表；表题在表上方、图题在图下方，均为五号加粗居中；目录与正文分页。

用法：python docs/report/build_docx.py
产出：报告-班级-姓名.docx
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from extract_html import DOCS, find_png, parse_doc, runs_text

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "报告-班级-姓名.docx"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SONG, HEI, KAI = "宋体", "黑体", "楷体"
TNR = "Times New Roman"


# ---------------------------------------------------------------- 富文本工具
def add_runs(par, runs, *, size=12, east=SONG, ascii_f=TNR, bold=None):
    """把 [(text, flags)] 写进段落；flags ⊆ {b, code, u, fk}。"""
    for text, flags in runs:
        if text == "":
            continue
        for seg in str(text).split("\n"):
            if seg != str(text).split("\n")[0]:
                r = par.add_run()
                r.add_break()
            if seg == "":
                continue
            flags = set(flags) if not isinstance(flags, str) else {flags}
            r = par.add_run(seg)
            r.font.name = "Consolas" if "code" in flags else ascii_f
            r._element.rPr.rFonts.set(qn("w:eastAsia"), SONG if "code" not in flags else SONG)
            r.font.size = Pt(size - 1.5 if "code" in flags else size)
            r.font.bold = True if (bold or "b" in flags) else None
            if "u" in flags:
                r.font.underline = True
            if "fk" in flags:
                r.font.underline = True
                r._element.rPr.rFonts.set(qn("w:eastAsia"), SONG)
                u = r._element.rPr.find(qn("w:u"))
                if u is None:
                    u = r._element.rPr.makeelement(qn("w:u"), {})
                    r._element.rPr.append(u)
                u.set(qn("w:val"), "dash")


def text_only(runs):
    return re.sub(r"\s+", " ", runs_text(runs)).strip()


# ---------------------------------------------------------------- 段落工具
def para(doc, text="", *, style=None, size=12, bold=False, align=None,
         indent=True, east=SONG, spacing=1.25, before=0, after=0):
    p = doc.add_paragraph(style=style)
    pf = p.paragraph_format
    pf.line_spacing = spacing
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    if align:
        p.alignment = align
    if text:
        r = p.add_run(text)
        r.font.size = Pt(size)
        r.font.bold = bold or None
        r.font.name = TNR
        r._element.rPr.rFonts.set(qn("w:eastAsia"), east)
    if indent and not align:
        ind = p._p.get_or_add_pPr().makeelement(qn("w:ind"), {})
        ind.set(qn("w:firstLineChars"), "200")
        ind.set(qn("w:firstLine"), "480")
        p._p.get_or_add_pPr().append(ind)
    return p


def set_cell_border(cell, **kw):
    """kw: top/bottom = (val, sz)"""
    tcPr = cell._tc.get_or_add_tcPr()
    borders = tcPr.makeelement(qn("w:tcBorders"), {})
    for edge, spec in kw.items():
        val, sz = spec
        el = borders.makeelement(qn(f"w:{edge}"), {})
        el.set(qn("w:val"), val)
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tcPr.append(borders)


def three_line_table(doc, caption, header, rows):
    """三线表：表题（上）+ 表格。"""
    if caption:
        para(doc, caption, size=10.5, bold=True,
             align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, before=6, after=2)
    ncols = max(len(header) or 0, max((len(r) for r in rows), default=0))
    if ncols == 0:
        return
    table = doc.add_table(rows=(1 if header else 0) + len(rows), cols=ncols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    def fill(cell, text, bold):
        p = cell.paragraphs[0]
        p.alignment = (WD_ALIGN_PARAGRAPH.CENTER if bold
                       else WD_ALIGN_PARAGRAPH.LEFT)
        pf = p.paragraph_format
        pf.line_spacing = 1.0
        pf.space_before = Pt(1)
        pf.space_after = Pt(1)
        r = p.add_run(text)
        r.font.size = Pt(10.5)
        r.font.bold = bold or None
        r.font.name = TNR
        r._element.rPr.rFonts.set(qn("w:eastAsia"), SONG)

    offset = 0
    if header:
        offset = 1
        # 跨页时重复表头
        trPr = table.rows[0]._tr.get_or_add_trPr()
        th = trPr.makeelement(qn("w:tblHeader"), {})
        trPr.append(th)
        for j, text in enumerate(header):
            c = table.rows[0].cells[j]
            fill(c, text, True)
            set_cell_border(c, bottom=("single", 6))
    for i, row in enumerate(rows):
        for j in range(ncols):
            c = table.rows[i + offset].cells[j]
            fill(c, row[j] if j < len(row) else "", False)
    # 三线表边框：顶/底粗线，无竖线
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = tblPr.makeelement(qn("w:tblBorders"), {})
    for edge, sz in (("top", 12), ("bottom", 12)):
        el = borders.makeelement(qn(f"w:{edge}"), {})
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:color"), "000000")
        borders.append(el)
    for edge in ("left", "right", "insideH", "insideV"):
        el = borders.makeelement(qn(f"w:{edge}"), {})
        el.set(qn("w:val"), "none")
        borders.append(el)
    tblPr.append(borders)
    para(doc, "", indent=False, spacing=1.0, after=4)


def code_block(doc, text):
    """代码清单：Consolas 小五、浅灰底、单倍行距、可换行。"""
    lines = text.rstrip("\n").split("\n")
    for i, line in enumerate(lines):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.line_spacing = 1.0
        pf.space_before = Pt(6 if i == 0 else 0)
        pf.space_after = Pt(6 if i == len(lines) - 1 else 0)
        pf.left_indent = Cm(0.4)
        pPr = p._p.get_or_add_pPr()
        shd = pPr.makeelement(qn("w:shd"), {})
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), "F2F3F5")
        pPr.append(shd)
        r = p.add_run(line if line else " ")
        r.font.name = "Consolas"
        r._element.rPr.rFonts.set(qn("w:eastAsia"), SONG)
        r.font.size = Pt(9)


def code_caption(doc, text):
    para(doc, text, size=10.5, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, before=6, after=2)


def image(doc, path: Path, caption, width_cm=14.0):
    if not path or not path.exists():
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    r = p.add_run()
    r.add_picture(str(path), width=Cm(width_cm))
    para(doc, caption, size=10.5, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, before=2, after=6)


def h1(doc, text, page_break=False):
    p = doc.add_paragraph(style="Heading 1")
    if page_break:
        p.paragraph_format.page_break_before = True
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.font.name = TNR
    r._element.rPr.rFonts.set(qn("w:eastAsia"), HEI)
    r.font.size = Pt(15)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0, 0, 0)
    p.paragraph_format.space_before = Pt(13)
    p.paragraph_format.space_after = Pt(10)
    return p


def h2(doc, runs):
    p = doc.add_paragraph(style="Heading 2")
    text = runs if isinstance(runs, str) else text_only(runs)
    r = p.add_run(text)
    r.font.name = TNR
    r._element.rPr.rFonts.set(qn("w:eastAsia"), HEI)
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0, 0, 0)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    return p


def h3(doc, runs):
    p = doc.add_paragraph(style="Heading 3")
    text = runs if isinstance(runs, str) else text_only(runs)
    r = p.add_run(text)
    r.font.name = TNR
    r._element.rPr.rFonts.set(qn("w:eastAsia"), HEI)
    r.font.size = Pt(12)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0, 0, 0)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    return p


# ---------------------------------------------------------------- 块渲染
def render_blocks(doc, blocks, img_dir=None):
    for b in blocks:
        kind = b[0]
        if kind == "h2":
            h2(doc, b[1])
        elif kind == "h3":
            h3(doc, b[1])
        elif kind == "p":
            para(doc, "")
            add_runs(doc.paragraphs[-1], b[1])
        elif kind == "note":
            para(doc, "")
            add_runs(doc.paragraphs[-1], b[1])
        elif kind == "table":
            three_line_table(doc, b[1], b[2], b[3])
        elif kind == "figure":
            png = find_png(b[1])
            image(doc, png, b[2], width_cm=13.5)
        elif kind == "code":
            code_block(doc, b[1])
        elif kind == "schema":
            p = para(doc, "", spacing=1.25)
            add_runs(p, [(t, f | {"u"} if f == "u" else f) for t, f in b[1]])
        elif kind == "img":
            image(doc, Path(b[1]), b[2], width_cm=b[3] if len(b) > 3 else 14.0)
        elif kind == "codecap":
            code_caption(doc, b[1])


def render_schema(doc, runs):
    """关系模式：主码实下划线、外码虚下划线。"""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.25
    for text, flags in runs:
        if text == "":
            continue
        flags = set(flags)
        r = p.add_run(text)
        r.font.name = TNR
        r._element.rPr.rFonts.set(qn("w:eastAsia"), SONG)
        r.font.size = Pt(12)
        if "u" in flags:
            r.font.underline = True
        if "fk" in flags:
            r.font.underline = True
            u = r._element.rPr.find(qn("w:u"))
            if u is not None:
                u.set(qn("w:val"), "dash")


# ---------------------------------------------------------------- 报告正文
CH1 = [
    ("p", [("报刊订阅是机关、企事业单位日常行政事务中的一项传统业务。随着单位规模扩大、"
            "报刊种类与订阅人数增多，依靠人工登记表格、手工汇总金额的传统管理方式暴露出"
            "效率低、易出错、难统计、难追溯等问题：订阅信息分散在各部门的纸质表格中，"
            "财务汇总需要人工核算单价、份数与期数的乘积，审核过程缺少记录，历史数据难以"
            "复用。针对上述问题，本课程设计选择附录题目 32“报刊订阅管理系统”，运用数据库"
            "原理课程所学知识，完成从需求分析、概念结构设计、逻辑结构设计、物理设计与实施，"
            "到应用系统开发与测试的完整数据库应用系统建设过程。", "")]),
    ("p", [("系统采用 B/S 架构，后端使用 Python 语言的 Flask 框架，数据库管理系统选用 "
            "MySQL 8.0[2]，前端以服务端渲染的 HTML 页面配合 ECharts 图表库实现数据可视化。"
            "系统设计并维护系统管理员、部门管理员、订阅用户三种系统角色[3]，不同角色通过"
            "不同界面完成各自业务：系统管理员负责基础数据维护、订阅单审核与系统监控；"
            "部门管理员负责为本部门人员代订报刊并掌握本部门订阅情况；订阅用户自助订阅、"
            "查询本人订单。数据库层通过视图、存储过程、函数、触发器、事务与权限控制保证"
            "数据的完整性与安全性。", "")]),
    ("p", [("本报告的组织安排如下：（二）需求分析给出系统功能模块图、数据流图与数据字典；"
            "（三）概念结构设计给出各模块分 E-R 图与系统总体 E-R 图；（四）逻辑结构设计"
            "完成 E-R 图向关系模型的转换、关系模式的规范化与视图设计；（五）数据库物理设计"
            "与实施介绍存储结构、索引、函数、存储过程、触发器、事务与权限控制的设计及建库"
            "实施过程；（六）应用系统的设计与实施介绍系统总体结构、各角色界面与访问数据库的"
            "关键代码；（七）数据库测试给出测试数据加载、分模块功能测试与性能测试的结果；"
            "（八）收获和体会总结课程设计的收获与分工；（九）参考文献列出设计过程中参考的"
            "文献。", "")]),
]

CH6 = [
    ("h2", "6.1 系统总体结构"),
    ("p", [("应用系统采用三层结构：表现层由 21 个 Jinja2 模板构成服务端渲染页面，配合"
            "原生 JavaScript 与离线引入的 ECharts 图表库完成交互与可视化；业务层由 Flask "
            "应用承担，按功能划分为认证、工作台、订阅业务、查询统计、基础数据管理 5 个蓝图，"
            "共 30 条路由；数据层通过自研的轻量级连接池访问本机 MySQL 8.0.40 的 "
            "press_sub_db 库，业务写操作全部经由第（五）章设计的存储过程完成。工程结构"
            "如表 6-1 所示。", "")]),
    ("table", "表 6-1 应用系统工程结构",
     ["目录/文件", "内容"],
     [["webapp/run.py", "启动入口（开发服务器 127.0.0.1:5000）"],
      ["webapp/pressapp/", "应用包：配置、数据库连接池、认证、公共辅助与 5 个路由蓝图"],
      ["webapp/templates/", "21 个 Jinja2 页面模板（登录、工作台、业务与维护页面）"],
      ["webapp/static/", "app.css 设计系统、页面脚本与离线 ECharts 库"],
      ["webapp/tests/", "端到端功能测试与性能测试脚本"],
      ["webapp/seed_data.py", "测试数据加载脚本（固定随机种子，可复现）"]]),
    ("p", [("系统的访问控制采用“页面—数据—行”三级防线：①业务层的 login_required 与 "
            "role_required 装饰器限制页面访问角色，未授权访问返回 403 页面；②登录成功后，"
            "系统为人员动态创建与其用户名同名的 MySQL 账号并授予对应数据库角色，会话内的"
            "所有数据库操作都以该账号执行，第（五）章的 GRANT 授权成为应用功能的硬性边界；"
            "③订阅用户的数据访问经由行级安全视图 v_user_orders，视图按登录账号自动过滤，"
            "保证其只能看到本人订单。", "")]),
    ("h2", "6.2 系统角色与用户界面"),
    ("p", [("三种系统角色的功能划分如表 6-2 所示，其设计依据是第（二）章需求分析中各角色的"
            "业务职责。", "")]),
    ("table", "表 6-2 系统角色功能对照表",
     ["功能", "系统管理员", "部门管理员", "订阅用户"],
     [["部门 / 人员 / 类别 / 报刊管理", "√", "—", "—"],
      ["订单审核", "√", "—", "—"],
      ["代订报刊（为本部门人员下单）", "—", "√", "—"],
      ["自助订阅 / 追加明细 / 退订", "—", "√", "√"],
      ["订阅查询", "全局", "本部门", "本人"],
      ["统计分析", "全局", "本部门", "全局报刊排行 + 本人汇总"],
      ["本部门人员名册", "—", "√", "—"],
      ["操作日志 / 系统维护 / 数据备份", "√", "—", "—"]]),
    ("p", [("登录页面如图 6-1 所示，页面以报纸刊头为视觉主题，底部提示演示账号。", "")]),
    ("img", "docs/report-images/图6-1_登录页.png", "图 6-1 登录页面", 11.5),
    ("p", [("系统管理员登录后进入全局工作台（图 6-2）：顶部指标栏汇总本月新增订阅单、本月"
            "订阅金额、待审核订单、在管报刊、订阅人员与部门数量；中部四张图表分别展示近"
            " 6 个月订阅金额趋势、订阅金额类别占比、订单状态分布与报刊订阅排行，数据均为"
            "服务端按“已通过”口径查询后内嵌给 ECharts 渲染；底部列出最近订单与最早提交的"
            "待审核订单，便于管理员快速进入审核工作台。", "")]),
    ("img", "docs/report-images/图6-2_系统管理员工作台.png", "图 6-2 系统管理员工作台", 14.5),
    ("p", [("订阅用户的工作台如图 6-3 所示，仅展示本人数据：累计订阅金额由函数 "
            "fn_person_total_amount 计算，订单数据来自行级安全视图 v_user_orders。",
            "")]),
    ("img", "docs/report-images/图6-13_订阅用户工作台.png", "图 6-3 订阅用户工作台", 14.5),
    ("p", [("订单审核工作台（图 6-4）按提交时间列出全部待审核订阅单；审核人在订单详情页"
            "（图 6-5）核对明细金额后填写审核意见执行“通过”或“驳回”，操作经由存储过程"
            " sp_audit_order 完成，状态机校验、审核时间与操作日志由数据库自动维护。", "")]),
    ("img", "docs/report-images/图6-3_订单审核页.png", "图 6-4 订单审核工作台", 14.5),
    ("img", "docs/report-images/图6-4_订单详情页.png", "图 6-5 订单详情与审核页", 14.5),
    ("p", [("新建订阅单页面（图 6-6）支持多明细行：选择报刊后页面按“单价 × 份数 × 期数”"
            "实时计算小计与合计金额，部门管理员还可选择本部门经办人员代订；提交后由存储"
            "过程在数据库内完成取号、订单头与首条明细的插入。订阅查询页（图 6-7）对姓名、"
            "报刊、部门、订单号提供模糊查询，并支持状态与日期区间组合筛选，结果可打印或"
            "导出 PDF。", "")]),
    ("img", "docs/report-images/图6-12_新建订阅单代订.png", "图 6-6 新建订阅单（部门管理员代订）", 14.5),
    ("img", "docs/report-images/图6-5_订阅查询模糊查询.png", "图 6-7 订阅明细模糊查询", 14.5),
    ("p", [("统计分析页（图 6-8）从部门、人员、报刊三个维度汇总订阅量与金额，图表下方"
            "为对应明细表格，支持模糊查询与打印。基础数据管理界面（图 6-9 ~ 图 6-11）提供"
            "部门、人员、报刊及其类别的增删改查，所有列表页均配备模糊查询与多条件筛选，"
            "删除操作经确认并对被引用数据给出友好提示。", "")]),
    ("img", "docs/report-images/图6-6_统计分析页.png", "图 6-8 统计分析页", 14.5),
    ("img", "docs/report-images/图6-7_部门管理.png", "图 6-9 部门管理", 14.5),
    ("img", "docs/report-images/图6-8_人员管理.png", "图 6-10 人员管理", 14.5),
    ("img", "docs/report-images/图6-9_报刊管理.png", "图 6-11 报刊管理", 14.5),
    ("p", [("系统维护模块（图 6-12、图 6-13）面向系统管理员提供操作日志查询（支持类型、"
            "日期与关键字过滤，日志由应用显式写入与触发器自动记录两部分构成）以及数据库"
            "对象清册、当前连接身份展示与 mysqldump 数据备份入口。", "")]),
    ("img", "docs/report-images/图6-10_操作日志.png", "图 6-12 操作日志", 14.5),
    ("img", "docs/report-images/图6-11_系统维护.png", "图 6-13 系统维护", 14.5),
    ("h2", "6.3 访问数据库的关键代码"),
    ("p", [("（1）按角色划分的数据库连接池。应用为每个数据库账号维护一个轻量级连接池，"
            "请求到来时取出连接、结束时归还，取出时通过 ping 保活。登录人员的角色决定其"
            "会话使用的数据库账号，实现“应用角色—数据库角色”的一一对应。", "")]),
    ("codecap", "代码清单 6-1 按账号缓存的连接池（节选自 pressapp/db.py）"),
    ("code", """class SimplePool:
    """ + '"""极简连接池：按需创建、上限控制、取出时 ping 保活。' + '"""' + """
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

def role_conn():
    # DYNAMIC_DB_ACCOUNTS 开启时以登录人同名账号连接，
    # 行级安全视图 v_user_orders 依赖 CURRENT_USER 过滤本人订单
    if "db" not in g:
        g.db = pool_for(session_account()).acquire()
    return g.db"""),
    ("p", [("（2）登录认证与动态同名账号。口令以 SHA-256 摘要比对，认证查询经由仅授予"
            " subscriber 表 5 个认证相关列 SELECT 权限的专用账号 auth_app 完成（列级授权）；"
            "首次登录时为人员动态创建同名 MySQL 账号并授予对应角色，口令由服务端密钥与"
            "用户名推导，不在任何位置存储。", "")]),
    ("codecap", "代码清单 6-2 登录验证与动态同名账号（节选自 pressapp/auth.py）"),
    ("code", """def verify(username, password):
    conn = db.auth_conn()           # 认证专用账号：仅可读 5 个认证相关列
    cur = conn.cursor()
    cur.execute("SELECT sub_id, username, password, role, sub_name"
                " FROM subscriber WHERE username = %s", (username,))
    row = cur.fetchone()
    if row and row[2] == digest(password):      # SHA-256 摘要比对
        return {"sub_id": row[0], "username": row[1],
                "role": row[3], "sub_name": row[4]}

def ensure_db_account(username, role):
    # 登录时幂等地创建/刷新与人员同名的 MySQL 账号并授予对应角色
    cur.execute("CREATE USER IF NOT EXISTS '%s'@'localhost' IDENTIFIED BY %%s",
                (db.dynamic_pwd(username),))
    cur.execute("GRANT '%s' TO '%s'@'localhost'" % (role_name, username))
    cur.execute("SET DEFAULT ROLE ALL TO '%s'@'localhost'" % username)"""),
    ("p", [("（3）创建订阅单。业务层仅负责参数校验与界面呈现，取号、插入订单头与首条"
            "明细在存储过程 sp_place_order 内部以显式事务完成：命名锁串行化取号保证并发"
            "下订单号唯一，触发器在明细插入时自动计算小计并汇总总金额。多种报刊的其余"
            "明细通过 sp_add_detail 逐条追加。", "")]),
    ("codecap", "代码清单 6-3 创建订阅单（节选自 pressapp/routes/orders.py）"),
    ("code", """# 4. 调用存储过程创建订阅单（事务 + 触发器自动计算金额）
first = next(iter(merged))
rows = db.call_proc("sp_place_order",
                    (orderer, start, end, first,
                     merged[first]["quantity"], merged[first]["periods"]))
order_id = rows[0][0]                       # 过程返回订单号 SO+7位流水
for pid, it in merged.items():
    if pid != first:
        db.call_proc("sp_add_detail",
                     (order_id, pid, it["quantity"], it["periods"]))
write_log("下单", f"提交订阅单 {order_id}，{len(merged)} 种报刊")"""),
    ("p", [("（4）订单审核。审核动作由系统管理员发起，存储过程内部校验审核人角色、锁定"
            "订单并校验状态机，状态变更由触发器进一步把关，审核时间与操作日志自动记录。",
            "")]),
    ("codecap", "代码清单 6-4 订单审核（节选自 pressapp/routes/orders.py）"),
    ("code", """db.call_proc("sp_audit_order",
             (order_id, session["sub_id"], 1 if action == "pass" else 0,
              comment or "同意订阅"))
# 过程内部：校验审核人角色 → FOR UPDATE 锁定订单 → 校验状态机
#           → UPDATE 状态/审核人/时间/意见 → COMMIT（触发器写日志）"""),
    ("h2", "6.4 模糊查询与统计的实现"),
    ("p", [("订阅查询页对订阅人姓名、报刊名称、部门名称与订单号提供模糊查询：以参数化"
            " LIKE 条件组合视图 v_order_detail，姓名支持“输入姓氏查全部同姓人员”；订阅"
            "用户与部门管理员的查询范围分别由行级视图与部门条件约束。", "")]),
    ("codecap", "代码清单 6-5 订阅明细模糊查询（节选自 pressapp/routes/stats.py）"),
    ("code", """if kw:      # 姓名/报刊/部门/订单号 四路模糊匹配（参数化，防注入）
    where += (" AND (d.sub_name LIKE %s OR d.pub_name LIKE %s"
              " OR d.dept_name LIKE %s OR d.order_id LIKE %s)")
    args += [f"%{kw}%"] * 4
pg = paginate(
    "SELECT d.* FROM " + rows_view + " WHERE 1=1" + where +
    " ORDER BY d.sub_date DESC, d.order_id DESC, d.pub_id",
    "SELECT COUNT(*) FROM " + rows_view + " WHERE 1=1" + where,
    tuple(args), per_page=15)"""),
    ("p", [("统计分析的数据在服务端按角色隔离后查询：趋势图按月分组聚合订阅金额，类别"
            "占比与排行来自统计视图，查询结果经 tojson 内嵌给前端 ECharts 渲染，如图 6-8"
            " 所示。", "")]),
    ("codecap", "代码清单 6-6 订阅金额月度趋势（节选自 pressapp/routes/stats.py）"),
    ("code", """trend_rows = db.query(
    "SELECT DATE_FORMAT(sub_date, '%%Y-%%m') AS ym, SUM(subtotal) AS amt"
    " FROM v_order_detail WHERE order_status='已通过' AND sub_date >= %s"
    " GROUP BY ym ORDER BY ym", (cutoff, *sargs))
# 前端：initStatsCharts({{ trend|tojson }}, ...) 渲染柱状趋势图"""),
    ("p", [("上述各模块在浏览器中的实际运行效果已在图 6-1 ~ 图 6-13 给出。系统全部页面"
            "均通过界面直接访问后台数据库完成增删改查，满足课程设计“在界面中访问后台"
            "数据库”的要求；模糊查询与统计值查询分别对应需求分析中的查询统计模块。", "")]),
]

CH8 = [
    ("p", [("本次课程设计完整地经历了一个数据库应用系统从需求到落地的全过程。在需求分析"
            "阶段，我们体会到“先把业务画清楚再动手”的重要性：数据流图与数据字典迫使我们把"
            "“谁来下单、谁来审核、金额怎么算”这些模糊的日常概念逐条落实为明确的数据流动，"
            "后续的 E-R 图与表设计几乎没有再出现大的返工。在概念与逻辑结构设计阶段，我们"
            "对函数依赖与范式理论有了远超课堂练习的理解——例如登录账号与订阅人员两个实体"
            "存在 1:1 联系，合并后产生了双候选键；“份数×期数×单价”的小计是派生属性，"
            "保留它是否符合范式、如何用触发器保证一致性，都经过了反复权衡并写入设计说明。",
            "")]),
    ("p", [("物理设计与实施阶段让我们第一次真正面对“数据库不信任应用”的问题：CHECK 约束、"
            "外码、状态机触发器在测试中多次拦下了界面层遗漏的非法数据；存储过程内部的显式"
            "事务与异常回滚保证了下单、审核等业务的原子性。性能测试则给了一个深刻的教训："
            "并发下单暴露了初版 FOR UPDATE 取号的间隙锁死锁，我们据此改用命名锁串行化取号"
            "临界区，并重新验证了 10 线程并发的取号唯一性——问题由测试发现、由设计闭环，"
            "这比任何一次顺利通过都更有收获。", "")]),
    ("p", [("应用开发阶段，我们将数据库层的权限控制与应用层会话打通：登录人为每个人动态"
            "创建同名数据库账号，行级安全视图配合 USER() 函数实现“数据库自己过滤数据”，"
            "期间排查出 DEFINER 视图内 CURRENT_USER() 返回定义者的问题，对视图执行语义的"
            "理解因此深刻了许多。此外，两人在 E-R 图评审、接口联调与测试用例设计中互相"
            "查漏补缺，也让我们体会到规范文档与版本管理在协作中的价值。", "")]),
    ("p", [("本课程设计的组内人员分工和完成情况如下表所示。", "")]),
    ("table", "表 8-1 组内人员分工和完成情况表",
     ["姓名", "所负责的任务", "完成情况"],
     [["（组长）", "数据库设计（需求分析、E-R 图、关系模型、物理设计与 SQL 对象）；"
                   "后端应用开发（连接池、认证与权限、业务路由）；报告第三~五章撰写",
       "已完成"],
      ["（组员）", "前端页面与测试（界面样式、图表、功能与性能测试脚本）；"
                   "报告第二、六、七章撰写；答辩 PPT 制作",
       "已完成"]],
     ),
    ("note", [("注：姓名、学号与班级信息请在提交前填写到封面与上表。", "")]),
]

REFS = [
    "[1] 王珊, 萨师煊. 数据库系统概论[M]. 5版. 北京: 高等教育出版社, 2014.",
    "[2] 姜承尧. MySQL技术内幕: InnoDB存储引擎[M]. 2版. 北京: 机械工业出版社, 2013.",
    "[3] 格林伯格. Flask Web开发: 基于Python的Web应用开发实战[M]. 安道, 译. "
    "北京: 人民邮电出版社, 2015.",
    "[4] 张海藩, 牟永敏. 软件工程导论[M]. 6版. 北京: 清华大学出版社, 2013.",
    "[5] 福塔. MySQL必知必会[M]. 刘晓霞, 钟鸣, 译. 北京: 人民邮电出版社, 2009.",
]

INTEGROS = {
    "二": "在第（一）章业务背景的基础上，本章从功能与数据两个视角对系统进行需求分析："
          "先给出系统功能模块图，再按结构化方法绘制自顶向下的数据流图，最后以数据字典"
          "对数据流图中各成分给出严格定义[4]。",
    "三": "本章对上章系统功能模块图中的每个功能模块按“模块功能描述—模块分E-R图”的层次"
          "进行概念结构设计，并最终集成为系统整体E-R图。",
    "四": "本章将第（三）章得到的系统整体E-R图转换为关系数据模型，依据函数依赖理论对其"
          "进行规范化优化[1]，并基于访问控制需求与数据访问特点设计视图。",
    "五": "本章介绍数据库的运行环境、存储结构设计与实施过程，给出索引、函数、存储过程、"
          "触发器、事务与权限控制的设计思想及关键实现代码[2]。",
    "七": "基于第（五）章实施完成的数据库与第（六）章开发的应用系统，本章通过界面操作"
          "与自动化脚本对数据库的访问功能与性能进行测试。",
}


# ---------------------------------------------------------------- 文档构建
def build_cover(doc):
    for _ in range(3):
        para(doc, "", indent=False)
    para(doc, "《数据库原理实践》", size=26, bold=True, east=HEI,
         align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=8)
    para(doc, "课程设计报告", size=26, bold=True, east=HEI,
         align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14)
    para(doc, "——报刊订阅管理系统的设计与实现", size=16, bold=True, east=KAI,
         align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=26)
    rows = [("姓　名：", "组　长：", "组　员："),
            ("学　号：", "", ""),
            ("班　级：", "", ""),
            ("指导教师：", "", ""),
            ("提交日期：", "2026 年 10 月", "")]
    t = doc.add_table(rows=5, cols=3)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths = (Cm(3.2), Cm(5.4), Cm(5.4))
    for i, (label, v1, v2) in enumerate(rows):
        cells = t.rows[i].cells
        for j, text in enumerate((label, v1, v2)):
            c = cells[j]
            c.width = widths[j]
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            r = p.add_run(text)
            r.font.size = Pt(14)
            r.font.name = TNR
            r._element.rPr.rFonts.set(qn("w:eastAsia"), SONG)
            if j == 0:
                r.font.bold = True
    for row in t.rows:
        for c in row.cells[1:]:
            set_cell_border(c, bottom=("single", 4))
    # 边框清理：仅保留信息行下划线


def toc_field(doc):
    p = doc.add_paragraph()
    fld = p._p.makeelement(qn("w:fldSimple"), {})
    fld.set(qn("w:instr"), r'TOC \o "1-2" \h \z \u')
    r = p.add_run("（目录：在 Word 中全选后按 F9，或右键选择“更新域”生成页码）")
    r.font.size = Pt(11)
    fld.append(r._r)
    p._p.append(fld)


def add_page_number(doc):
    section = doc.sections[0]
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    fld = r._element.makeelement(qn("w:fldSimple"), {})
    fld.set(qn("w:instr"), "PAGE")
    rr = r._element.makeelement(qn("w:r"), {})
    t = rr.makeelement(qn("w:t"), {})
    t.text = "1"
    rr.append(t)
    fld.append(rr)
    p._p.append(fld)
    for run in p.runs:
        run.font.size = Pt(9)


def setup_styles(doc):
    st = doc.styles["Normal"]
    st.font.name = TNR
    st._element.rPr.rFonts.set(qn("w:eastAsia"), SONG)
    st.font.size = Pt(12)
    pf = st.paragraph_format
    pf.line_spacing = 1.25
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)


def main():
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21.0), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2.54)
    section.left_margin = section.right_margin = Cm(2.8)
    setup_styles(doc)

    # ---- 封面
    build_cover(doc)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---- 目录
    para(doc, "目　　录", size=16, bold=True, east=HEI,
         align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=10)
    toc_field(doc)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---- 正文各章
    h1(doc, "（一）概述")
    render_blocks(doc, CH1)

    h1(doc, "（二）需求分析", page_break=False)
    para(doc, INTEGROS["二"], )
    render_blocks(doc, parse_doc(DOCS / "需求分析.html"))

    h1(doc, "（三）概念结构设计")
    para(doc, INTEGROS["三"])
    er_blocks = [b for b in parse_doc(DOCS / "概念结构设计-ER图.html")
                 if not (b[0] == "h2" and text_only(b[1]).startswith("图例"))]
    # “模块划分”改为引言性质小节：保留内容
    render_blocks(doc, er_blocks)

    h1(doc, "（四）逻辑结构设计")
    para(doc, INTEGROS["四"])
    for b in parse_doc(DOCS / "逻辑结构设计.html"):
        if b[0] == "schema":
            render_schema(doc, b[1])
        else:
            render_blocks(doc, [b])

    h1(doc, "（五）数据库物理设计与实施")
    para(doc, INTEGROS["五"])
    render_blocks(doc, parse_doc(DOCS / "物理设计与实施.html"))

    h1(doc, "（六）应用系统的设计与实施")
    render_blocks(doc, CH6)

    h1(doc, "（七）数据库测试")
    para(doc, INTEGROS["七"])
    render_blocks(doc, parse_doc(DOCS / "数据库测试.html"))

    h1(doc, "（八）收获和体会")
    render_blocks(doc, CH8)

    h1(doc, "（九）参考文献")
    for ref in REFS:
        para(doc, ref, size=10.5, indent=False, spacing=1.25, after=3)

    add_page_number(doc)
    doc.save(OUT)
    print(f"已生成 {OUT}")

    # ---- 字数统计（CJK 字符）
    total = 0
    for src in ["需求分析", "概念结构设计-ER图", "逻辑结构设计", "物理设计与实施",
                "数据库测试"]:
        s = (DOCS / f"{src}.html").read_text(encoding="utf-8")
        s = re.sub(r"<[^>]+>", "", s)
        total += len(re.findall(r"[\u4e00-\u9fff]", s))
    extras = []
    for ch in (CH1, CH6, CH8):
        for b in ch:
            if b[0] in ("p", "note", "h2"):
                extras.append(b[1] if isinstance(b[1], str) else text_only(b[1]))
    total += len(re.findall(r"[\u4e00-\u9fff]", " ".join(extras)))
    total += len(re.findall(r"[\u4e00-\u9fff]", "".join(REFS)))
    print(f"正文汉字总数（不含表格数据）：约 {total} 字")


if __name__ == "__main__":
    main()
