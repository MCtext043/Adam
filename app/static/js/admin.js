const ordersEl = document.querySelector("#orders");
const refreshBtn = document.querySelector("#refreshOrders");

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
    .map(
      (order) => `
        <article class="order-card">
          <div class="order-meta">
            <h3>Заказ #${order.id}</h3>
            <span class="status-pill">${statusLabels[order.status] || order.status}</span>
          </div>
          <p><strong>${order.customer_name}</strong> · ${order.phone}</p>
          <p class="order-address"><strong>Адрес:</strong> ${order.address}</p>
          ${order.comment ? `<p><strong>Комментарий:</strong> ${order.comment}</p>` : ""}
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
      `,
    )
    .join("");
}

async function loadOrders() {
  ordersEl.innerHTML = `<article class="order-card"><p>Загрузка заказов...</p></article>`;
  const response = await fetch("/api/admin/orders");
  const orders = await response.json();
  renderOrders(orders);
}

async function updateStatus(orderId, status) {
  const response = await fetch(`/api/admin/orders/${orderId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });

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

loadOrders().catch(() => {
  ordersEl.innerHTML = `<article class="order-card"><h3>Ошибка загрузки</h3><p>Проверьте сервер и подключение к PostgreSQL.</p></article>`;
});
