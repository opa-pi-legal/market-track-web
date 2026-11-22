    document.querySelectorAll(".mt-toggle-password").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const input = document.getElementById(btn.dataset.target);
        const icon = btn.querySelector("i");
        if (!input || !icon) return;

        const isPassword = input.type === "password";
        input.type = isPassword ? "text" : "password";
        icon.classList.toggle("bi-eye", !isPassword);
        icon.classList.toggle("bi-eye-slash", isPassword);
      });
    });