-- =====================================================================
-- 报刊订阅管理系统 · 02 视图设计（逻辑结构设计 4.3）
-- 每个视图对应系统的一项真实访问需求
-- =====================================================================
USE press_sub_db;

-- 视图1：订阅人员公开信息（屏蔽用户名与口令）
-- 需求：查询模块展示人员信息、普通用户互相查看时不得暴露登录凭据（安全性）
CREATE OR REPLACE VIEW v_user_brief AS
SELECT s.sub_id, s.sub_name, s.gender, s.phone, s.address,
       d.dept_name, s.role
FROM subscriber s
JOIN department d ON d.dept_id = s.dept_id;

-- 视图2：订阅单明细全景（订单 + 下单人 + 部门 + 报刊 + 明细 + 审核痕迹）
-- 需求：按人员/报刊/部门查询订阅信息，是最常用的多表连接，定义为视图简化操作（简单性）；
--       同时供系统管理员/部门管理员的订单详情页使用（含审核人与审核意见）
CREATE OR REPLACE VIEW v_order_detail AS
SELECT o.order_id, o.sub_date, o.start_date, o.end_date,
       o.order_status, o.total_amount,
       o.auditor_id, o.audit_time, o.audit_comment,
       s.sub_id, s.sub_name, d.dept_name,
       p.pub_id, p.pub_name, p.period, p.unit_price,
       det.quantity, det.periods, det.subtotal
FROM subscription o
JOIN subscriber s ON s.sub_id = o.orderer_id
JOIN department d ON d.dept_id = s.dept_id
JOIN subscription_detail det ON det.order_id = o.order_id
JOIN publication p ON p.pub_id = det.pub_id;

-- 视图3：待审核订阅单（审核工作台）
-- 需求：系统管理员审核时只关心待审核订单，视图同时屏蔽其他状态数据
CREATE OR REPLACE VIEW v_pending_orders AS
SELECT o.order_id, s.sub_name, d.dept_name, o.sub_date,
       o.start_date, o.end_date, o.total_amount
FROM subscription o
JOIN subscriber s ON s.sub_id = o.orderer_id
JOIN department d ON d.dept_id = s.dept_id
WHERE o.order_status = '待审核';

-- 视图4：按人员订阅统计（仅统计已通过订单）
-- 需求：统计功能之“按人员统计”
CREATE OR REPLACE VIEW v_person_stat AS
SELECT s.sub_id, s.sub_name, d.dept_name,
       COUNT(DISTINCT o.order_id)  AS order_cnt,
       SUM(det.quantity)           AS total_qty,
       SUM(det.subtotal)           AS total_amount
FROM subscription o
JOIN subscriber s ON s.sub_id = o.orderer_id
JOIN department d ON d.dept_id = s.dept_id
JOIN subscription_detail det ON det.order_id = o.order_id
WHERE o.order_status = '已通过'
GROUP BY s.sub_id, s.sub_name, d.dept_name;

-- 视图5：按部门订阅统计
-- 需求：统计功能之“按部门统计”
CREATE OR REPLACE VIEW v_dept_stat AS
SELECT d.dept_id, d.dept_name,
       COUNT(DISTINCT o.order_id)  AS order_cnt,
       COUNT(DISTINCT s.sub_id)    AS person_cnt,
       SUM(det.quantity)           AS total_qty,
       SUM(det.subtotal)           AS total_amount
FROM subscription o
JOIN subscriber s ON s.sub_id = o.orderer_id
JOIN department d ON d.dept_id = s.dept_id
JOIN subscription_detail det ON det.order_id = o.order_id
WHERE o.order_status = '已通过'
GROUP BY d.dept_id, d.dept_name;

-- 视图6：按报刊订阅统计
-- 需求：统计功能之“按报刊统计”，也可用于受欢迎报刊排行
CREATE OR REPLACE VIEW v_pub_stat AS
SELECT p.pub_id, p.pub_name, c.cat_name, p.period, p.unit_price,
       SUM(det.quantity) AS total_qty,
       SUM(det.subtotal) AS total_amount
FROM subscription_detail det
JOIN publication p ON p.pub_id = det.pub_id
JOIN category   c ON c.cat_id = p.cat_id
JOIN subscription o ON o.order_id = det.order_id
WHERE o.order_status = '已通过'
GROUP BY p.pub_id, p.pub_name, c.cat_name, p.period, p.unit_price;

-- 视图7：个人订单视图（行级安全）
-- 需求：订阅用户只能查看自己的订单。视图按登录账号自动过滤：
--   ① 直连数据库：约定“数据库账号名 = 订阅人员用户名”；
--   ② Web 应用：登录时为人员动态创建同名 MySQL 账号并授予对应角色，
--      会话内所有操作以该账号执行。
--   注意必须用 USER() 而不是 CURRENT_USER()——后者在 DEFINER 权限的
--   视图内部返回定义者（root），USER() 始终反映实际连接账号。
CREATE OR REPLACE VIEW v_user_orders AS
SELECT o.order_id, o.sub_date, o.start_date, o.end_date,
       o.total_amount, o.order_status,
       o.auditor_id, o.audit_time, o.audit_comment,
       p.pub_id, p.pub_name, p.period, p.unit_price,
       det.quantity, det.periods, det.subtotal
FROM subscription o
JOIN subscription_detail det ON det.order_id = o.order_id
JOIN publication p ON p.pub_id = det.pub_id
WHERE o.orderer_id = (
    SELECT s.sub_id FROM subscriber s
    WHERE s.username = SUBSTRING_INDEX(USER(), '@', 1)
);
