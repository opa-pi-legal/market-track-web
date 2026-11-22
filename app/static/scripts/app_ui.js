(function () {
  document.addEventListener("DOMContentLoaded", function () {
    // 1. Toasts flutuantes com auto-dismiss suave
    document.querySelectorAll(".mt-toast-item").forEach(function (el) {
      if (window.bootstrap && window.bootstrap.Toast) {
        const t = new window.bootstrap.Toast(el, { delay: 4500, autohide: true });
        t.show();
      }
    });

    // 2. Modal de confirmação estilizado substituindo window.confirm()
    const modalEl = document.getElementById("mtConfirmModal");
    const titleEl = document.getElementById("mtConfirmTitle");
    const bodyEl = document.getElementById("mtConfirmBody");
    const okBtn = document.getElementById("mtConfirmOkBtn");
    let pendingForm = null;
    let bsModal = null;

    if (modalEl && window.bootstrap && window.bootstrap.Modal) {
      bsModal = new window.bootstrap.Modal(modalEl);
    }

    document.querySelectorAll("form[data-mt-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (form.dataset.mtConfirmed === "true") {
          return;
        }
        if (!bsModal) return;
        event.preventDefault();
        pendingForm = form;
        if (titleEl) titleEl.textContent = form.dataset.mtConfirmTitle || "Confirmar ação";
        if (bodyEl) bodyEl.textContent = form.dataset.mtConfirm || "Deseja continuar?";
        if (okBtn) {
          okBtn.textContent = form.dataset.mtConfirmBtn || "Confirmar";
          const isDanger = form.dataset.mtConfirmDanger !== "false";
          okBtn.className = isDanger ? "mt-btn-danger py-2 px-3" : "mt-btn-primary py-2 px-3";
        }
        bsModal.show();
      });
    });

    if (okBtn) {
      okBtn.addEventListener("click", function () {
        if (!pendingForm) return;
        const target = pendingForm;
        pendingForm = null;
        target.dataset.mtConfirmed = "true";
        if (bsModal) bsModal.hide();
        target.submit();
      });
    }

    // 3. Copiar para área de transferência (EAN, IDs, etc.)
    document.querySelectorAll("[data-mt-copy]").forEach(function (btn) {
      btn.addEventListener("click", async function (event) {
        event.preventDefault();
        event.stopPropagation();
        const text = btn.getAttribute("data-mt-copy") || "";
        if (!text) return;
        try {
          await navigator.clipboard.writeText(text);
          const originalHtml = btn.innerHTML;
          btn.innerHTML = '<i class="bi bi-check2 text-success"></i>';
          setTimeout(function () {
            btn.innerHTML = originalHtml;
          }, 1500);
        } catch (_) {}
      });
    });

    // 4. Estado de carregamento em botões de submit para evitar clique duplo
    document.querySelectorAll("form").forEach(function (form) {
      form.addEventListener("submit", function () {
        if (form.dataset.mtConfirm && form.dataset.mtConfirmed !== "true") {
          return;
        }
        const btn = form.querySelector('button[type="submit"]:not([data-no-spinner])');
        if (!btn || btn.disabled) return;
        setTimeout(function () {
          btn.disabled = true;
          btn.classList.add("opacity-75");
        }, 10);
      });
    });
  });
})();
