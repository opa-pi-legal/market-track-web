import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.2/firebase-app.js";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
} from "https://www.gstatic.com/firebasejs/11.0.2/firebase-auth.js";

function getCsrfToken() {
  const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
  if (input && input.value) return input.value;
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function showGoogleError(message) {
  const box = document.getElementById("googleAuthError");
  if (!box) return;
  box.textContent = message;
  box.classList.remove("d-none");
}

function clearGoogleError() {
  const box = document.getElementById("googleAuthError");
  if (!box) return;
  box.textContent = "";
  box.classList.add("d-none");
}

function initGoogleLogin() {
  const btn = document.getElementById("googleLoginBtn");
  const configEl = document.getElementById("firebase-web-config");
  if (!btn || !configEl) return;

  let config = {};
  try {
    config = JSON.parse(configEl.textContent || "{}");
  } catch (_) {
    return;
  }

  if (!config.apiKey || !config.authDomain || !config.projectId) {
    return;
  }

  const app = initializeApp(config);
  const auth = getAuth(app);
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });

  const endpoint = btn.getAttribute("data-google-endpoint") || "/auth/google/";
  const labelEl = btn.querySelector("span");
  const originalLabel = labelEl ? labelEl.textContent : "Continuar com Google";

  btn.addEventListener("click", async function (event) {
    event.preventDefault();
    clearGoogleError();
    btn.classList.add("disabled");
    btn.setAttribute("aria-disabled", "true");
    if (labelEl) labelEl.textContent = "Conectando ao Google...";

    try {
      const result = await signInWithPopup(auth, provider);
      const idToken = await result.user.getIdToken(true);

      const resp = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        credentials: "same-origin",
        body: JSON.stringify({ id_token: idToken }),
      });

      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        await signOut(auth).catch(() => {});
        showGoogleError(data.error || "Não foi possível entrar com sua conta Google.");
        return;
      }

      window.location.href = data.redirect_url || "/dashboard/";
    } catch (err) {
      await signOut(auth).catch(() => {});
      const code = err && err.code ? String(err.code) : "";
      if (code === "auth/popup-closed-by-user" || code === "auth/cancelled-popup-request") {
        // Usuário fechou o popup voluntariamente
        return;
      }
      if (code === "auth/unauthorized-domain") {
        showGoogleError(
          `Domínio "${window.location.hostname}" não autorizado no Firebase Authentication. Adicione este endereço em Firebase Console → Authentication → Settings → Authorized domains.`
        );
        return;
      }
      if (code === "auth/popup-blocked") {
        showGoogleError("O navegador bloqueou o popup do Google. Libere popups para este site e tente novamente.");
        return;
      }
      showGoogleError("Erro ao autenticar com o Google. Tente novamente.");
    } finally {
      btn.classList.remove("disabled");
      btn.removeAttribute("aria-disabled");
      if (labelEl) labelEl.textContent = originalLabel;
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initGoogleLogin);
} else {
  initGoogleLogin();
}
