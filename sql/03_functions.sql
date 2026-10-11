-- =====================================================================
-- 报刊订阅管理系统 · 03 函数设计（物理结构优化 5.3）
-- =====================================================================
USE press_sub_db;
DELIMITER $$

-- 函数1：计算订阅小计金额 = 报刊单价 × 份数 × 订阅期数
-- 需求：订阅登记与金额计算的核心公式集中一处，保证口径一致
DROP FUNCTION IF EXISTS fn_calc_subtotal $$
CREATE FUNCTION fn_calc_subtotal(p_pub_id CHAR(8), p_qty INT, p_periods INT)
RETURNS DECIMAL(10,2)
READS SQL DATA
BEGIN
    DECLARE v_price DECIMAL(6,2);
    SELECT unit_price INTO v_price FROM publication WHERE pub_id = p_pub_id;
    IF v_price IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '报刊不存在，无法计算金额';
    END IF;
    RETURN CAST(v_price * p_qty * p_periods AS DECIMAL(10,2));
END $$

-- 函数2：统计某人累计订阅金额（仅已通过订单）
-- 需求：查询模块的个人订阅汇总展示
DROP FUNCTION IF EXISTS fn_person_total_amount $$
CREATE FUNCTION fn_person_total_amount(p_sub_id CHAR(8))
RETURNS DECIMAL(12,2)
READS SQL DATA
BEGIN
    DECLARE v_total DECIMAL(12,2);
    SELECT IFNULL(SUM(det.subtotal), 0) INTO v_total
    FROM subscription o
    JOIN subscription_detail det ON det.order_id = o.order_id
    WHERE o.orderer_id = p_sub_id AND o.order_status = '已通过';
    RETURN v_total;
END $$

DELIMITER ;
