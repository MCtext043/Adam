const page = document.body.dataset.page;

function setAuthMessage(el, text, type) {
  if (!el) return;
  el.textContent = text || "";
  el.className = text ? `form-message ${type}` : "form-message";
}

if (page === "login") {
  const form = document.getElementById("loginForm");
  const msg = document.getElementById("authMessage");
  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const payload = {
      email: String(fd.get("email") || "").trim(),
      password: String(fd.get("password") || ""),
    };
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || "Не удалось войти");
      }
      window.location.href = "/";
    } catch (error) {
      setAuthMessage(msg, error.message, "error");
    }
  });
}

if (page === "register") {
  const form = document.getElementById("registerForm");
  const msg = document.getElementById("authMessage");
  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const payload = {
      display_name: String(fd.get("display_name") || "").trim(),
      email: String(fd.get("email") || "").trim(),
      phone: String(fd.get("phone") || "").trim(),
      password: String(fd.get("password") || ""),
    };
    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || "Не удалось зарегистрироваться");
      }
      setAuthMessage(msg, "Аккаунт создан. Сейчас перенаправим на вход…", "success");
      setTimeout(() => {
        window.location.href = "/login";
      }, 900);
    } catch (error) {
      setAuthMessage(msg, error.message, "error");
    }
  });
}

if (page === "account") {
  const lead = document.getElementById("accountLead");
  const card = document.getElementById("accountCard");
  const pointsEl = document.getElementById("loyaltyPoints");

  fetch("/api/auth/me", { credentials: "same-origin" })
    .then((r) => r.json())
    .then((data) => {
      if (!data.authenticated) {
        window.location.href = "/login";
        return;
      }
      if (lead) {
        lead.textContent = `${data.name || "Гость"}, добро пожаловать.`;
      }
      if (pointsEl) pointsEl.textContent = String(data.loyalty_points ?? 0);
      card?.removeAttribute("hidden");
    })
    .catch(() => {
      if (lead) lead.textContent = "Не удалось загрузить профиль.";
    });
}
