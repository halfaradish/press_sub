-- =====================================================================
-- 报刊订阅管理系统 · 01 建库建表脚本（物理设计与实施）
-- 运行环境：MySQL 8.0+，字符集 utf8mb4
-- 说明：与报告第五章 5.2 物理结构设计、5.4 数据库实施对应
-- =====================================================================

-- 1. 创建数据库
DROP DATABASE IF EXISTS press_sub_db;
CREATE DATABASE press_sub_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE press_sub_db;

-- 2. 部门表
CREATE TABLE department (
  dept_id     CHAR(6)     NOT NULL COMMENT '部门编号',
  dept_name   VARCHAR(30) NOT NULL COMMENT '部门名称',
  location    VARCHAR(30) NULL     COMMENT '办公地点',
  phone       VARCHAR(13) NULL     COMMENT '联系电话（可为区号-号码）',
  CONSTRAINT pk_department  PRIMARY KEY (dept_id),
  CONSTRAINT uk_dept_name   UNIQUE (dept_name),
  CONSTRAINT chk_dept_phone CHECK (phone IS NULL OR phone REGEXP '^[0-9-]{7,13}$')
) ENGINE=InnoDB COMMENT='部门表';

-- 3. 订阅人员表（含登录账号与角色，1:1 联系已合并）
CREATE TABLE subscriber (
  sub_id    CHAR(8)     NOT NULL DEFAULT '' COMMENT '人员编号（EMP+5位数字）',
  sub_name  VARCHAR(20) NOT NULL COMMENT '姓名',
  gender    CHAR(2)     NULL COMMENT '性别（男/女）',
  phone     CHAR(11)    NULL COMMENT '联系电话',
  address   VARCHAR(50) NULL COMMENT '通信地址',
  dept_id   CHAR(6)     NOT NULL COMMENT '所属部门编号',
  username  VARCHAR(20) NOT NULL COMMENT '登录用户名',
  password  VARCHAR(64) NOT NULL COMMENT '登录口令（加密存储）',
  role      VARCHAR(10) NOT NULL DEFAULT '订阅用户' COMMENT '系统角色',
  CONSTRAINT pk_subscriber   PRIMARY KEY (sub_id),
  CONSTRAINT uk_sub_username UNIQUE (username),
  CONSTRAINT chk_sub_gender  CHECK (gender IN ('男','女')),
  CONSTRAINT chk_sub_role    CHECK (role IN ('系统管理员','部门管理员','订阅用户')),
  INDEX idx_sub_dept (dept_id),
  INDEX idx_sub_name (sub_name),
  CONSTRAINT fk_sub_dept FOREIGN KEY (dept_id) REFERENCES department (dept_id)
) ENGINE=InnoDB COMMENT='订阅人员表';

-- 4. 报刊类别表
CREATE TABLE category (
  cat_id   CHAR(4)     NOT NULL COMMENT '类别编号',
  cat_name VARCHAR(20) NOT NULL COMMENT '类别名称',
  cat_desc VARCHAR(50) NULL     COMMENT '类别说明',
  CONSTRAINT pk_category PRIMARY KEY (cat_id),
  CONSTRAINT uk_cat_name UNIQUE (cat_name)
) ENGINE=InnoDB COMMENT='报刊类别表';

-- 5. 报刊表（维护联系 1:n 已合并为维护人外码）
CREATE TABLE publication (
  pub_id     CHAR(8)      NOT NULL COMMENT '报刊编号（P+7位数字）',
  pub_name   VARCHAR(40)  NOT NULL COMMENT '报刊名称',
  cat_id     CHAR(4)      NOT NULL COMMENT '所属类别编号',
  period     VARCHAR(6)   NOT NULL COMMENT '刊期',
  unit_price DECIMAL(6,2) NOT NULL COMMENT '每期单价（元）',
  publisher  VARCHAR(30)  NULL     COMMENT '出版社',
  maintainer CHAR(8)      NULL     COMMENT '维护人（系统管理员人员编号）',
  CONSTRAINT pk_publication  PRIMARY KEY (pub_id),
  CONSTRAINT chk_pub_price   CHECK (unit_price > 0),
  CONSTRAINT chk_pub_period  CHECK (period IN ('日报','周报','半月刊','月刊','双月刊')),
  INDEX idx_pub_name (pub_name),
  INDEX idx_pub_cat  (cat_id),
  CONSTRAINT fk_pub_cat FOREIGN KEY (cat_id) REFERENCES category (cat_id),
  CONSTRAINT fk_pub_mnt FOREIGN KEY (maintainer) REFERENCES subscriber (sub_id)
) ENGINE=InnoDB COMMENT='报刊表';

-- 6. 订阅单表（提交、审核两个 1:n 联系均合并为外码）
CREATE TABLE subscription (
  order_id      CHAR(10)      NOT NULL COMMENT '订单编号（SO+7位流水）',
  sub_date      DATE          NOT NULL COMMENT '订阅日期',
  start_date    DATE          NOT NULL COMMENT '起订日期',
  end_date      DATE          NOT NULL COMMENT '截止日期',
  total_amount  DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '总金额（触发器汇总）',
  order_status  VARCHAR(8)    NOT NULL DEFAULT '待审核' COMMENT '订单状态',
  orderer_id    CHAR(8)       NOT NULL COMMENT '下单人（人员编号）',
  auditor_id    CHAR(8)       NULL COMMENT '审核人（人员编号）',
  audit_time    DATETIME      NULL COMMENT '审核时间',
  audit_comment VARCHAR(100)  NULL COMMENT '审核意见',
  CONSTRAINT pk_subscription  PRIMARY KEY (order_id),
  CONSTRAINT chk_ord_dates    CHECK (end_date > start_date AND start_date >= sub_date),
  CONSTRAINT chk_ord_status   CHECK (order_status IN ('待审核','已通过','已驳回','已退订')),
  INDEX idx_ord_orderer (orderer_id),
  INDEX idx_ord_status_date (order_status, sub_date),
  CONSTRAINT fk_ord_orderer FOREIGN KEY (orderer_id) REFERENCES subscriber (sub_id),
  CONSTRAINT fk_ord_auditor FOREIGN KEY (auditor_id) REFERENCES subscriber (sub_id)
) ENGINE=InnoDB COMMENT='订阅单表';

-- 7. 订阅明细表（包含联系 m:n 转换为独立关系，主码为两外码组合）
CREATE TABLE subscription_detail (
  order_id CHAR(10)      NOT NULL COMMENT '订单编号',
  pub_id   CHAR(8)       NOT NULL COMMENT '报刊编号',
  quantity INT           NOT NULL COMMENT '订阅份数',
  periods  INT           NOT NULL COMMENT '订阅期数',
  subtotal DECIMAL(10,2) NOT NULL COMMENT '小计金额（触发器按单价×份数×期数计算）',
  CONSTRAINT pk_sub_detail   PRIMARY KEY (order_id, pub_id),
  CONSTRAINT chk_det_qty     CHECK (quantity BETWEEN 1 AND 999),
  CONSTRAINT chk_det_periods CHECK (periods >= 1),
  INDEX idx_det_pub (pub_id),
  CONSTRAINT fk_det_order FOREIGN KEY (order_id) REFERENCES subscription (order_id) ON DELETE CASCADE,
  CONSTRAINT fk_det_pub   FOREIGN KEY (pub_id)   REFERENCES publication (pub_id)
) ENGINE=InnoDB COMMENT='订阅明细表';

-- 8. 操作日志表
CREATE TABLE op_log (
  log_id     INT          NOT NULL AUTO_INCREMENT COMMENT '日志编号',
  sub_id     CHAR(8)      NULL COMMENT '操作人员（人员编号）',
  op_type    VARCHAR(10)  NOT NULL COMMENT '操作类型',
  op_content VARCHAR(200) NOT NULL COMMENT '操作内容',
  op_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  CONSTRAINT pk_op_log PRIMARY KEY (log_id),
  INDEX idx_log_time (op_time),
  INDEX idx_log_sub  (sub_id),
  CONSTRAINT fk_log_sub FOREIGN KEY (sub_id) REFERENCES subscriber (sub_id)
) ENGINE=InnoDB COMMENT='操作日志表';
