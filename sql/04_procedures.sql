-- =====================================================================
-- 报刊订阅管理系统 · 04 存储过程设计（物理结构优化 5.3）
-- 关键业务以存储过程封装，内部使用显式事务保证原子性
-- =====================================================================
USE press_sub_db;
DELIMITER $$

-- 过程1：创建订阅单（含第一条订阅明细）
-- 事务：订单号分配、订单头插入、明细插入必须同时成功或同时失败
DROP PROCEDURE IF EXISTS sp_place_order $$
CREATE PROCEDURE sp_place_order(
    IN p_sub_id  CHAR(8),   -- 下单人
    IN p_start   DATE,      -- 起订日期
    IN p_end     DATE,      -- 截止日期
    IN p_pub_id  CHAR(8),   -- 报刊编号
    IN p_qty     INT,       -- 份数
    IN p_periods INT)       -- 订阅期数
BEGIN
    DECLARE v_last  INT;
    DECLARE v_order CHAR(10);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF NOT EXISTS (SELECT 1 FROM subscriber WHERE sub_id = p_sub_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '订阅人员不存在';
    END IF;

    START TRANSACTION;
    -- 锁定最近订单行再取号，防止并发取号重复
    SELECT CAST(SUBSTRING(order_id, 3) AS UNSIGNED) INTO v_last
    FROM subscription ORDER BY order_id DESC LIMIT 1 FOR UPDATE;
    SET v_order = CONCAT('SO', LPAD(IFNULL(v_last, 0) + 1, 7, '0'));

    INSERT INTO subscription (order_id, sub_date, start_date, end_date, order_status, orderer_id)
    VALUES (v_order, CURDATE(), p_start, p_end, '待审核', p_sub_id);

    INSERT INTO subscription_detail (order_id, pub_id, quantity, periods)
    VALUES (v_order, p_pub_id, p_qty, p_periods);

    COMMIT;
    SELECT v_order AS order_id;
END $$

-- 过程2：向已有订阅单追加订阅明细（一张订阅单可订多种报刊）
DROP PROCEDURE IF EXISTS sp_add_detail $$
CREATE PROCEDURE sp_add_detail(
    IN p_order   CHAR(10),
    IN p_pub_id  CHAR(8),
    IN p_qty     INT,
    IN p_periods INT)
BEGIN
    DECLARE v_status VARCHAR(8);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    SELECT order_status INTO v_status FROM subscription
    WHERE order_id = p_order FOR UPDATE;
    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '订阅单不存在';
    END IF;
    IF v_status <> '待审核' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '仅待审核订单可追加订阅明细';
    END IF;

    INSERT INTO subscription_detail (order_id, pub_id, quantity, periods)
    VALUES (p_order, p_pub_id, p_qty, p_periods);
    COMMIT;
END $$

-- 过程3：审核订阅单（仅系统管理员）
DROP PROCEDURE IF EXISTS sp_audit_order $$
CREATE PROCEDURE sp_audit_order(
    IN p_order    CHAR(10),
    IN p_auditor  CHAR(8),
    IN p_pass     TINYINT,        -- 1=通过 0=驳回
    IN p_comment  VARCHAR(100))
BEGIN
    DECLARE v_role   VARCHAR(10);
    DECLARE v_status VARCHAR(8);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SELECT role INTO v_role FROM subscriber WHERE sub_id = p_auditor;
    IF v_role IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '审核人不存在';
    END IF;
    IF v_role <> '系统管理员' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '仅系统管理员可审核订阅单';
    END IF;

    START TRANSACTION;
    SELECT order_status INTO v_status FROM subscription
    WHERE order_id = p_order FOR UPDATE;
    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '订阅单不存在';
    END IF;
    IF v_status <> '待审核' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '该订阅单已处理，不能重复审核';
    END IF;

    UPDATE subscription
    SET order_status   = IF(p_pass = 1, '已通过', '已驳回'),
        auditor_id     = p_auditor,
        audit_time     = NOW(),
        audit_comment  = p_comment
    WHERE order_id = p_order;
    COMMIT;
END $$

-- 过程4：退订（订阅人本人对已通过的订单执行退订，保留历史记录）
DROP PROCEDURE IF EXISTS sp_cancel_order $$
CREATE PROCEDURE sp_cancel_order(
    IN p_order  CHAR(10),
    IN p_sub_id CHAR(8))
BEGIN
    DECLARE v_orderer CHAR(8);
    DECLARE v_status  VARCHAR(8);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    SELECT orderer_id, order_status INTO v_orderer, v_status
    FROM subscription WHERE order_id = p_order FOR UPDATE;
    IF v_orderer IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '订阅单不存在';
    END IF;
    IF v_orderer <> p_sub_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '仅可退订本人的订阅单';
    END IF;
    IF v_status <> '已通过' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '仅已通过的订阅单可退订';
    END IF;

    UPDATE subscription SET order_status = '已退订' WHERE order_id = p_order;
    COMMIT;
END $$

DELIMITER ;
