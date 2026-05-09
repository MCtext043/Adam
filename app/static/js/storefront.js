const productsEl = document.querySelector("#products");
const cartItemsEl = document.querySelector("#cartItems");
const cartTotalEl = document.querySelector("#cartTotal");
const clearCartBtn = document.querySelector("#clearCart");
const orderForm = document.querySelector("#orderForm");
const orderMessage = document.querySelector("#orderMessage");
const menuSearch = document.querySelector("#menuSearch");
const categoryFiltersEl = document.querySelector("#categoryFilters");
const resetFiltersBtn = document.querySelector("#resetFilters");
const filterSummary = document.querySelector("#filterSummary");

let products = [];
let cart = JSON.parse(localStorage.getItem("adamCart") || "{}");
let activeCategory = "all";
let searchQuery = "";

const formatPrice = (value) =>
  new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value);

function saveCart() {
  localStorage.setItem("adamCart", JSON.stringify(cart));
}

function getCartEntries() {
  return Object.entries(cart)
    .map(([productId, quantity]) => {
      const product = products.find((item) => item.id === Number(productId));
      return product ? { product, quantity } : null;
    })
    .filter(Boolean);
}

function getFilteredProducts() {
  const query = searchQuery.trim().toLowerCase();

  return products.filter((product) => {
    const matchesCategory = activeCategory === "all" || product.category === activeCategory;
    const matchesSearch =
      !query ||
      product.name.toLowerCase().includes(query) ||
      product.description.toLowerCase().includes(query) ||
      product.category.toLowerCase().includes(query);

    return matchesCategory && matchesSearch;
  });
}

function renderCategoryFilters() {
  const categories = ["all", ...new Set(products.map((product) => product.category))];
  categoryFiltersEl.innerHTML = categories
    .map((category) => {
      const label = category === "all" ? "Все" : category;
      const isActive = category === activeCategory;
      return `<button class="filter-chip ${isActive ? "active" : ""}" type="button" data-category="${category}">${label}</button>`;
    })
    .join("");
}

function renderProducts() {
  const filteredProducts = getFilteredProducts();

  productsEl.innerHTML = filteredProducts.length
    ? filteredProducts
    .map(
      (product) => `
        <article class="product-card">
          <img src="${product.image_url}" alt="${product.name}">
          <div class="product-content">
            <span class="product-category">${product.category}</span>
            <h3>${product.name}</h3>
            <p>${product.description}</p>
            <div class="product-footer">
              <span class="price">${formatPrice(product.price)}</span>
              <button class="button button-dark" type="button" data-add="${product.id}">В корзину</button>
            </div>
          </div>
        </article>
      `,
    )
    .join("")
    : `<p class="cart-empty">По этим фильтрам ничего не найдено. Попробуйте другой запрос или категорию.</p>`;

  filterSummary.textContent = `Найдено: ${filteredProducts.length} из ${products.length}`;
}

function renderCart() {
  const entries = getCartEntries();
  const total = entries.reduce((sum, entry) => sum + entry.product.price * entry.quantity, 0);

  cartItemsEl.innerHTML = entries.length
    ? entries
        .map(
          ({ product, quantity }) => `
            <div class="cart-item">
              <div>
                <strong>${product.name}</strong><br>
                <span>${formatPrice(product.price)} за шт.</span>
              </div>
              <div class="quantity-controls">
                <button type="button" data-decrease="${product.id}" aria-label="Уменьшить">-</button>
                <strong>${quantity}</strong>
                <button type="button" data-increase="${product.id}" aria-label="Увеличить">+</button>
              </div>
            </div>
          `,
        )
        .join("")
    : `<p class="cart-empty">Корзина пока пустая. Добавьте блюда из меню.</p>`;

  cartTotalEl.textContent = formatPrice(total);
  saveCart();
}

function addToCart(productId) {
  cart[productId] = (cart[productId] || 0) + 1;
  renderCart();
}

function decreaseCartItem(productId) {
  if (!cart[productId]) return;
  cart[productId] -= 1;
  if (cart[productId] <= 0) delete cart[productId];
  renderCart();
}

productsEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-add]");
  if (!button) return;
  addToCart(button.dataset.add);
});

cartItemsEl.addEventListener("click", (event) => {
  const increaseButton = event.target.closest("[data-increase]");
  const decreaseButton = event.target.closest("[data-decrease]");

  if (increaseButton) addToCart(increaseButton.dataset.increase);
  if (decreaseButton) decreaseCartItem(decreaseButton.dataset.decrease);
});

clearCartBtn.addEventListener("click", () => {
  cart = {};
  renderCart();
});

menuSearch.addEventListener("input", (event) => {
  searchQuery = event.target.value;
  renderProducts();
});

categoryFiltersEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (!button) return;

  activeCategory = button.dataset.category;
  renderCategoryFilters();
  renderProducts();
});

resetFiltersBtn.addEventListener("click", () => {
  activeCategory = "all";
  searchQuery = "";
  menuSearch.value = "";
  renderCategoryFilters();
  renderProducts();
});

orderForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const entries = getCartEntries();
  if (!entries.length) {
    setMessage("Добавьте хотя бы одно блюдо в корзину.", "error");
    return;
  }

  const formData = new FormData(orderForm);
  const payload = {
    customer_name: formData.get("customer_name"),
    phone: formData.get("phone"),
    address: formData.get("address"),
    comment: formData.get("comment") || "",
    items: entries.map(({ product, quantity }) => ({ product_id: product.id, quantity })),
  };

  try {
    const response = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Не удалось оформить заказ");
    }

    const order = await response.json();
    cart = {};
    orderForm.reset();
    renderCart();
    setMessage(`Заказ #${order.id} принят. Итого: ${formatPrice(order.total)}.`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
});

function setMessage(text, type) {
  orderMessage.textContent = text;
  orderMessage.className = `form-message ${type}`;
}

async function loadProducts() {
  const response = await fetch("/api/products");
  products = await response.json();
  renderCategoryFilters();
  renderProducts();
  renderCart();
}

loadProducts().catch(() => {
  productsEl.innerHTML = `<p class="cart-empty">Не удалось загрузить меню. Проверьте подключение к PostgreSQL и запуск сервера.</p>`;
});
