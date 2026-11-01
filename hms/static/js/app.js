/* =====================================================================
   Ujjwal Hostel — front-end behaviour
   Sidebar, dropdowns, toasts, modals, dark mode, form guards, charts
   ===================================================================== */
(function () {
  "use strict";

  /* ---------------------------------------------------------------- icons */
  function paintIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
  }
  document.addEventListener("DOMContentLoaded", paintIcons);
  if (document.readyState !== "loading") paintIcons();

  /* ------------------------------------------------------------- dark mode */
  const THEME_KEY = "hms-theme";
  function applyTheme(mode) {
    document.body.classList.toggle("dark", mode === "dark");
    document.documentElement.style.colorScheme = mode === "dark" ? "dark" : "light";
    document.querySelectorAll("[data-theme-icon]").forEach(function (el) {
      el.setAttribute("data-lucide", mode === "dark" ? "sun" : "moon");
    });
    paintIcons();
    redrawCharts();
  }

  // Charts bake their palette (grid / tick colours) in at creation time, so they
  // are rebuilt from the stored config whenever the theme changes.
  const CHART_REGISTRY = {};
  function redrawCharts() {
    if (!window.Chart) return;
    Object.keys(CHART_REGISTRY).forEach(function (id) {
      const cfg = CHART_REGISTRY[id];
      const existing = window.Chart.getChart(id);
      if (existing) existing.destroy();
      if (window.HMS_CHART) window.HMS_CHART(id, cfg, true);
    });
  }
  let storedTheme = null;
  try { storedTheme = localStorage.getItem(THEME_KEY); } catch (e) {}
  if (storedTheme) applyTheme(storedTheme);

  document.addEventListener("click", function (e) {
    const toggle = e.target.closest("[data-theme-toggle]");
    if (!toggle) return;
    e.preventDefault();
    const next = document.body.classList.contains("dark") ? "light" : "dark";
    try { localStorage.setItem(THEME_KEY, next); } catch (err) {}
    applyTheme(next);
  });

  /* --------------------------------------------------------------- sidebar */
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-nav-toggle]")) {
      document.body.classList.toggle("nav-open");
      return;
    }
    if (e.target.closest(".nav-scrim")) document.body.classList.remove("nav-open");
    const link = e.target.closest(".sidebar .nav-link");
    if (link && window.innerWidth <= 1024) document.body.classList.remove("nav-open");
  });

  /* ------------------------------------------------------------- dropdowns */
  document.addEventListener("click", function (e) {
    const trigger = e.target.closest("[data-dropdown]");
    document.querySelectorAll(".dropdown.open").forEach(function (dd) {
      if (!trigger || dd !== trigger.closest(".dropdown")) dd.classList.remove("open");
    });
    if (trigger) {
      e.preventDefault();
      const dd = trigger.closest(".dropdown");
      if (dd) dd.classList.toggle("open");
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      document.querySelectorAll(".dropdown.open").forEach(function (d) { d.classList.remove("open"); });
    }
  });

  /* ----------------------------------------------------------------- toasts */
  function dismissToast(toast) {
    toast.classList.add("hide");
    setTimeout(function () { toast.remove(); }, 260);
  }
  window.showToast = function (message, category, icon) {
    let stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      document.body.appendChild(stack);
    }
    const el = document.createElement("div");
    el.className = "toast " + (category || "info");
    el.setAttribute("role", "status");
    el.innerHTML =
      '<i data-lucide="' + (icon || "info") + '" class="i"></i>' +
      "<div>" + message + "</div>" +
      '<button class="t-close" type="button" aria-label="Dismiss"><i data-lucide="x" class="i-sm"></i></button>';
    stack.appendChild(el);
    paintIcons();
    const close = el.querySelector(".t-close");
    if (close) close.addEventListener("click", function () { dismissToast(el); });
    setTimeout(function () { dismissToast(el); }, 6000);
  };
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".toast[data-autohide]").forEach(function (t) {
      setTimeout(function () { dismissToast(t); }, 6000);
    });
  });

  /* -------------------------------------------------------------- modals */
  window.openModal = function (id) {
    const dlg = document.getElementById(id);
    if (dlg && typeof dlg.showModal === "function") { dlg.showModal(); }
  };
  window.closeModal = function (id) {
    const dlg = document.getElementById(id);
    if (dlg && dlg.open) dlg.close();
  };
  document.addEventListener("click", function (e) {
    const opener = e.target.closest("[data-modal-open]");
    if (opener) {
      e.preventDefault();
      const id = opener.getAttribute("data-modal-open");
      // optional: prefill fields from data-* attributes
      const dlg = document.getElementById(id);
      if (dlg) {
        Array.prototype.forEach.call(opener.attributes, function (attr) {
          if (attr.name.indexOf("data-field-") === 0) {
            const name = attr.name.replace("data-field-", "");
            const input = dlg.querySelector('[name="' + name + '"]');
            if (input) input.value = attr.value;
            const label = dlg.querySelector('[data-label="' + name + '"]');
            if (label) label.textContent = attr.value;
            const action = dlg.querySelector("form");
            if (name === "form_action" && action) action.setAttribute("action", attr.value);
          }
        });
      }
      window.openModal(id);
      return;
    }
    const closer = e.target.closest("[data-modal-close]");
    if (closer) {
      e.preventDefault();
      const dlg = closer.closest("dialog");
      if (dlg) dlg.close();
    }
    // click on the backdrop closes
    if (e.target.tagName === "DIALOG") e.target.close();
  });

  /* ------------------------------------------- confirmations before delete */
  document.addEventListener("submit", function (e) {
    const form = e.target;
    const confirmMsg = form.getAttribute("data-confirm");
    if (confirmMsg && !window.confirm(confirmMsg)) {
      e.preventDefault();
      return;
    }
    // button loading state (purely visual, form still submits)
    const btn = form.querySelector('button[type="submit"]:not([data-no-spinner])');
    if (btn) setTimeout(function () { btn.classList.add("is-loading"); }, 0);
  });

  /* ---------------------------------------------------------- client checks */
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-validate]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        const pw = form.querySelector('input[name="password"]');
        const cpw = form.querySelector('input[name="confirm_password"]');
        if (pw && cpw && pw.value !== cpw.value) {
          e.preventDefault();
          window.showToast("Passwords do not match.", "danger");
          cpw.focus();
          return;
        }
        if (pw && pw.value.length < 8) {
          e.preventDefault();
          window.showToast("Password must be at least 8 characters.", "danger");
          pw.focus();
        }
      });
    });

    /* auto-submit filter forms on change */
    document.querySelectorAll("form[data-autosubmit] select").forEach(function (sel) {
      sel.addEventListener("change", function () { sel.form.submit(); });
    });

    /* animate cards in */
    document.querySelectorAll("[data-anim]").forEach(function (el, i) {
      el.style.animationDelay = Math.min(i * 45, 320) + "ms";
      el.classList.add("reveal-in");
    });

    /* header shadow on scroll */
    const header = document.querySelector(".site-header");
    if (header) {
      const onScroll = function () {
        header.classList.toggle("scrolled", window.scrollY > 8);
      };
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }
  });

  /* ------------------------------------------------------------ charts */
  const PALETTE = ["#2f4bff", "#7c3aed", "#06b6d4", "#f97316", "#10b981", "#ec4899", "#0ea5e9", "#f59e0b"];
  const isDark = function () { return document.body.classList.contains("dark"); };
  function deepMerge(target, source) {
    if (!source || typeof source !== "object") return target;
    const out = Object.assign({}, target);
    Object.keys(source).forEach(function (key) {
      const sv = source[key];
      const tv = out[key];
      if (sv && typeof sv === "object" && !Array.isArray(sv) && tv && typeof tv === "object" && !Array.isArray(tv)) {
        out[key] = deepMerge(tv, sv);
      } else if (sv !== undefined) {
        out[key] = sv;
      }
    });
    return out;
  }

  window.HMS_CHART = function (canvasId, config, isRedraw) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return null;
    if (!isRedraw) CHART_REGISTRY[canvasId] = config;

    // Templates may pass `scales` / `plugins` either at the top level or inside
    // `options`. Normalise both into a proper Chart.js `options` object.
    const inline = Object.assign({}, config.options || {});
    if (config.scales !== undefined) inline.scales = config.scales;
    if (config.plugins !== undefined) inline.plugins = config.plugins;

    const noise = isDark() ? "rgba(34,48,85,.7)" : "#eef2fa";
    const tickColor = isDark() ? "#93a1c1" : "#6b7a99";
    const baseOptions = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          display: false,
          position: "bottom",
          labels: {
            color: isDark() ? "#c2cbe6" : "#33415c",
            boxWidth: 10,
            boxHeight: 10,
            usePointStyle: true,
            padding: 14,
            font: { family: "InterVar, Inter, sans-serif", size: 11 },
          },
        },
        tooltip: {
          backgroundColor: "#0b1230",
          padding: 10,
          cornerRadius: 10,
          titleFont: { size: 12, weight: "600" },
          bodyFont: { size: 12 },
          displayColors: true,
          boxPadding: 4,
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: tickColor, font: { size: 11 } },
          border: { color: isDark() ? "#223055" : "#e7ecf6" },
        },
        y: {
          beginAtZero: true,
          grid: { color: noise },
          ticks: { color: tickColor, font: { size: 11 } },
          border: { display: false },
        },
      },
    };

    const chartType = config.type || "bar";
    const options = deepMerge(baseOptions, inline);
    if (
      inline.scales === false ||
      ["doughnut", "pie", "polarArea", "radar"].indexOf(chartType) !== -1
    ) {
      delete options.scales;
    }

    const data = config.data || { labels: [], datasets: [] };
    (data.datasets || []).forEach(function (ds, i) {
      if (!ds.backgroundColor) ds.backgroundColor = PALETTE[i % PALETTE.length];
      if (ds.type === "line") {
        if (ds.tension === undefined) ds.tension = 0.38;
        if (!ds.borderWidth) ds.borderWidth = 2.5;
        if (ds.pointRadius === undefined) ds.pointRadius = 3;
        if (ds.fill === undefined) ds.fill = false;
        if (!ds.borderColor) ds.borderColor = PALETTE[i % PALETTE.length];
      }
      if (ds.type === "bar" && !ds.borderRadius) ds.borderRadius = 8;
    });

    return new Chart(canvas, {
      type: chartType,
      data: data,
      options: options,
    });
  };

  /* ----------------------------------------------------------------- tabs */
  document.addEventListener("click", function (e) {
    const tab = e.target.closest("[data-tab]");
    if (!tab) return;
    e.preventDefault();
    const group = tab.closest("[data-tab-group]") || document;
    group.querySelectorAll("[data-tab]").forEach(function (t) { t.classList.remove("active"); });
    tab.classList.add("active");
    group.querySelectorAll("[data-tab-panel]").forEach(function (p) {
      p.classList.toggle("hidden", p.getAttribute("data-tab-panel") !== tab.getAttribute("data-tab"));
    });
  });

  /* ------------------------------------------------------- print helpers */
  window.printPage = function () { window.print(); };
})();
