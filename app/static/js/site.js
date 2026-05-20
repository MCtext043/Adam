function adamGetCart() {
  try {
    return JSON.parse(localStorage.getItem("adamCart") || "{}");
  } catch {
    return {};
  }
}

function adamCartItemCount(cart) {
  return Object.values(cart).reduce((sum, n) => sum + Number(n || 0), 0);
}

function updateNavCartCount() {
  const cart = adamGetCart();
  const count = adamCartItemCount(cart);
  const badge = document.getElementById("navCartBadge");
  if (!badge) return;
  if (count > 0) {
    badge.textContent = String(count);
    badge.classList.remove("hidden");
    badge.setAttribute("aria-label", `Товаров в корзине: ${count}`);
  } else {
    badge.textContent = "0";
    badge.classList.add("hidden");
    badge.removeAttribute("aria-label");
  }
}

function showAdamToast(message) {
  const host = document.getElementById("toastHost");
  if (!host) return;
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  host.appendChild(el);
  requestAnimationFrame(() => el.classList.add("toast-visible"));
  setTimeout(() => {
    el.classList.remove("toast-visible");
    setTimeout(() => el.remove(), 280);
  }, 3400);
}

async function hydrateAuthNav() {
  const slot = document.getElementById("authNavSlot");
  if (!slot) return;
  try {
    const response = await fetch("/api/auth/me", { credentials: "same-origin" });
    if (!response.ok) return;
    const data = await response.json();
    if (data.authenticated) {
      const label = (data.name || data.email || "Профиль").replace(/</g, "");
      slot.innerHTML =
        `<a class="nav-btn" href="/account" title="Личный кабинет">${label}</a>` +
        '<button type="button" class="nav-btn nav-btn-outline" id="logoutNavBtn">Выйти</button>';
      document.getElementById("logoutNavBtn")?.addEventListener("click", async () => {
        await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
        window.location.reload();
      });
    }
  } catch {
    /* ignore */
  }
}

function setupMobileNav() {
  const toggle = document.getElementById("navMenuToggle");
  const links = document.getElementById("primaryNavLinks");
  if (!toggle || !links) return;
  toggle.addEventListener("click", () => {
    const open = links.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
  links.querySelectorAll("a, button").forEach((el) =>
    el.addEventListener("click", () => {
      links.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    }),
  );
}

window.updateNavCartCount = updateNavCartCount;
window.showAdamToast = showAdamToast;

document.addEventListener("DOMContentLoaded", () => {
  updateNavCartCount();
  hydrateAuthNav();
  setupMobileNav();
});
