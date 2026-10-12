/* =====================================================================
   order_form.js · 新建订阅单：明细行增删、单价联动、金额实时计算
   ===================================================================== */
(function () {
  "use strict";

  var rows = document.getElementById("item-rows");
  if (!rows) return;
  var addBtn = document.getElementById("add-item");
  var form = document.getElementById("order-form");

  var pubTpl = function () {
    // 克隆首行的报刊下拉（optgroup 结构保持一致），清空选择
    var sel = rows.querySelector(".pub-pick").cloneNode(true);
    sel.value = "";
    return sel;
  };

  function money(n) {
    return (Math.round(n * 100) / 100).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function rowPrice(row) {
    var pick = row.querySelector(".pub-pick");
    var opt = pick.selectedOptions[0];
    var price = opt && opt.dataset.price ? parseFloat(opt.dataset.price) : 0;
    row.querySelector(".cell-price").textContent =
      price ? price.toFixed(2) : "—";
    return price;
  }

  function recalc() {
    var all = rows.querySelectorAll(".item-row");
    var total = 0, qty = 0, filled = 0;
    all.forEach(function (row) {
      var price = rowPrice(row);
      var q = parseInt(row.querySelector('[name="quantity[]"]').value, 10) || 0;
      var n = parseInt(row.querySelector('[name="periods[]"]').value, 10) || 0;
      var sub = price * q * n;
      row.querySelector(".cell-subtotal").textContent = money(sub);
      if (row.querySelector('[name="pub_id[]"]').value) { filled += 1; qty += q; }
      total += sub;
    });
    document.getElementById("sum-items").textContent = filled;
    document.getElementById("sum-qty").textContent = filled ? qty + " 份" : "—";
    document.getElementById("sum-amount").textContent = money(total);
  }

  function bindRow(row) {
    row.querySelector(".pub-pick").addEventListener("change", recalc);
    row.querySelector('[name="quantity[]"]').addEventListener("input", recalc);
    row.querySelector('[name="periods[]"]').addEventListener("input", recalc);
    row.querySelector(".cell-del .linklike").addEventListener("click", function () {
      if (rows.querySelectorAll(".item-row").length > 1) {
        row.remove();
      } else {
        // 最后一行：清空而不是移除
        row.querySelector(".pub-pick").value = "";
        row.querySelector('[name="quantity[]"]').value = 1;
        row.querySelector('[name="periods[]"]').value = 12;
      }
      recalc();
    });
  }

  addBtn.addEventListener("click", function () {
    var tr = document.createElement("tr");
    tr.className = "item-row";
    tr.innerHTML =
      '<td></td>' +
      '<td class="num cell-price">—</td>' +
      '<td><input class="input num-input" type="number" name="quantity[]" min="1" max="999" value="1"></td>' +
      '<td><input class="input num-input" type="number" name="periods[]" min="1" max="365" value="12"></td>' +
      '<td class="num cell-subtotal strong">0.00</td>' +
      '<td class="cell-del"><button class="linklike danger" type="button" aria-label="删除本行">✕</button></td>';
    tr.firstElementChild.appendChild(pubTpl());
    rows.appendChild(tr);
    bindRow(tr);
    recalc();
    tr.querySelector(".pub-pick").focus();
  });

  rows.querySelectorAll(".item-row").forEach(bindRow);
  recalc();

  /* 提交前把明细行转成合法表单（占位行直接清空 required，由服务端校验兜底） */
  form.addEventListener("submit", function () {
    rows.querySelectorAll(".item-row").forEach(function (row) {
      var pick = row.querySelector(".pub-pick");
      if (!pick.value) {
        pick.removeAttribute("required");
        row.querySelector('[name="quantity[]"]').disabled = true;
        row.querySelector('[name="periods[]"]').disabled = true;
      }
    });
  });
})();
