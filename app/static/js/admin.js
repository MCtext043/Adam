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
const tabButtons = document.querySelectorAll("[data-admin-tab]");

let activeTab = "today";
let archiveLoaded = false;

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

async function loadOrders() {
  if (!ordersEl) return;
  ordersEl.innerHTML = `<article class="order-card"><p>Загрузка заказов...</p></article>`;
  const response = await fetch("/api/admin/orders", { credentials: "same-origin" });
  if (response.status === 401) {
    window.location.href = "/admin/login";
    return;
  }
  const orders = await response.json();
  renderOrders(orders, ordersEl, {
    emptyTitle: "Заказов за сегодня нет",
    emptyText: "Новые заказы появятся здесь сразу после оформления на сайте.",
  });
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

  if (adminPageTitle) {
    adminPageTitle.textContent = tab === "archive" ? "Архив заказов" : "Текущие заказы";
  }

  if (tab === "archive" && !archiveLoaded) {
    loadArchiveOrders();
  }
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

refreshBtn?.addEventListener("click", loadOrders);
refreshArchiveBtn?.addEventListener("click", loadArchiveOrders);
settingsForm?.addEventListener("submit", saveSettings);

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => setActiveTab(btn.dataset.adminTab));
});

Promise.all([loadSettings(), loadOrders()]).catch(() => {
  if (ordersEl) {
    ordersEl.innerHTML = `<article class="order-card"><h3>Ошибка загрузки</h3><p>Проверьте сервер и подключение к PostgreSQL.</p></article>`;
  }
});
