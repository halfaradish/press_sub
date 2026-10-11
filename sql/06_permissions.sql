-- =====================================================================
-- 报刊订阅管理系统 · 06 用户角色与权限控制（物理结构优化 5.3）
-- 设计思想：数据库角色与系统角色一一对应，
--           ①先建角色并授权（视图实现列级/行级控制，存储过程封装业务写操作）
--           ②再创建应用账号并将角色授予账号
-- =====================================================================
USE press_sub_db;

-- 1. 创建与系统角色对应的数据库角色
DROP ROLE IF EXISTS 'r_sys_admin';
DROP ROLE IF EXISTS 'r_dept_admin';
DROP ROLE IF EXISTS 'r_sub_user';
CREATE ROLE 'r_sys_admin';
CREATE ROLE 'r_dept_admin';
CREATE ROLE 'r_sub_user';

-- 2. 系统管理员：基础数据全权 + 审核入口 + 统计视图
GRANT SELECT, INSERT, UPDATE, DELETE ON press_sub_db.department   TO 'r_sys_admin';
GRANT SELECT, INSERT, UPDATE, DELETE ON press_sub_db.subscriber   TO 'r_sys_admin';
GRANT SELECT, INSERT, UPDATE, DELETE ON press_sub_db.category     TO 'r_sys_admin';
GRANT SELECT, INSERT, UPDATE, DELETE ON press_sub_db.publication  TO 'r_sys_admin';
GRANT SELECT ON press_sub_db.v_pending_orders                     TO 'r_sys_admin';
GRANT SELECT ON press_sub_db.v_order_detail                       TO 'r_sys_admin';
GRANT SELECT ON press_sub_db.v_person_stat                        TO 'r_sys_admin';
GRANT SELECT ON press_sub_db.v_dept_stat                          TO 'r_sys_admin';
GRANT SELECT ON press_sub_db.v_pub_stat                           TO 'r_sys_admin';
GRANT SELECT ON press_sub_db.op_log                               TO 'r_sys_admin';
GRANT EXECUTE ON PROCEDURE press_sub_db.sp_audit_order            TO 'r_sys_admin';

-- 3. 部门管理员：代订入口 + 本部门统计（不授基础表写权限）
GRANT SELECT ON press_sub_db.v_user_brief                         TO 'r_dept_admin';
GRANT SELECT ON press_sub_db.v_pub_stat                           TO 'r_dept_admin';
GRANT SELECT ON press_sub_db.v_dept_stat                          TO 'r_dept_admin';
GRANT SELECT ON press_sub_db.v_person_stat                        TO 'r_dept_admin';
GRANT EXECUTE ON PROCEDURE press_sub_db.sp_place_order            TO 'r_dept_admin';

-- 4. 订阅用户：浏览报刊、自助订阅与退订、只看自己的订单
GRANT SELECT ON press_sub_db.publication                          TO 'r_sub_user';
GRANT SELECT ON press_sub_db.v_user_orders                        TO 'r_sub_user';
GRANT SELECT ON press_sub_db.v_pub_stat                           TO 'r_sub_user';
GRANT EXECUTE ON PROCEDURE press_sub_db.sp_place_order            TO 'r_sub_user';
GRANT EXECUTE ON PROCEDURE press_sub_db.sp_cancel_order           TO 'r_sub_user';

-- 5. 创建应用账号并把角色授予账号（账号名与订阅人员用户名一致时，
--    视图 v_user_orders 可按 CURRENT_USER 自动过滤出本人订单）
CREATE USER IF NOT EXISTS 'sys_admin_app'@'localhost' IDENTIFIED BY 'Admin#2026';
CREATE USER IF NOT EXISTS 'dept_admin_app'@'localhost' IDENTIFIED BY 'Dept#2026';
CREATE USER IF NOT EXISTS 'sub_user_app'@'localhost' IDENTIFIED BY 'Sub#2026';
GRANT 'r_sys_admin'   TO 'sys_admin_app'@'localhost';
GRANT 'r_dept_admin'  TO 'dept_admin_app'@'localhost';
GRANT 'r_sub_user'    TO 'sub_user_app'@'localhost';
SET DEFAULT ROLE ALL TO 'sys_admin_app'@'localhost';
SET DEFAULT ROLE ALL TO 'dept_admin_app'@'localhost';
SET DEFAULT ROLE ALL TO 'sub_user_app'@'localhost';
FLUSH PRIVILEGES;

-- 6. 回收示例（展示 REVOKE 用法）：如需收回某账号的订阅权限
-- REVOKE EXECUTE ON PROCEDURE press_sub_db.sp_place_order FROM 'r_sub_user';
