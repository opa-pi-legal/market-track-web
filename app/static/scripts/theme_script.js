(function () {
  const STORAGE_KEY = "mt-theme";

  function getPreferredTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "dark" || saved === "light") {
      return saved;
    }
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.setAttribute("data-bs-theme", theme);

    document.querySelectorAll("[data-mt-theme-toggle]").forEach(function (btn) {
      const icon = btn.querySelector("i");
      const label = btn.querySelector("span");
      const isDark = theme === "dark";
      btn.setAttribute("aria-pressed", String(isDark));
      btn.setAttribute("title", isDark ? "Alternar para modo claro" : "Alternar para modo escuro");
      if (icon) {
        icon.className = isDark ? "bi bi-sun-fill" : "bi bi-moon-stars-fill";
      }
      if (label) {
        label.textContent = isDark ? "Claro" : "Escuro";
      }
    });

    window.dispatchEvent(new CustomEvent("mt-theme-change", { detail: { theme: theme } }));
  }

  applyTheme(getPreferredTheme());

  document.addEventListener("DOMContentLoaded", function () {
    applyTheme(document.documentElement.getAttribute("data-theme") || getPreferredTheme());

    document.querySelectorAll("[data-mt-theme-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const current = document.documentElement.getAttribute("data-theme") || "light";
        const next = current === "dark" ? "light" : "dark";
        localStorage.setItem(STORAGE_KEY, next);
        applyTheme(next);
      });
    });
  });
})();
