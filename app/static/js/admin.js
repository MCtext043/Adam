const ordersEl = document.querySelector("#orders");
const refreshBtn = document.querySelector("#refreshOrders");
const settingsForm = document.querySelector("#adminSettingsForm");
const minOrderAmountInput = document.querySelector("#minOrderAmount");
const settingsMessage = document.querySelector("#settingsMessage");

const statusLabels = {
  new: "Новый",
  cooking: "Готовится",
  delivering: "В доставке",
  done: "Готово",
  cancelled: "Отменен",
};

const formatPrice = (value) =>
  new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value);

function statusOptions(currentStatus) {
  return window.ORDER_STATUSES.map(
    (status) => `<option value="${status}" ${status === currentStatus ? "selected" : ""}>${statusLabels[status]}</option>`,
  ).join("");
}

function renderOrders(orders) {
  if (!orders.length) {
    ordersEl.innerHTML = `<article class="order-card"><h3>Заказов пока нет</h3><p>Новые заказы появятся здесь сразу после оформления на сайте.</p></article>`;
    return;
  }

  ordersEl.innerHTML = orders
    .map((order) => {
      const bonusLine =
        order.loyalty_points_spent > 0
          ? `<p><strong>Бонусы:</strong> списано ${order.loyalty_points_spent}</p>`
          : "";
      return `
        <article class="order-card">
          <div class="order-meta">
            <h3>Заказ #${order.id}</h3>
            <span class="status-pill">${statusLabels[order.status] || order.status}</span>
          </div>
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
          <div class="cart-total">
            <span>Итого</span>
            <strong>${formatPrice(order.total)}</strong>
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
  ordersEl.innerHTML = `<article class="order-card"><p>Загрузка заказов...</p></article>`;
  const response = await fetch("/api/admin/orders", { credentials: "same-origin" });
  if (response.status === 401) {
    window.location.href = "/admin/login";
    return;
  }
  const orders = await response.json();
  renderOrders(orders);
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
  const response = await fetch("/api/admin/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ min_order_amount: value }),
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
  }

  await loadOrders();
}

ordersEl.addEventListener("change", (event) => {
  const select = event.target.closest("[data-order-status]");
  if (!select) return;
  updateStatus(select.dataset.orderStatus, select.value);
});

refreshBtn.addEventListener("click", loadOrders);
settingsForm?.addEventListener("submit", saveSettings);

Promise.all([loadSettings(), loadOrders()]).catch(() => {
  ordersEl.innerHTML = `<article class="order-card"><h3>Ошибка загрузки</h3><p>Проверьте сервер и подключение к PostgreSQL.</p></article>`;
});
