# -*- coding: utf-8 -*-
"""把 docs/ 下四个阶段 HTML 的正文解析为结构化内容块，供报告构建使用。

块类型：
  ("h2", text) ("h3", text)
  ("p", runs)        runs=[(text, flags)]  flags ⊆ {b, code, u, fk}
  ("note", runs)
  ("table", caption, header_rows, body_rows)   单元格为 runs
  ("figure", fig_no, caption)                  fig_no 形如 "图2-1"
  ("code", text)
  ("schema", runs)                             主码 u / 外码 fk
"""
import re
from html.parser import HTMLParser
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1]


# 上面 _in_caption 逻辑较绕，改用简化实现：重写一个更直白的解析器
class DocParser(HTMLParser):
    """针对四份阶段文档的直白解析器（依赖其规整结构）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.mode = []             # 栈: card/note/code/schema/figure/table
        self.runs = []             # 富文本累积
        self.flags = []            # 样式栈
        self.buf = []
        self.cur_tag = None        # h2/h3/p
        self.table = None
        self.cell = None
        self.cap_buf = None        # 表题累积
        self.figcap = False

    # ---------- 样式
    def _push(self, f):
        self.flags.append(f)

    def _pop(self, f):
        if f in self.flags:
            # 弹出最近的同类
            for i in range(len(self.flags) - 1, -1, -1):
                if self.flags[i] == f:
                    self.flags.pop(i)
                    break

    def _cur_flags(self):
        return {f for f in self.flags if f}

    def _add(self, text):
        if not text:
            return
        if self.cell is not None:
            self.cell.append((text, tuple(self._cur_flags())))
        elif self.buf is not None and (self.cap_buf or self.figcap):
            self.buf.append(text)
        elif self.mode and self.mode[-1] in ("code",):
            self.buf.append(text)
        elif self.cur_tag or (self.mode and self.mode[-1] in ("note", "schema")):
            self.runs.append((text, tuple(self._cur_flags())))

    def _emit(self, kind, *payload):
        self.blocks.append((kind, *payload))

    # ---------- 标签
    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "")
        if tag == "div" and cls in ("note", "code", "schema"):
            self.mode.append(cls)
            self.runs, self.buf = [], []
            return
        if tag == "div" and cls == "card":
            self.mode.append("card")
            return
        if tag in ("svg", "script", "style", "footer"):
            self.mode.append("skip")
            return
        if self.mode and self.mode[-1] == "skip":
            return
        if tag == "figure":
            self.mode.append("figure")
            self.figcap = False
            return
        if tag == "figcaption":
            self.figcap = True
            self.buf = []
            return
        if tag == "table" and "tbl" in cls:
            self.mode.append("table")
            self.table = {"cap": "", "header": [], "rows": [], "head": False}
            return
        if tag == "caption" and self.table:
            self.cap_buf = []
            return
        if tag == "thead" and self.table:
            self.table["head"] = True
            return
        if tag == "tbody" and self.table:
            self.table["head"] = False
            return
        if tag == "tr" and self.table:
            self.table.setdefault("row", [])
            return
        if tag in ("th", "td") and self.table:
            self.cell = []
            return
        if tag in ("h2", "h3"):
            self.cur_tag = tag
            self.runs = []
            return
        if tag == "li":
            self.cur_tag = "li"         # 列表项按独立正文段落输出
            self.runs = []
            return
        if tag == "p" and "body" in cls:
            self.cur_tag = "p"
            self.runs = []
            return
        if tag == "b":
            self._push("b")
            return
        if tag == "u":
            self._push("u")
            return
        if tag == "code":
            self._push("code")
            return
        if tag == "span" and "fk" in cls:
            self._push("fk")
            return
        if tag == "br":
            self._add("\n")

    def handle_endtag(self, tag):
        if tag in ("svg", "script", "style", "footer"):
            if self.mode and self.mode[-1] == "skip":
                self.mode.pop()
            return
        if self.mode and self.mode[-1] == "skip":
            return
        if tag == "figure":
            if self.mode and self.mode[-1] == "figure":
                self.mode.pop()
            self.figcap = False
            return
        if tag == "figcaption":
            cap = "".join(self.buf).strip()
            m = re.match(r"(图[0-9]+-[0-9]+)", cap)
            if m:
                self._emit("figure", m.group(1), cap)
            self.buf = None
            self.figcap = False
            return
        if tag == "div":
            if self.mode and self.mode[-1] in ("note", "code", "schema", "card"):
                kind = self.mode.pop()
                if kind == "note":
                    self._emit("note", self.runs[:])
                    self.runs = []
                elif kind == "code":
                    text = "".join(self.buf).strip("\n")
                    if text.strip():
                        self._emit("code", text)
                    self.buf = None
                elif kind == "schema":
                    self._emit("schema", self.runs[:])
                    self.runs = []
            return
        if tag == "table":
            if self.mode and self.mode[-1] == "table":
                self.mode.pop()
            t = self.table
            self.table = None
            if t:
                self._emit("table", t["cap"].strip(), t["header"], t["rows"])
            self.cap_buf = None
            return
        if tag == "caption" and self.cap_buf is not None:
            t = self.table
            if t is not None:
                t["cap"] = "".join(self.cap_buf)
            self.cap_buf = None
            return
        if tag in ("th", "td") and self.cell is not None:
            text = "".join(x for x, _ in self.cell).strip()
            if self.table:
                if self.table["head"]:
                    self.table["header"].append(text)
                else:
                    self.table.setdefault("row", []).append(text)
            self.cell = None
            return
        if tag == "tr" and self.table:
            row = self.table.pop("row", None)
            if row and not self.table["head"]:
                self.table["rows"].append(row)
            return
        if tag in ("thead", "tbody"):
            return
        if tag in ("h2", "h3", "li") and self.cur_tag == tag:
            self._emit("h2" if tag == "h2" else ("h3" if tag == "h3" else "p"),
                       self.runs[:])
            self.cur_tag = None
            self.runs = []
            return
        if tag == "p" and self.cur_tag == "p":
            self._emit("p", self.runs[:])
            self.cur_tag = None
            self.runs = []
            return
        if tag == "b":
            self._pop("b")
        elif tag == "u":
            self._pop("u")
        elif tag == "code":
            self._pop("code")
        elif tag == "span":
            self._pop("fk")

    def handle_data(self, data):
        if self.mode and self.mode[-1] == "skip":
            return
        if self.mode and self.mode[-1] == "figure" and not self.figcap:
            return                      # 跳过内联 SVG 文本
        if self.cell is not None:
            self.cell.append((data, tuple(self._cur_flags())))
            return
        if self.cap_buf is not None:
            self.cap_buf.append(data)
            return
        if self.figcap and self.buf is not None:
            self.buf.append(data)
            return
        if self.mode and self.mode[-1] == "code":
            self.buf.append(data)
            return
        if self.cur_tag or (self.mode and self.mode[-1] in ("note", "schema")):
            self.runs.append((data, tuple(self._cur_flags())))


def parse_doc(path: Path):
    p = DocParser()
    p.feed(path.read_text(encoding="utf-8"))
    return p.blocks


def runs_text(runs):
    return "".join(t for t, _ in runs)


def find_png(fig_no: str) -> Path | None:
    """按图号在 dfd-images / er-images 中定位 PNG。"""
    for sub in ("dfd-images", "er-images"):
        d = DOCS / sub
        if d.exists():
            for f in d.glob(f"{fig_no}_*.png"):
                return f
    return None


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for name in ["需求分析", "概念结构设计-ER图", "逻辑结构设计", "物理设计与实施"]:
        blocks = parse_doc(DOCS / f"{name}.html")
        kinds = {}
        for b in blocks:
            kinds[b[0]] = kinds.get(b[0], 0) + 1
        print(name, kinds)
        for b in blocks[:6]:
            head = runs_text(b[1])[:40] if isinstance(b[1], list) else str(b[1])[:40]
            print("   ", b[0], head)
