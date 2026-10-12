/* =====================================================================
   app.js · 界面交互：用户菜单 / 侧栏抽屉 / 删除确认 / 提示条 / 打印
   ===================================================================== */
(function () {
  "use strict";

  /* 用户菜单 */
  var whoBtn = document.getElementById("who-btn");
  var whoMenu = document.getElementById("who-menu");
  if (whoBtn && whoMenu) {
    whoBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      whoMenu.hidden = !whoMenu.hidden;
    });
    document.addEventListener("click", function (e) {
      if (!whoMenu.hidden && !whoMenu.contains(e.target)) whoMenu.hidden = true;
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") whoMenu.hidden = true;
    });
  }

  /* 移动端侧栏 */
  var burger = document.getElementById("burger");
  var mask = document.getElementById("mask");
  if (burger && mask) {
    burger.addEventListener("click", function () {
      document.body.classList.toggle("side-open");
      mask.hidden = !document.body.classList.contains("side-open");
    });
    mask.addEventListener("click", function () {
      document.body.classList.remove("side-open");
      mask.hidden = true;
    });
  }

  /* 危险操作确认 */
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form.dataset && form.dataset.confirm) {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    }
  });

  /* 提示条自动消失 */
  var toasts = document.getElementById("toasts");
  if (toasts) {
    setTimeout(function () {
      Array.prototype.forEach.call(toasts.children, function (t) {
        t.style.transition = "opacity .4s";
        t.style.opacity = "0";
        setTimeout(function () { t.remove(); }, 450);
      });
    }, 3600);
  }

  /* 打印按钮 */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-print]");
    if (btn) window.print();
  });

  /* 类别编辑表单填充（categories 页联动） */
  var catForm = document.getElementById("cat-form");
  if (catForm) {
    document.addEventListener("click", function (e) {
      var b = e.target.closest("[data-fill-form]");
      if (!b) return;
      catForm.querySelector('[name="cat_name"]').value = b.dataset.name || "";
      catForm.querySelector('[name="cat_desc"]').value = b.dataset.desc || "";
      catForm.action = catForm.action.replace(/\/categories\/[^/]+$/, "") +
        "/categories/" + b.dataset.id + "/edit";
      document.getElementById("cat-form-title").textContent = "编辑类别 " + b.dataset.id;
      catForm.scrollIntoView({ behavior: "smooth" });
    });
    var reset = document.getElementById("cat-reset");
    if (reset) reset.addEventListener("click", function () {
      document.getElementById("cat-form-title").textContent = "新增类别";
    });
  }
})();
