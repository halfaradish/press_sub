# -*- coding: utf-8 -*-
"""测试数据加载脚本（报告 7.1 加载测试数据）。

数据来源：程序自动生成（固定随机种子 2026，可重复执行、结果一致）。
覆盖范围：7 张关系表每表不少于 50 条记录；口令统一为 SHA-256 摘要存储。
说明：部门、报刊类别为组织机构/分类字典，按真实业务规模生成；
      订阅单金额由触发器按 单价×份数×期数 自动计算。

用法：
    python seed_data.py            # 清空并重新灌入全部测试数据
"""
import hashlib
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pymysql
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------- 词料
SURNAMES = ["王", "李", "张", "刘", "陈", "杨", "黄", "赵", "吴", "周",
            "徐", "孙", "马", "朱", "胡", "郭", "何", "林", "罗", "郑",
            "梁", "谢", "宋", "唐", "许", "韩", "冯", "邓", "曹", "彭",
            "曾", "肖", "田", "董", "袁", "蔡", "蒋", "余", "杜", "叶"]
GIVEN = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋",
         "勇", "艳", "杰", "涛", "明", "超", "秀英", "霞", "平", "刚",
         "桂英", "文轩", "雨欣", "志强", "建华", "国栋", "嘉怡", "晨曦",
         "思远", "晓峰", "雪梅", "海燕", "俊杰", "春花", "德华", "丽华",
         "子涵", "浩然", "梦琪", "忆萱", "志明", "凤兰"]
PY = {"王": "wang", "李": "li", "张": "zhang", "刘": "liu", "陈": "chen",
      "杨": "yang", "黄": "huang", "赵": "zhao", "吴": "wu", "周": "zhou",
      "徐": "xu", "孙": "sun", "马": "ma", "朱": "zhu", "胡": "hu",
      "郭": "guo", "何": "he", "林": "lin", "罗": "luo", "郑": "zheng",
      "梁": "liang", "谢": "xie", "宋": "song", "唐": "tang", "许": "xu",
      "韩": "han", "冯": "feng", "邓": "deng", "曹": "cao", "彭": "peng",
      "曾": "zeng", "肖": "xiao", "田": "tian", "董": "dong", "袁": "yuan",
      "蔡": "cai", "蒋": "jiang", "余": "yu", "杜": "du", "叶": "ye",
      "伟": "wei", "芳": "fang", "娜": "na", "敏": "min", "静": "jing",
      "丽": "li", "强": "qiang", "磊": "lei", "军": "jun", "洋": "yang",
      "勇": "yong", "艳": "yan", "杰": "jie", "涛": "tao", "明": "ming",
      "超": "chao", "英": "ying", "霞": "xia", "平": "ping", "刚": "gang"}

# 52 个部门（大学规模：职能部门 + 学院 + 教辅机构）
DEPT_NAMES = [
    "学校办公室", "党委宣传部", "党委组织部", "纪律检查委员会办公室", "人事处",
    "教务处", "科研处", "财务处", "招生就业处", "研究生院",
    "发展规划处", "审计处", "国际合作与交流处", "学生工作处", "保卫处",
    "后勤管理处", "基建管理处", "资产管理处", "离退休工作处", "工会委员会",
    "计算机与电子信息学院", "新闻与传播学院", "经济学院", "管理学院", "法学院",
    "文学院", "外国语学院", "数学与统计学院", "物理科学与技术学院", "化学化工学院",
    "生命科学学院", "资源环境与材料学院", "机械工程学院", "电气工程学院",
    "土木建筑工程学院", "轻工与食品工程学院", "农学院", "林学院", "动物科学技术学院",
    "医学院", "口腔医学院", "公共卫生学院", "药学院", "马克思主义学院",
    "体育学院", "艺术学院", "国际学院", "继续教育学院", "图书馆",
    "网络中心", "档案馆", "学报编辑部",
]

# 52 类报刊分类字典（本期报刊覆盖其中一部分，其余为可扩展字典项）
CATEGORIES = [
    ("C001", "综合日报",   "面向大众的综合新闻类日报"),
    ("C002", "都市晚报",   "城市市民生活类晚报"),
    ("C003", "党政机关报", "各级党委机关报"),
    ("C004", "时政周刊",   "时事政治深度报道周刊"),
    ("C005", "新闻月刊",   "新闻综述类月刊"),
    ("C006", "证券财经",   "证券市场与投资理财"),
    ("C007", "产经报道",   "产业经济与区域经济"),
    ("C008", "管理营销",   "企业管理与市场营销"),
    ("C009", "金融保险",   "金融、银行与保险"),
    ("C010", "基础科学",   "数理化等基础学科"),
    ("C011", "信息技术",   "计算机与信息技术"),
    ("C012", "科普读物",   "大众科学普及"),
    ("C013", "自然科学",   "地学、生物与自然科学"),
    ("C014", "医学健康",   "医学与健康保健"),
    ("C015", "文学原创",   "原创文学作品"),
    ("C016", "文摘文选",   "文摘类选刊"),
    ("C017", "诗歌散文",   "诗歌与散文"),
    ("C018", "小说期刊",   "小说与故事"),
    ("C019", "艺术收藏",   "艺术鉴赏与收藏"),
    ("C020", "书画摄影",   "书法、绘画与摄影"),
    ("C021", "音乐影视",   "音乐与影视"),
    ("C022", "体育综合",   "综合体育赛事"),
    ("C023", "足球专项",   "足球运动"),
    ("C024", "篮球专项",   "篮球运动"),
    ("C025", "健身养生",   "健身与养生保健"),
    ("C026", "基础教育",   "中小学教育"),
    ("C027", "高等教育",   "高等教育与大学"),
    ("C028", "考试升学",   "考试与升学辅导"),
    ("C029", "学前教育",   "幼儿与学前教育"),
    ("C030", "家庭教育",   "家庭与亲子教育"),
    ("C031", "旅游出行",   "旅游与户外"),
    ("C032", "美食生活",   "美食与烹饪"),
    ("C033", "家居园艺",   "家居与园艺"),
    ("C034", "服饰美容",   "服饰与美容"),
    ("C035", "汽车交通",   "汽车与交通"),
    ("C036", "少儿科普",   "少年儿童科普"),
    ("C037", "少儿文学",   "少年儿童文学"),
    ("C038", "幼儿启蒙",   "幼儿启蒙读物"),
    ("C039", "英文报刊",   "英文原版报刊"),
    ("C040", "多语种报刊", "其他语种报刊"),
    ("C041", "学术综合",   "综合类学术期刊"),
    ("C042", "自然科学学报", "自然科学类学报"),
    ("C043", "工程技术学报", "工程技术类学报"),
    ("C044", "农林科学",   "农业与林业科学"),
    ("C045", "医药卫生",   "医药与卫生"),
    ("C046", "人文社科",   "人文社会科学"),
    ("C047", "法律法制",   "法律与法制"),
    ("C048", "军事国防",   "军事与国防"),
    ("C049", "行业动态",   "行业信息动态"),
    ("C050", "能源电力",   "能源与电力工业"),
    ("C051", "交通运输",   "交通运输工程"),
    ("C052", "通信技术",   "通信与电子技术"),
]

# (报刊名称, 类别编号, 刊期, 单价, 出版社)
PUBS = [
    ("广西日报", "C001", "日报", 1.50, "广西日报传媒集团"),
    ("南国早报", "C002", "日报", 1.20, "广西日报传媒集团"),
    ("南宁晚报", "C002", "日报", 1.00, "南宁日报社"),
    ("人民日报", "C003", "日报", 1.80, "人民日报社"),
    ("光明日报", "C003", "日报", 1.60, "光明日报社"),
    ("新华每日电讯", "C003", "日报", 1.50, "新华通讯社"),
    ("南方周末", "C004", "周报", 4.00, "南方报业传媒集团"),
    ("环球时报", "C003", "日报", 1.70, "人民日报社"),
    ("半月谈", "C005", "半月刊", 6.50, "新华通讯社"),
    ("瞭望新闻周刊", "C004", "周报", 5.00, "新华通讯社"),
    ("经济日报", "C007", "日报", 1.60, "经济日报社"),
    ("第一财经日报", "C006", "日报", 2.50, "上海广播电视台"),
    ("21世纪经济报道", "C007", "周报", 3.50, "南方报业传媒集团"),
    ("财经杂志", "C006", "双月刊", 20.00, "中国证券市场研究设计中心"),
    ("财新周刊", "C006", "周报", 8.00, "财新传媒"),
    ("中国经营报", "C008", "周报", 3.00, "中国社会科学院"),
    ("销售与市场", "C008", "月刊", 12.00, "销售与市场杂志社"),
    ("经济观察报", "C007", "周报", 3.20, "经济观察报社"),
    ("中国金融家", "C009", "月刊", 15.00, "中国金融出版社"),
    ("科技日报", "C011", "日报", 1.50, "科技日报社"),
    ("计算机世界", "C011", "周报", 4.50, "计算机世界传媒集团"),
    ("环球科学", "C012", "月刊", 18.00, "环球科学杂志社"),
    ("科学画报", "C012", "月刊", 9.80, "上海科学技术出版社"),
    ("中国国家地理", "C013", "月刊", 22.00, "中国科学院地理研究所"),
    ("科幻世界", "C012", "月刊", 10.00, "科幻世界杂志社"),
    ("电脑报", "C011", "周报", 4.00, "电脑报社"),
    ("人民文学", "C015", "月刊", 15.00, "人民文学出版社"),
    ("收获", "C015", "双月刊", 22.00, "收获杂志社"),
    ("十月", "C015", "双月刊", 20.00, "北京出版社"),
    ("读者", "C016", "半月刊", 6.00, "读者出版传媒股份有限公司"),
    ("意林", "C016", "半月刊", 5.50, "意林杂志社"),
    ("小说月报", "C018", "月刊", 9.00, "百花文艺出版社"),
    ("诗刊", "C017", "半月刊", 7.00, "中国作家协会"),
    ("散文选刊", "C017", "月刊", 6.80, "河南省文联"),
    ("体坛周报", "C022", "周报", 3.00, "体坛周报社"),
    ("足球报", "C023", "周报", 2.50, "足球报社"),
    ("篮球公园", "C024", "周报", 5.00, "篮球公园杂志社"),
    ("新体育", "C022", "月刊", 10.00, "新体育杂志社"),
    ("健与美", "C025", "月刊", 9.00, "健身与美容杂志社"),
    ("中国教育报", "C026", "日报", 1.50, "中国教育报刊社"),
    ("大学生", "C027", "月刊", 6.50, "大学生杂志社"),
    ("求学", "C028", "半月刊", 6.00, "求学杂志社"),
    ("幼儿画报", "C029", "月刊", 7.50, "中国少年儿童出版社"),
    ("父母必读", "C030", "月刊", 8.00, "北京出版社"),
    ("中国国家旅游", "C031", "月刊", 16.00, "中国国家旅游杂志社"),
    ("美食与美酒", "C032", "月刊", 15.00, "美食与美酒杂志社"),
    ("健康之友", "C014", "月刊", 8.00, "健康之友杂志社"),
    ("儿童文学", "C037", "月刊", 8.50, "中国少年儿童出版社"),
    ("我们爱科学", "C036", "半月刊", 6.00, "中国少年儿童出版社"),
    ("China Daily", "C039", "日报", 2.80, "中国日报社"),
    ("北京周报", "C039", "周报", 12.00, "北京周报社"),
    ("The Economist", "C039", "周报", 45.00, "The Economist Group"),
    ("计算机学报", "C043", "月刊", 25.00, "科学出版社"),
    ("软件学报", "C043", "月刊", 28.00, "科学出版社"),
    ("通信学报", "C052", "月刊", 24.00, "中国通信学会"),
    ("电力系统自动化", "C050", "半月刊", 20.00, "中国电机工程学会"),
]

AUDIT_PASS = ["同意订阅", "预算内，同意", "部门集体订阅，同意", "数量核实无误，同意",
              "符合订阅管理办法，同意", "经办人已确认，同意"]
AUDIT_REJECT = ["预算超支，驳回", "重复提交，驳回", "起订日期有误，请重新提交",
                "份数与部门编制不符，驳回", "报刊已停刊，驳回"]

PERIOD_DAYS = {"日报": 1, "周报": 7, "半月刊": 15, "月刊": 30, "双月刊": 60}
PERIOD_CHOICES = {"日报": [90, 180, 365], "周报": [13, 26, 52],
                  "半月刊": [6, 12, 24], "月刊": [3, 6, 12], "双月刊": [3, 6]}


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_names(n: int) -> list:
    """生成 n 个不重复的中文姓名。"""
    seen, names = set(), []
    while len(names) < n:
        name = rng.choice(SURNAMES) + rng.choice(GIVEN)
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def py_of(name: str) -> str:
    return "".join(PY.get(ch, "u") for ch in name)


def main():
    global rng
    rng = random.Random(2026)

    cfg = yaml.safe_load(open(ROOT / "config" / "config.yml", encoding="utf-8"))["mysql"]
    conn = pymysql.connect(host=cfg["ip"], port=int(cfg["port"]), user=cfg["user"],
                           password=cfg["password"], database="press_sub_db",
                           charset="utf8mb4", autocommit=True)
    cur = conn.cursor()

    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for t in ["subscription_detail", "subscription", "op_log", "publication",
              "category", "subscriber", "department"]:
        cur.execute(f"TRUNCATE TABLE {t}")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")

    # 1. 部门 52 条
    depts = [(f"D{i+1:05d}", name, f"{rng.choice(['行政楼', '教学楼', '文科楼', '工科楼', '科研楼'])}"
              f"{rng.choice('ABCDEF')}{rng.randint(101, 620)}",
              f"0771-32{rng.randint(30000, 39999)}")
             for i, name in enumerate(DEPT_NAMES)]
    cur.executemany("INSERT INTO department VALUES (%s,%s,%s,%s)", depts)

    # 2. 人员：2 系统管理员 + 52 部门管理员（每部门 1 名）+ 55 订阅用户 = 109
    names = make_names(109)
    subs, used = [], {"admin", "admin2"}
    subs.append(("EMP00001", names[0], "男", "13800000001", "广西南宁市大学路1号",
                 depts[20][0], "admin", sha256("123456"), "系统管理员"))
    subs.append(("EMP00002", names[1], "女", "13800000002", "广西南宁市大学路2号",
                 depts[0][0], "admin2", sha256("123456"), "系统管理员"))
    for i, dept in enumerate(depts):
        uname = f"dept{i+1:02d}"
        used.add(uname)
        subs.append((f"EMP{len(subs)+1:05d}", names[i + 2], "男" if i % 2 == 0 else "女",
                     f"139{rng.randint(10000000, 99999999)}",
                     f"广西南宁市大学路{rng.randint(3, 99)}号",
                     dept[0], uname, sha256("123456"), "部门管理员"))
    for j in range(55):
        name = names[j + 54]
        base = py_of(name)
        uname = base if base not in used else f"{base}{j+2}"
        while uname in used:
            uname = f"{base}{rng.randint(10, 99)}"
        used.add(uname)
        subs.append((f"EMP{len(subs)+1:05d}", name, "男" if j % 2 == 0 else "女",
                     f"137{rng.randint(10000000, 99999999)}",
                     f"广西南宁市大学路{rng.randint(3, 99)}号",
                     rng.choice(depts)[0], uname, sha256("123456"), "订阅用户"))
    cur.executemany("INSERT INTO subscriber VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", subs)

    # 3. 类别 52 条
    cur.executemany("INSERT INTO category VALUES (%s,%s,%s)", CATEGORIES)

    # 4. 报刊 56 条
    pubs = [(f"P{i+1:07d}", name, cat, period, price, publisher, "EMP00001")
            for i, (name, cat, period, price, publisher) in enumerate(PUBS)]
    cur.executemany("INSERT INTO publication VALUES (%s,%s,%s,%s,%s,%s,%s)", pubs)

    # 5. 订阅单 96 张 + 明细（小计/总金额由触发器自动计算）
    today = date(2026, 10, 11)
    staff_ids = [s[0] for s in subs if s[8] == "订阅用户"]
    dept_admin_ids = [s[0] for s in subs if s[8] == "部门管理员"]
    pub_rows = cur.fetchall() if cur.execute("SELECT pub_id, period FROM publication") else []
    for k in range(96):
        order_id = f"SO{k+1:07d}"
        sub_date = today - timedelta(days=rng.randint(5, 380))
        pub_id, period = rng.choice(pub_rows)
        periods = rng.choice(PERIOD_CHOICES[period])
        start = sub_date + timedelta(days=rng.randint(0, 15))
        end = start + timedelta(days=periods * PERIOD_DAYS[period])
        orderer = (rng.choice(dept_admin_ids + staff_ids) if rng.random() < 0.65
                   else rng.choice(staff_ids))
        age = (today - sub_date).days
        if age < 5:
            status = "待审核" if rng.random() < 0.7 else rng.choice(["已通过", "已驳回"])
        else:
            status = rng.choices(["已通过", "已退订", "已驳回", "待审核"],
                                 weights=[70, 15, 8, 7])[0]
        if status in ("已通过", "已驳回"):
            auditor = "EMP00001"
            audit_time = sub_date + timedelta(days=rng.randint(1, 3))
            comment = rng.choice(AUDIT_PASS if status == "已通过" else AUDIT_REJECT)
        else:
            auditor, audit_time, comment = None, None, None
        cur.execute(
            "INSERT INTO subscription (order_id, sub_date, start_date, end_date,"
            " order_status, orderer_id, auditor_id, audit_time, audit_comment)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (order_id, sub_date, start, end, status, orderer, auditor, audit_time, comment))
        chosen = {pub_id}
        for _ in range(rng.randint(0, 2)):
            chosen.add(rng.choice(pub_rows)[0])
        for pid in chosen:
            cur.execute("INSERT INTO subscription_detail VALUES (%s,%s,%s,%s,0)",
                        (order_id, pid, rng.randint(1, 3), periods))

    # 6. 操作日志：插入人员/报刊时触发器已自动写入 165 条，另补登录/查询/维护日志
    logs = []
    for _ in range(40):
        who = rng.choice(subs)[0]
        op = rng.choice(["登录", "查询", "维护", "下单", "审核"])
        content = {
            "登录": "登录系统",
            "查询": rng.choice(["查询订阅明细", "查询报刊统计", "查询部门汇总"]),
            "维护": rng.choice(["调整报刊单价", "新增报刊类别", "备份基础数据"]),
            "下单": "提交订阅申请",
            "审核": rng.choice(["审核通过订阅单", "驳回订阅单"]),
        }[op]
        t = today - timedelta(days=rng.randint(0, 30), hours=rng.randint(0, 9),
                              minutes=rng.randint(0, 59))
        logs.append((who, op, content, t))
    cur.executemany(
        "INSERT INTO op_log (sub_id, op_type, op_content, op_time) VALUES (%s,%s,%s,%s)", logs)

    # 7. 结果核对
    print("测试数据加载完成：")
    ok = True
    for t in ["department", "subscriber", "category", "publication",
              "subscription", "subscription_detail", "op_log"]:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]
        ok &= cnt >= 50
        print(f"  {t:<22} {cnt:>4}  {'OK' if cnt >= 50 else '!! 不足50'}")
    print("\n演示账号（口令均为 123456）：")
    print("  系统管理员   admin / admin2")
    print("  部门管理员   dept01 ~ dept52")
    print("  订阅用户     以姓名拼音为用户名（如 wangwei），口令 123456")
    print("全部满足每表≥50" if ok else "存在不足 50 条的表，请检查")
    conn.close()


if __name__ == "__main__":
    main()
