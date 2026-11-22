    (function () {
      const btn = document.getElementById("togglePasswordBtn");
      const input = document.getElementById("id_password");
      const icon = document.getElementById("togglePasswordIcon");

      if (btn && input && icon) {
        btn.addEventListener("click", function () {
          const isPassword = input.type === "password";
          input.type = isPassword ? "text" : "password";
          icon.classList.toggle("bi-eye", !isPassword);
          icon.classList.toggle("bi-eye-slash", isPassword);
        });
      }
    })();