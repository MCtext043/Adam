const ordersEl = document.querySelector("#orders");
const archiveOrdersEl = document.querySelector("#ordersArchive");
const refreshBtn = document.querySelector("#refreshOrders");
const refreshArchiveBtn = document.querySelector("#refreshArchive");
const settingsForm = document.querySelector("#adminSettingsForm");
const minOrderAmountInput = document.querySelector("#minOrderAmount");
const freeDeliveryThresholdInput = document.querySelector("#freeDeliveryThreshold");
const deliveryPricePerKmInput = document.querySelector("#deliveryPricePerKm");
const settingsMessage = document.querySelector("#settingsMessage");
const adminPageTitle = document.querySelector("#adminPageTitle");
const sectionToday = document.querySelector("#adminSectionToday");
const sectionArchive = document.querySelector("#adminSectionArchive");
const sectionStoplist = document.querySelector("#adminSectionStoplist");
const tabButtons = document.querySelectorAll("[data-admin-tab]");
const enableNotifyBtn = document.querySelector("#enableNotifyBtn");
const adminNotifyStatus = document.querySelector("#adminNotifyStatus");
const stoplistSearch = document.querySelector("#stoplistSearch");
const stoplistAvailableEl = document.querySelector("#stoplistAvailable");
const stoplistStoppedEl = document.querySelector("#stoplistStopped");
const refreshStoplistBtn = document.querySelector("#refreshStoplist");

const ORDER_POLL_MS = 15000;

let activeTab = "today";
let archiveLoaded = false;
let stoplistLoaded = false;
let stoplistProducts = [];
let latestKnownOrderId = 0;
let ordersWatchReady = false;
let soundEnabled = false;
let audioContext = null;
let orderPollTimer = null;

const statusLabels = {
  pending_payment: "Ожидает оплату",
  new: "Новый",
  cooking: "Готовится",
  delivering: "В доставке",
  done: "Готово",
  cancelled: "Отменен",
};

const formatPrice = (value) =>
  new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value);

function formatOrderDate(order) {
  if (order?.created_at_display) return order.created_at_display;
  const value = order?.created_at;
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU", {
    timeZone: "Europe/Samara",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function showToast(message) {
  const host = document.getElementById("toastHost");
  if (!host) return;
  const el = document.createElement("div");
  el.className = "toast toast-admin";
  el.textContent = message;
  host.appendChild(el);
  requestAnimationFrame(() => el.classList.add("toast-visible"));
  window.setTimeout(() => {
    el.classList.remove("toast-visible");
    window.setTimeout(() => el.remove(), 300);
  }, 8000);
}

function getAudioContext() {
  if (!audioContext) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (Ctx) audioContext = new Ctx();
  }
  return audioContext;
}

function playTone(ctx, frequency, startAt, duration) {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = frequency;
  gain.gain.setValueAtTime(0.0001, startAt);
  gain.gain.exponentialRampToValueAtTime(0.28, startAt + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, startAt + duration);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(startAt);
  osc.stop(startAt + duration + 0.05);
}

function playOrderSound() {
  if (!soundEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  const start = ctx.currentTime;
  playTone(ctx, 880, start, 0.18);
  playTone(ctx, 1175, start + 0.22, 0.22);
  playTone(ctx, 880, start + 0.5, 0.18);
}

async function enableSoundNotifications() {
  const ctx = getAudioContext();
  if (ctx?.state === "suspended") {
    await ctx.resume();
  }
  soundEnabled = true;
  if (enableNotifyBtn) enableNotifyBtn.hidden = true;
  if (adminNotifyStatus) adminNotifyStatus.hidden = false;
  playOrderSound();
}

function notifyNewOrders(orderIds) {
  if (!orderIds.length) return;
  const label = orderIds.length === 1 ? `Новый заказ #${orderIds[0]}` : `Новые заказы: ${orderIds.map((id) => `#${id}`).join(", ")}`;
  playOrderSound();
  showToast(label);
  if (document.hidden && "Notification" in window && Notification.permission === "granted") {
    new Notification("Кафе Адам", { body: label });
  }
  document.title = `(${orderIds.length}) ${document.title.replace(/^\(\d+\)\s*/, "")}`;
}

function rememberLatestOrderId(orders) {
  if (!orders.length) return;
  latestKnownOrderId = Math.max(latestKnownOrderId, ...orders.map((order) => order.id));
}

function statusOptions(currentStatus) {
  return window.ORDER_STATUSES.map(
    (status) => `<option value="${status}" ${status === currentStatus ? "selected" : ""}>${statusLabels[status]}</option>`,
  ).join("");
}

function renderOrders(orders, container, { emptyTitle, emptyText }) {
  if (!container) return;

  if (!orders.length) {
    container.innerHTML = `<article class="order-card"><h3>${emptyTitle}</h3><p>${emptyText}</p></article>`;
    return;
  }

  container.innerHTML = orders
    .map((order) => {
      const bonusLine =
        order.loyalty_points_spent > 0
          ? `<p><strong>Бонусы:</strong> списано ${order.loyalty_points_spent}</p>`
          : "";
      const payLine =
        order.payment_status && order.payment_status !== "none"
          ? `<p><strong>Оплата:</strong> ${order.payment_status === "paid" ? "оплачен" : "ожидает"}</p>`
          : "";
      const deliveryAmount =
        order.delivery_fee > 0
          ? `${formatPrice(order.delivery_fee)} (~${order.delivery_distance_km} км)`
          : "бесплатно";
      return `
        <article class="order-card">
          <div class="order-meta">
            <div class="order-meta-main">
              <h3>Заказ #${order.id}</h3>
              <p class="order-date">${formatOrderDate(order)}</p>
            </div>
            <span class="status-pill">${statusLabels[order.status] || order.status}</span>
          </div>
          ${payLine}
          <p><strong>${order.customer_name}</strong> · ${order.phone}</p>
          ${order.customer_email ? `<p><strong>Email:</strong> ${order.customer_email}</p>` : ""}
          <p class="order-address"><strong>Адрес:</strong> ${order.address}</p>
          ${order.comment ? `<p><strong>Комментарий:</strong> ${order.comment}</p>` : ""}
          ${bonusLine}
          <div class="order-lines">
            ${order.items
              .map(
                (item) => `
                  <div class="order-line">
                    <span>${item.product_name} x ${item.quantity}</span>
                    <strong>${formatPrice(item.sum)}</strong>
                  </div>
                `,
              )
              .join("")}
          </div>
          <div class="order-payment-breakdown">
            <div class="cart-total checkout-line">
              <span>За заказ</span>
              <strong>${formatPrice(order.food_total)}</strong>
            </div>
            <div class="cart-total checkout-line">
              <span>За доставку</span>
              <strong>${deliveryAmount}</strong>
            </div>
            <div class="cart-total checkout-total-line">
              <span>Итого к оплате</span>
              <strong>${formatPrice(order.total)}</strong>
            </div>
          </div>
          <label>
            Статус
            <select class="status-select" data-order-status="${order.id}">
              ${statusOptions(order.status)}
            </select>
          </label>
        </article>
      `;
    })
    .join("");
}

async function loadOrders({ silent = false } = {}) {
  if (!ordersEl) return [];
  if (!silent) {
    ordersEl.innerHTML = `<article class="order-card"><p>Загрузка заказов...</p></article>`;
  }
  const response = await fetch("/api/admin/orders", { credentials: "same-origin" });
  if (response.status === 401) {
    window.location.href = "/admin/login";
    return [];
  }
  const orders = await response.json();
  renderOrders(orders, ordersEl, {
    emptyTitle: "Заказов за сегодня нет",
    emptyText: "Новые заказы появятся здесь сразу после оформления на сайте.",
  });
  rememberLatestOrderId(orders);
  ordersWatchReady = true;
  return orders;
}

async function pollForNewOrders() {
  if (document.hidden || activeTab !== "today") return;
  try {
    const response = await fetch(`/api/admin/orders/watch?after=${latestKnownOrderId}`, {
      credentials: "same-origin",
    });
    if (response.status === 401) {
      window.location.href = "/admin/login";
      return;
    }
    if (!response.ok) return;
    const data = await response.json();
    if (ordersWatchReady && data.new_ids?.length) {
      notifyNewOrders(data.new_ids);
      await loadOrders({ silent: true });
    }
    if (data.latest_id) {
      latestKnownOrderId = Math.max(latestKnownOrderId, data.latest_id);
    }
  } catch {
    // ignore transient network errors
  }
}

function startOrderPolling() {
  if (orderPollTimer) return;
  orderPollTimer = window.setInterval(pollForNewOrders, ORDER_POLL_MS);
}

async function loadArchiveOrders() {
  if (!archiveOrdersEl) return;
  archiveOrdersEl.innerHTML = `<article class="order-card"><p>Загрузка архива...</p></article>`;
  const response = await fetch("/api/admin/orders/archive", { credentials: "same-origin" });
  if (response.status === 401) {
    window.location.href = "/admin/login";
    return;
  }
  const orders = await response.json();
  archiveLoaded = true;
  renderOrders(orders, archiveOrdersEl, {
    emptyTitle: "Архив пуст",
    emptyText: "Здесь будут заказы за прошлые дни.",
  });
}

function setActiveTab(tab) {
  activeTab = tab;
  tabButtons.forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.adminTab === tab);
  });

  if (sectionToday) sectionToday.hidden = tab !== "today";
  if (sectionArchive) sectionArchive.hidden = tab !== "archive";
  if (sectionStoplist) sectionStoplist.hidden = tab !== "stoplist";

  if (adminPageTitle) {
    if (tab === "archive") adminPageTitle.textContent = "Архив заказов";
    else if (tab === "stoplist") adminPageTitle.textContent = "Стоп-лист";
    else adminPageTitle.textContent = "Текущие заказы";
  }

  if (tab === "archive" && !archiveLoaded) {
    loadArchiveOrders();
  }
  if (tab === "stoplist" && !stoplistLoaded) {
    loadStoplistProducts();
  }
}

function renderStoplistProducts() {
  const query = (stoplistSearch?.value || "").trim().toLowerCase();
  const filtered = stoplistProducts.filter((product) => {
    if (!query) return true;
    return product.name.toLowerCase().includes(query) || product.category.toLowerCase().includes(query);
  });
  const available = filtered.filter((product) => !product.is_stopped);
  const stopped = filtered.filter((product) => product.is_stopped);

  if (stoplistAvailableEl) {
    stoplistAvailableEl.innerHTML = available.length
      ? available
          .map(
            (product) => `
              <article class="stoplist-item">
                <div class="stoplist-item-info">
                  <p class="stoplist-item-name">${product.name}</p>
                  <p class="stoplist-item-meta">${product.category} · ${formatPrice(product.price)}</p>
                </div>
                <button class="button button-ghost button-sm" type="button" data-stop-product="${product.id}" data-stop-value="1">
                  В стоп
                </button>
              </article>
            `,
          )
          .join("")
      : `<p class="stoplist-empty">${query ? "Ничего не найдено" : "Все позиции в стоп-листе"}</p>`;
  }

  if (stoplistStoppedEl) {
    stoplistStoppedEl.innerHTML = stopped.length
      ? stopped
          .map(
            (product) => `
              <article class="stoplist-item">
                <div class="stoplist-item-info">
                  <p class="stoplist-item-name">${product.name}</p>
                  <p class="stoplist-item-meta">${product.category} · ${formatPrice(product.price)}</p>
                </div>
                <button class="button button-dark button-sm" type="button" data-stop-product="${product.id}" data-stop-value="0">
                  Вернуть
                </button>
              </article>
            `,
          )
          .join("")
      : `<p class="stoplist-empty">${query ? "Ничего не найдено" : "Стоп-лист пуст"}</p>`;
  }
}

async function loadStoplistProducts() {
  if (!stoplistAvailableEl || !stoplistStoppedEl) return;
  stoplistAvailableEl.innerHTML = `<p class="stoplist-empty">Загрузка...</p>`;
  stoplistStoppedEl.innerHTML = "";
  const response = await fetch("/api/admin/products", { credentials: "same-origin" });
  if (response.status === 401) {
    window.location.href = "/admin/login";
    return;
  }
  if (!response.ok) {
    stoplistAvailableEl.innerHTML = `<p class="stoplist-empty">Не удалось загрузить меню</p>`;
    return;
  }
  stoplistProducts = await response.json();
  stoplistLoaded = true;
  renderStoplistProducts();
}

async function toggleStopList(productId, isStopped) {
  const response = await fetch(`/api/admin/products/${productId}/stop-list`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ is_stopped: isStopped }),
  });
  if (response.status === 401) {
    window.location.href = "/admin/login";
    return;
  }
  if (!response.ok) {
    showToast("Не удалось обновить стоп-лист");
    return;
  }
  const updated = await response.json();
  stoplistProducts = stoplistProducts.map((product) => (product.id === updated.id ? updated : product));
  renderStoplistProducts();
  showToast(updated.is_stopped ? `${updated.name} — в стоп-листе` : `${updated.name} — снова в меню`);
}

function handleStoplistClick(event) {
  const button = event.target.closest("[data-stop-product]");
  if (!button) return;
  const isStopped = button.dataset.stopValue === "1";
  toggleStopList(Number(button.dataset.stopProduct), isStopped);
}

async function loadSettings() {
  if (!minOrderAmountInput) return;
  const response = await fetch("/api/admin/settings", { credentials: "same-origin" });
  if (response.status === 401) {
    window.location.href = "/admin/login";
    return;
  }
  if (!response.ok) return;
  const data = await response.json();
  minOrderAmountInput.value = String(Math.round(data.min_order_amount));
  if (freeDeliveryThresholdInput) {
    freeDeliveryThresholdInput.value = String(Math.round(data.free_delivery_threshold || 3000));
  }
  if (deliveryPricePerKmInput) {
    deliveryPricePerKmInput.value = String(Math.round(data.delivery_price_per_km || 45));
  }
}

function showSettingsMessage(text, type) {
  if (!settingsMessage) return;
  settingsMessage.hidden = false;
  settingsMessage.textContent = text;
  settingsMessage.className = `form-message ${type}`;
}

async function saveSettings(event) {
  event.preventDefault();
  if (!minOrderAmountInput) return;

  const value = Number(minOrderAmountInput.value);
  const freeThreshold = Number(freeDeliveryThresholdInput?.value || 3000);
  const pricePerKm = Number(deliveryPricePerKmInput?.value || 45);
  const response = await fetch("/api/admin/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({
      min_order_amount: value,
      free_delivery_threshold: freeThreshold,
      delivery_price_per_km: pricePerKm,
    }),
  });

  if (response.status === 401) {
    window.location.href = "/admin/login";
    return;
  }

  if (!response.ok) {
    showSettingsMessage("Не удалось сохранить настройки", "error");
    return;
  }

  const data = await response.json();
  minOrderAmountInput.value = String(Math.round(data.min_order_amount));
  if (freeDeliveryThresholdInput) {
    freeDeliveryThresholdInput.value = String(Math.round(data.free_delivery_threshold));
  }
  if (deliveryPricePerKmInput) {
    deliveryPricePerKmInput.value = String(Math.round(data.delivery_price_per_km));
  }
  showSettingsMessage("Сохранено", "success");
}

async function updateStatus(orderId, status) {
  const response = await fetch(`/api/admin/orders/${orderId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ status }),
  });

  if (response.status === 401) {
    window.location.href = "/admin/login";
    return;
  }

  if (!response.ok) {
    alert("Не удалось обновить статус заказа");
    return;
  }

  if (activeTab === "archive") {
    await loadArchiveOrders();
  } else {
    await loadOrders();
  }
}

function handleStatusChange(event) {
  const select = event.target.closest("[data-order-status]");
  if (!select) return;
  updateStatus(select.dataset.orderStatus, select.value);
}

ordersEl?.addEventListener("change", handleStatusChange);
archiveOrdersEl?.addEventListener("change", handleStatusChange);

refreshBtn?.addEventListener("click", () => loadOrders());
refreshArchiveBtn?.addEventListener("click", loadArchiveOrders);
refreshStoplistBtn?.addEventListener("click", loadStoplistProducts);
stoplistSearch?.addEventListener("input", renderStoplistProducts);
stoplistAvailableEl?.addEventListener("click", handleStoplistClick);
stoplistStoppedEl?.addEventListener("click", handleStoplistClick);
settingsForm?.addEventListener("submit", saveSettings);
enableNotifyBtn?.addEventListener("click", () => {
  enableSoundNotifications();
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
});

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => setActiveTab(btn.dataset.adminTab));
});

Promise.all([loadSettings(), loadOrders()]).then(() => {
  startOrderPolling();
}).catch(() => {
  if (ordersEl) {
    ordersEl.innerHTML = `<article class="order-card"><h3>Ошибка загрузки</h3><p>Проверьте сервер и подключение к PostgreSQL.</p></article>`;
  }
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    pollForNewOrders();
  }
});
