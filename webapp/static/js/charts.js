/* =====================================================================
   charts.js · ECharts 图表主题与页面初始化
   配色沿用站点令牌：刊头红 / 藏蓝 / 橄榄 / 青 / 赭 / 灰蓝
   ===================================================================== */
(function () {
  "use strict";

  var PALETTE = ["#A6341B", "#31465A", "#7A7E46", "#3E7C7B",
                 "#8C6A3F", "#5C5F70", "#B08A3E", "#4E7A5A", "#7B5A6E"];
  var INK = "#1F2328", INK2 = "#5C6470", LINE = "#E4E2DB";

  var BASE = {
    color: PALETTE,
    textStyle: { fontFamily: "'Microsoft YaHei','PingFang SC',sans-serif" },
    grid: { left: 8, right: 18, top: 36, bottom: 8, containLabel: true },
    tooltip: {
      borderWidth: 1,
      borderColor: LINE,
      textStyle: { color: INK, fontSize: 12.5 },
      backgroundColor: "#FFFFFF"
    }
  };

  function axis(num) {
    return {
      axisLine: { lineStyle: { color: LINE } },
      axisTick: { show: false },
      axisLabel: { color: INK2, fontSize: 11.5 },
      splitLine: num ? { lineStyle: { color: LINE, type: "dashed" } } : { show: false }
    };
  }

  var instances = [];
  function make(id, option) {
    var el = document.getElementById(id);
    if (!el || typeof echarts === "undefined") return null;
    var chart = echarts.init(el);
    chart.setOption(Object.assign({}, BASE, option));
    instances.push(chart);
    return chart;
  }

  window.addEventListener("resize", function () {
    instances.forEach(function (c) { c.resize(); });
  });

  /* ---------- 工作台 ---------- */
  window.initDashboardCharts = function (data, scope) {
    make("chart-trend", {
      xAxis: Object.assign({ type: "category", data: data.trend.labels }, axis(false)),
      yAxis: Object.assign({ type: "value" }, axis(true)),
      series: [{
        name: "订阅金额（元）",
        type: "line",
        data: data.trend.amts,
        smooth: false,
        symbol: "circle",
        symbolSize: 7,
        lineStyle: { width: 2.5, color: PALETTE[0] },
        itemStyle: { color: PALETTE[0] },
        areaStyle: { color: "rgba(166,52,27,.07)" },
        label: { show: true, position: "top", color: INK2, fontSize: 11,
                 formatter: function (p) { return p.value ? p.value : ""; } }
      }]
    });

    if (scope === "admin") {
      make("chart-cat", {
        tooltip: { trigger: "item", formatter: "{b}<br/>¥{c}（{d}%）" },
        legend: { bottom: 0, type: "scroll", textStyle: { color: INK2, fontSize: 11.5 },
                  pageIconSize: 9 },
        series: [{
          type: "pie",
          radius: ["42%", "68%"],
          center: ["50%", "44%"],
          itemStyle: { borderColor: "#fff", borderWidth: 2 },
          label: { show: false },
          data: data.cat.map(function (d) { return { name: d[0], value: d[1] }; })
        }]
      });
    } else {
      make("chart-cat", {
        xAxis: Object.assign({ type: "category", data: data.top.map(function (d) { return d[0]; }),
                               axisLabel: { color: INK2, fontSize: 11, rotate: 24,
                                            interval: 0, formatter: trim } }, axis(false)),
        yAxis: Object.assign({ type: "value" }, axis(true)),
        series: [{ type: "bar", data: data.top.map(function (d) { return d[2]; }),
                   itemStyle: { color: PALETTE[1] }, barMaxWidth: 26 }]
      });
    }

    make("chart-status", {
      xAxis: Object.assign({ type: "category",
                             data: data.status.map(function (d) { return d[0]; }) }, axis(false)),
      yAxis: Object.assign({ type: "value", minInterval: 1 }, axis(true)),
      series: [{
        type: "bar",
        data: data.status.map(function (d, i) {
          return { value: d[1],
                   itemStyle: { color: [PALETTE[4], PALETTE[1], PALETTE[0], "#9298A1"][i] } };
        }),
        barMaxWidth: 34,
        label: { show: true, position: "top", color: INK2, fontSize: 11.5 }
      }]
    });

    make("chart-top", {
      xAxis: Object.assign({ type: "value" }, axis(true)),
      yAxis: Object.assign({ type: "category",
                             data: data.top.map(function (d) { return d[0]; }).reverse(),
                             axisLabel: { color: INK, fontSize: 11.5, width: 150,
                                          overflow: "truncate" } }, axis(false)),
      series: [{
        name: "订阅金额（元）",
        type: "bar",
        data: data.top.map(function (d) { return d[2]; }).reverse(),
        itemStyle: { color: PALETTE[0] },
        barMaxWidth: 16,
        label: { show: true, position: "right", color: INK2, fontSize: 11,
                 formatter: function (p) { return "¥" + p.value; } }
      }]
    });
  };

  /* ---------- 统计分析 ---------- */
  window.initStatsCharts = function (trend, pubTop, pubPie, deptTop) {
    make("chart-trend", {
      xAxis: Object.assign({ type: "category", data: trend.labels,
                             axisLabel: { color: INK2, fontSize: 11, rotate: 32 } }, axis(false)),
      yAxis: Object.assign({ type: "value" }, axis(true)),
      series: [{
        name: "订阅金额（元）",
        type: "bar",
        data: trend.amts,
        itemStyle: { color: PALETTE[1] },
        barMaxWidth: 18
      }]
    });

    make("chart-pie", {
      tooltip: { trigger: "item", formatter: "{b}<br/>¥{c}（{d}%）" },
      legend: { type: "scroll", orient: "vertical", right: 4, top: "middle",
                textStyle: { color: INK2, fontSize: 11.5 } },
      series: [{
        type: "pie",
        radius: ["38%", "66%"],
        center: ["38%", "50%"],
        itemStyle: { borderColor: "#fff", borderWidth: 2 },
        label: { show: false },
        data: pubPie.map(function (d) { return { name: d[0], value: d[1] }; })
      }]
    });

    make("chart-pub", {
      xAxis: Object.assign({ type: "value" }, axis(true)),
      yAxis: Object.assign({ type: "category",
                             data: pubTop.map(function (d) { return d[0]; }).reverse(),
                             axisLabel: { color: INK, fontSize: 11.5, width: 150,
                                          overflow: "truncate" } }, axis(false)),
      series: [{
        name: "订阅份数",
        type: "bar",
        data: pubTop.map(function (d) { return d[1]; }).reverse(),
        itemStyle: { color: PALETTE[2] },
        barMaxWidth: 14
      }, {
        name: "订阅金额（元）",
        type: "bar",
        data: pubTop.map(function (d) { return d[2]; }).reverse(),
        itemStyle: { color: PALETTE[0] },
        barMaxWidth: 14
      }]
    });

    if (document.getElementById("chart-dept") && deptTop && deptTop.length) {
      make("chart-dept", {
        xAxis: Object.assign({ type: "value" }, axis(true)),
        yAxis: Object.assign({ type: "category",
                               data: deptTop.map(function (d) { return d[0]; }).reverse(),
                               axisLabel: { color: INK, fontSize: 11.5, width: 150,
                                            overflow: "truncate" } }, axis(false)),
        series: [{
          name: "订阅金额（元）",
          type: "bar",
          data: deptTop.map(function (d) { return d[1]; }).reverse(),
          itemStyle: { color: PALETTE[3] },
          barMaxWidth: 14
        }]
      });
    }
  };

  function trim(name) {
    return name.length > 6 ? name.slice(0, 6) + "…" : name;
  }
})();
