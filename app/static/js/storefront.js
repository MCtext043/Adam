const productsEl = document.querySelector("#products");
const homeFeaturedProductsEl = document.querySelector("#homeFeaturedProducts");
const cartItemsEl = document.querySelector("#cartItems");
const cartTotalEl = document.querySelector("#cartTotal");
const checkoutCartItemsEl = document.querySelector("#checkoutCartItems");
const checkoutCartTotalEl = document.querySelector("#checkoutCartTotal");
const clearCartBtn = document.querySelector("#clearCart");
const orderForm = document.querySelector("#orderForm");
const orderMessage = document.querySelector("#orderMessage");
const menuSearch = document.querySelector("#menuSearch");
const categoryFiltersEl = document.querySelector("#categoryFilters");
const resetFiltersBtn = document.querySelector("#resetFilters");
const checkoutHint = document.querySelector("#checkoutHint");
const goCheckout = document.getElementById("goCheckout");
const accountBanner = document.getElementById("accountBanner");
const bonusPreview = document.getElementById("bonusPreview");
const orderEmail = document.getElementById("orderEmail");

const page = document.body.dataset.page;

let products = [];
let cart = JSON.parse(localStorage.getItem("adamCart") || "{}");
let activeCategory = "all";
let searchQuery = "";

const formatPrice = (value) =>
  new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value);

function saveCart() {
  localStorage.setItem("adamCart", JSON.stringify(cart));
  if (typeof window.updateNavCartCount === "function") window.updateNavCartCount();
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
  if (!categoryFiltersEl) return;
  const categories = ["all", ...new Set(products.map((product) => product.category))];
  categoryFiltersEl.innerHTML = categories
    .map((category) => {
      const label = category === "all" ? "Все" : category;
      const isActive = category === activeCategory;
      return `<button class="filter-chip ${isActive ? "active" : ""}" type="button" data-category="${category}">${label}</button>`;
    })
    .join("");
}

function productFooterHtml(product) {
  const qty = cart[product.id] || 0;
  const priceHtml = `<span class="price">${formatPrice(product.price)}</span>`;

  if (qty > 0) {
    return `
      <div class="product-footer product-footer-split">
        ${priceHtml}
        <div class="product-inline-cart">
          <div class="quantity-controls quantity-controls-card" data-card-controls="${product.id}">
            <button type="button" data-decrease="${product.id}" aria-label="Уменьшить">−</button>
            <strong>${qty}</strong>
            <button type="button" data-increase="${product.id}" aria-label="Увеличить">+</button>
          </div>
        </div>
      </div>
    `;
  }

  return `
    <div class="product-footer">
      ${priceHtml}
      <button class="button button-dark" type="button" data-add="${product.id}">В корзину</button>
    </div>
  `;
}

function renderProducts() {
  if (!productsEl) return;
  const filteredProducts = getFilteredProducts();

  productsEl.innerHTML = filteredProducts.length
    ? filteredProducts.map((product) => productCardHtml(product)).join("")
    : `<p class="cart-empty">По этим фильтрам ничего не найдено. Попробуйте другой запрос или категорию.</p>`;
}

function productCardHtml(product) {
  return `
    <article class="product-card">
      <img src="${product.image_url}" alt="${product.name}" loading="lazy" width="900" height="600">
      <div class="product-content">
        <span class="product-category">${product.category}</span>
        <h3>${product.name}</h3>
        <p>${product.description}</p>
        ${productFooterHtml(product)}
      </div>
    </article>
  `;
}

function renderHomeFeaturedProducts() {
  if (!homeFeaturedProductsEl) return;

  const featured = products.slice(0, 4);
  homeFeaturedProductsEl.innerHTML = featured.length
    ? featured.map((product) => productCardHtml(product)).join("")
    : `<p class="cart-empty">Меню скоро появится.</p>`;
}

function renderCartList(targetItemsEl, targetTotalEl) {
  const entries = getCartEntries();
  const total = entries.reduce((sum, entry) => sum + entry.product.price * entry.quantity, 0);

  if (targetItemsEl && targetTotalEl) {
    targetItemsEl.innerHTML = entries.length
      ? entries
          .map(
            ({ product, quantity }) => `
            <div class="cart-item">
              <div>
                <strong>${product.name}</strong><br>
                <span>${formatPrice(product.price)} за шт.</span>
              </div>
              <div class="quantity-controls">
                <button type="button" data-decrease="${product.id}" aria-label="Уменьшить">−</button>
                <strong>${quantity}</strong>
                <button type="button" data-increase="${product.id}" aria-label="Увеличить">+</button>
              </div>
            </div>
          `,
          )
          .join("")
      : `<p class="cart-empty">Корзина пока пустая. Добавьте блюда в меню.</p>`;

    targetTotalEl.textContent = formatPrice(total);
  }

  saveCart();
  updateCheckoutChrome(total, entries.length);

  if (page === "menu") renderProducts();
  renderHomeFeaturedProducts();
  if (goCheckout) {
    goCheckout.classList.toggle("is-disabled", entries.length === 0);
    goCheckout.setAttribute("aria-disabled", entries.length === 0 ? "true" : "false");
  }
  if (checkoutHint) {
    checkoutHint.textContent = entries.length ? "" : "Добавьте блюда в меню.";
  }
}

function updateCheckoutChrome(total, count) {
  if (!bonusPreview) return;
  const previewPoints = count ? Math.max(1, Math.floor(total * 0.03)) : 0;
  fetch("/api/auth/me", { credentials: "same-origin" })
    .then((r) => r.json())
    .then((data) => {
      if (data.authenticated && count) {
        bonusPreview.textContent = `+${previewPoints} бонусов с этого заказа`;
      } else if (count) {
        bonusPreview.textContent = "Войдите — будем копить бонусы";
      } else {
        bonusPreview.textContent = "";
      }
    })
    .catch(() => {
      bonusPreview.textContent = "";
    });
}

function renderCart() {
  renderCartList(cartItemsEl, cartTotalEl);
}

function renderCheckoutCart() {
  renderCartList(checkoutCartItemsEl, checkoutCartTotalEl);
}

function addToCart(productId, toastName) {
  const product = products.find((item) => item.id === Number(productId));
  if (!product) return;
  cart[productId] = (cart[productId] || 0) + 1;
  renderCart();
  if (page === "menu") renderProducts();
  renderCheckoutCart();

  if (toastName && typeof window.showAdamToast === "function") {
    window.showAdamToast(`«${toastName}» добавлено в корзину`);
  }
}

function decreaseCartItem(productId) {
  if (!cart[productId]) return;
  cart[productId] -= 1;
  if (cart[productId] <= 0) delete cart[productId];
  renderCart();
  if (page === "menu") renderProducts();
  renderCheckoutCart();
}

productsEl?.addEventListener("click", (event) => {
  const addButton = event.target.closest("[data-add]");
  const increaseButton = event.target.closest("[data-increase]");
  const decreaseButton = event.target.closest("[data-decrease]");
  if (addButton) {
    const product = products.find((item) => item.id === Number(addButton.dataset.add));
    addToCart(addButton.dataset.add, product?.name);
    return;
  }
  if (increaseButton) addToCart(increaseButton.dataset.increase);
  if (decreaseButton) decreaseCartItem(decreaseButton.dataset.decrease);
});

homeFeaturedProductsEl?.addEventListener("click", (event) => {
  const addButton = event.target.closest("[data-add]");
  const increaseButton = event.target.closest("[data-increase]");
  const decreaseButton = event.target.closest("[data-decrease]");
  if (addButton) {
    const product = products.find((item) => item.id === Number(addButton.dataset.add));
    addToCart(addButton.dataset.add, product?.name);
    return;
  }
  if (increaseButton) addToCart(increaseButton.dataset.increase);
  if (decreaseButton) decreaseCartItem(decreaseButton.dataset.decrease);
});

cartItemsEl?.addEventListener("click", (event) => {
  const increaseButton = event.target.closest("[data-increase]");
  const decreaseButton = event.target.closest("[data-decrease]");
  if (increaseButton) addToCart(increaseButton.dataset.increase);
  if (decreaseButton) decreaseCartItem(decreaseButton.dataset.decrease);
});

checkoutCartItemsEl?.addEventListener("click", (event) => {
  const increaseButton = event.target.closest("[data-increase]");
  const decreaseButton = event.target.closest("[data-decrease]");
  if (increaseButton) addToCart(increaseButton.dataset.increase);
  if (decreaseButton) decreaseCartItem(decreaseButton.dataset.decrease);
});

clearCartBtn?.addEventListener("click", () => {
  cart = {};
  renderCart();
  if (page === "menu") renderProducts();
  renderCheckoutCart();
});

menuSearch?.addEventListener("input", (event) => {
  searchQuery = event.target.value;
  renderProducts();
});

categoryFiltersEl?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (!button) return;

  activeCategory = button.dataset.category;
  renderCategoryFilters();
  renderProducts();
});

resetFiltersBtn?.addEventListener("click", () => {
  activeCategory = "all";
  searchQuery = "";
  if (menuSearch) menuSearch.value = "";
  renderCategoryFilters();
  renderProducts();
});

orderForm?.addEventListener("submit", async (event) => {
  event.preventDefault();

  const entries = getCartEntries();
  if (!entries.length) {
    setMessage("Добавьте хотя бы одно блюдо в корзину.", "error");
    return;
  }

  const formData = new FormData(orderForm);
  const emailRaw = String(formData.get("email") || "").trim();
  const payload = {
    customer_name: formData.get("customer_name"),
    phone: formData.get("phone"),
    email: emailRaw || null,
    address: formData.get("address"),
    comment: formData.get("comment") || "",
    items: entries.map(({ product, quantity }) => ({ product_id: product.id, quantity })),
  };

  try {
    const response = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
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
    if (page === "menu") renderProducts();
    renderCheckoutCart();

    let bonusText = "";
    if (order.loyalty_points_earned) {
      bonusText = ` Начислено баллов: ${order.loyalty_points_earned}.`;
    }
    setMessage(`Заказ #${order.id} принят. Итого: ${formatPrice(order.total)}.${bonusText}`, "success");

    await hydrateCheckoutAccount();
  } catch (error) {
    setMessage(error.message, "error");
  }
});

function setMessage(text, type) {
  if (!orderMessage) return;
  orderMessage.textContent = text;
  orderMessage.className = `form-message ${type}`;
}

async function hydrateCheckoutAccount() {
  if (!accountBanner) return;
  try {
    const response = await fetch("/api/auth/me", { credentials: "same-origin" });
    const data = await response.json();
    if (data.authenticated) {
      accountBanner.hidden = false;
      accountBanner.textContent = `Вы вошли. Баллы: ${data.loyalty_points}.`;
      if (orderEmail && !orderEmail.value) orderEmail.value = data.email;
    } else {
      accountBanner.hidden = true;
      accountBanner.textContent = "";
    }
  } catch {
    accountBanner.hidden = true;
  }
}

async function loadProducts() {
  const response = await fetch("/api/products");
  products = await response.json();
  renderCategoryFilters();
  renderProducts();
  renderHomeFeaturedProducts();
  renderCart();
  renderCheckoutCart();
}

goCheckout?.addEventListener("click", (e) => {
  if (goCheckout.classList.contains("is-disabled")) {
    e.preventDefault();
  }
});

async function boot() {
  try {
    await loadProducts();
    if (page === "checkout") await hydrateCheckoutAccount();

    if (productsEl && products.length === 0) {
      productsEl.innerHTML = `<p class="cart-empty">Меню пустое. Проверьте базу данных.</p>`;
    }
  } catch {
    if (productsEl) {
      productsEl.innerHTML = `<p class="cart-empty">Не удалось загрузить меню. Проверьте подключение к PostgreSQL и запуск сервера.</p>`;
    }
    if (homeFeaturedProductsEl) {
      homeFeaturedProductsEl.innerHTML = `<p class="cart-empty">Не удалось загрузить блюда.</p>`;
    }
  }
}

boot();
