-- =====================================================================
-- 报刊订阅管理系统 · 05 触发器设计（物理结构优化 5.3）
-- 职责：小计/总金额自动维护、订单状态机校验、关键操作自动记日志
-- =====================================================================
USE press_sub_db;
DELIMITER $$

-- 触发器1：插入明细前按“单价×份数×期数”自动计算小计
DROP TRIGGER IF EXISTS trg_det_before_ins $$
CREATE TRIGGER trg_det_before_ins
BEFORE INSERT ON subscription_detail
FOR EACH ROW
BEGIN
    DECLARE v_price DECIMAL(6,2);
    SELECT unit_price INTO v_price FROM publication WHERE pub_id = NEW.pub_id;
    IF v_price IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '报刊不存在，无法订阅';
    END IF;
    SET NEW.subtotal = CAST(v_price * NEW.quantity * NEW.periods AS DECIMAL(10,2));
END $$

-- 触发器2：插入明细后把小计累加到订阅单总金额
DROP TRIGGER IF EXISTS trg_det_after_ins $$
CREATE TRIGGER trg_det_after_ins
AFTER INSERT ON subscription_detail
FOR EACH ROW
BEGIN
    UPDATE subscription
    SET total_amount = total_amount + NEW.subtotal
    WHERE order_id = NEW.order_id;
END $$

-- 触发器3：删除明细后重算订阅单总金额
DROP TRIGGER IF EXISTS trg_det_after_del $$
CREATE TRIGGER trg_det_after_del
AFTER DELETE ON subscription_detail
FOR EACH ROW
BEGIN
    UPDATE subscription o
    SET o.total_amount = (SELECT IFNULL(SUM(d.subtotal), 0)
                          FROM subscription_detail d
                          WHERE d.order_id = OLD.order_id)
    WHERE o.order_id = OLD.order_id;
END $$

-- 触发器4：订阅单状态机校验（待审核→已通过/已驳回；已通过→已退订）
--          审核通过/驳回时若未填审核时间则自动补当前时间
DROP TRIGGER IF EXISTS trg_ord_before_upd $$
CREATE TRIGGER trg_ord_before_upd
BEFORE UPDATE ON subscription
FOR EACH ROW
BEGIN
    IF NOT (OLD.order_status <=> NEW.order_status) THEN
        IF NOT ( (OLD.order_status = '待审核' AND NEW.order_status IN ('已通过','已驳回'))
              OR (OLD.order_status = '已通过' AND NEW.order_status = '已退订') ) THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = '非法的订单状态变更：待审核→已通过/已驳回，已通过→已退订';
        END IF;
    END IF;
    IF OLD.order_status = '待审核' AND NEW.order_status IN ('已通过','已驳回')
       AND NEW.audit_time IS NULL THEN
        SET NEW.audit_time = NOW();
    END IF;
END $$

-- 触发器5：订单状态变更自动写入操作日志
DROP TRIGGER IF EXISTS trg_ord_after_upd $$
CREATE TRIGGER trg_ord_after_upd
AFTER UPDATE ON subscription
FOR EACH ROW
BEGIN
    IF NOT (OLD.order_status <=> NEW.order_status) THEN
        INSERT INTO op_log (sub_id, op_type, op_content)
        VALUES (COALESCE(NEW.auditor_id, NEW.orderer_id), '审核',
                CONCAT('订单 ', NEW.order_id, ' 状态变更：',
                       OLD.order_status, ' → ', NEW.order_status));
    END IF;
END $$

-- 触发器6：新增订阅人员自动写日志
DROP TRIGGER IF EXISTS trg_sub_after_ins $$
CREATE TRIGGER trg_sub_after_ins
AFTER INSERT ON subscriber
FOR EACH ROW
BEGIN
    INSERT INTO op_log (sub_id, op_type, op_content)
    VALUES (NEW.sub_id, '录入', CONCAT('新增订阅人员：', NEW.sub_name, '（', NEW.role, '）'));
END $$

-- 触发器7：新增报刊自动写日志
DROP TRIGGER IF EXISTS trg_pub_after_ins $$
CREATE TRIGGER trg_pub_after_ins
AFTER INSERT ON publication
FOR EACH ROW
BEGIN
    INSERT INTO op_log (sub_id, op_type, op_content)
    VALUES (NEW.maintainer, '录入', CONCAT('新增报刊：', NEW.pub_name, '，单价 ', NEW.unit_price, ' 元'));
END $$

DELIMITER ;
