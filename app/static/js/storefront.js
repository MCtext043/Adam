const productsEl = document.querySelector("#products");
const cartItemsEl = document.querySelector("#cartItems");
const cartTotalEl = document.querySelector("#cartTotal");
const checkoutCartItemsEl = document.querySelector("#checkoutCartItems");
const checkoutCartTotalEl = document.querySelector("#checkoutCartTotal");
const checkoutSubtotalEl = document.querySelector("#checkoutSubtotal");
const checkoutDiscountEl = document.querySelector("#checkoutDiscount");
const discountLineEl = document.querySelector("#discountLine");
const checkoutFoodTotalEl = document.querySelector("#checkoutFoodTotal");
const checkoutDeliveryEl = document.querySelector("#checkoutDelivery");
const deliveryAddressEl = document.querySelector("#deliveryAddress");
const deliveryHintEl = document.querySelector("#deliveryHint");
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
const minOrderHintEl = document.getElementById("minOrderHint");
const checkoutMinOrderHintEl = document.getElementById("checkoutMinOrderHint");
const checkoutPaymentHintEl = document.getElementById("checkoutPaymentHint");
const orderSubmitBtn = document.getElementById("orderSubmitBtn");
const loyaltySpendPanel = document.getElementById("loyaltySpendPanel");
const useLoyaltyPoints = document.getElementById("useLoyaltyPoints");
const loyaltyAmountWrap = document.getElementById("loyaltyAmountWrap");
const loyaltyPointsInput = document.getElementById("loyaltyPointsInput");
const loyaltyAvailableHint = document.getElementById("loyaltyAvailableHint");

const page = document.body.dataset.page;

let products = [];
let cart = JSON.parse(localStorage.getItem("adamCart") || "{}");
let activeCategory = "all";
let searchQuery = "";
let storeSettings = {
  min_order_amount: 500,
  free_delivery_threshold: 3000,
  delivery_price_per_km: 45,
  payment_enabled: false,
};
let authUser = null;
let loyaltySpendAmount = 0;
let deliveryEstimate = { fee: 0, distance_km: 0, free: false, ok: false, loading: false, error: "" };
let deliveryEstimateTimer = null;

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

function getCartSubtotal() {
  return getCartEntries().reduce((sum, entry) => sum + entry.product.price * entry.quantity, 0);
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

function minOrderHintText() {
  const min = Math.round(storeSettings.min_order_amount || 0);
  return min > 0 ? `Минимальная сумма заказа для доставки — ${min} ₽` : "";
}

function updateMinOrderHints(subtotal) {
  const text = minOrderHintText();
  const belowMin = subtotal > 0 && subtotal < storeSettings.min_order_amount;

  [minOrderHintEl, checkoutMinOrderHintEl].forEach((el) => {
    if (!el) return;
    if (!text) {
      el.textContent = "";
      el.hidden = true;
      return;
    }
    el.hidden = false;
    el.textContent = belowMin ? `${text}. Сейчас в корзине ${Math.round(subtotal)} ₽.` : text;
    el.classList.toggle("min-order-hint-warn", belowMin);
  });
}

function maxLoyaltySpend(subtotal) {
  if (!authUser) return 0;
  return Math.min(authUser.loyalty_points || 0, Math.floor(subtotal));
}

function getLoyaltySpendForCheckout(subtotal) {
  if (!useLoyaltyPoints?.checked || !authUser) return 0;
  const max = maxLoyaltySpend(subtotal);
  let value = Number(loyaltyPointsInput?.value || 0);
  if (!Number.isFinite(value) || value < 0) value = 0;
  return Math.min(max, Math.floor(value));
}

function syncLoyaltyInput(subtotal) {
  const max = maxLoyaltySpend(subtotal);
  loyaltySpendAmount = getLoyaltySpendForCheckout(subtotal);

  if (loyaltyPointsInput) {
    loyaltyPointsInput.max = String(max);
    if (Number(loyaltyPointsInput.value) > max) loyaltyPointsInput.value = String(max);
  }
  if (loyaltyAvailableHint && authUser) {
    loyaltyAvailableHint.textContent = `Доступно: ${authUser.loyalty_points} · можно списать до ${max}`;
  }
}

function getDeliveryFee(subtotal) {
  if (subtotal >= storeSettings.free_delivery_threshold) return 0;
  if (!deliveryEstimate.ok) return 0;
  return deliveryEstimate.fee || 0;
}

function updateDeliveryHint(subtotal) {
  if (!deliveryHintEl) return;
  const threshold = Math.round(storeSettings.free_delivery_threshold || 3000);
  const perKm = Math.round(storeSettings.delivery_price_per_km || 45);
  if (subtotal >= storeSettings.free_delivery_threshold) {
    deliveryHintEl.textContent = `Доставка бесплатно (заказ от ${threshold} ₽).`;
    return;
  }
  if (deliveryEstimate.loading) {
    deliveryHintEl.textContent = "Считаем расстояние до адреса…";
    return;
  }
  if (deliveryEstimate.error) {
    deliveryHintEl.textContent = deliveryEstimate.error;
    deliveryHintEl.classList.add("field-hint-warn");
    return;
  }
  deliveryHintEl.classList.remove("field-hint-warn");
  if (deliveryEstimate.ok && deliveryEstimate.distance_km > 0) {
    deliveryHintEl.textContent = `~${deliveryEstimate.distance_km} км · ${perKm} ₽/км. От ${threshold} ₽ доставка бесплатно.`;
    return;
  }
  deliveryHintEl.textContent = `Доставка ${perKm} ₽/км (примерный расчёт по адресу). От ${threshold} ₽ — бесплатно.`;
}

async function requestDeliveryEstimate() {
  if (page !== "checkout") return;
  const subtotal = getCartSubtotal();
  if (subtotal >= storeSettings.free_delivery_threshold) {
    deliveryEstimate = { fee: 0, distance_km: 0, free: true, ok: true, loading: false, error: "" };
    updateCheckoutTotals(subtotal);
    return;
  }
  const address = deliveryAddressEl?.value.trim() || "";
  if (address.length < 8) {
    deliveryEstimate = { fee: 0, distance_km: 0, free: false, ok: false, loading: false, error: "" };
    updateCheckoutTotals(subtotal);
    return;
  }
  deliveryEstimate.loading = true;
  deliveryEstimate.error = "";
  updateCheckoutTotals(subtotal);
  try {
    const response = await fetch("/api/delivery/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address, subtotal }),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = data.detail || "Не удалось рассчитать доставку";
      deliveryEstimate = {
        fee: 0,
        distance_km: 0,
        free: false,
        ok: false,
        loading: false,
        error: typeof detail === "string" ? detail : "Укажите более точный адрес",
      };
    } else {
      deliveryEstimate = {
        fee: data.delivery_fee,
        distance_km: data.distance_km,
        free: data.free_delivery,
        ok: true,
        loading: false,
        error: "",
      };
    }
  } catch {
    deliveryEstimate = { fee: 0, distance_km: 0, free: false, ok: false, loading: false, error: "" };
  }
  updateCheckoutTotals(getCartSubtotal());
}

function updateCheckoutTotals(subtotal) {
  loyaltySpendAmount = getLoyaltySpendForCheckout(subtotal);
  const discount = loyaltySpendAmount;
  const deliveryFee = getDeliveryFee(subtotal);
  const foodTotal = Math.max(0, subtotal - discount);
  const finalTotal = foodTotal + deliveryFee;

  if (checkoutSubtotalEl) checkoutSubtotalEl.textContent = formatPrice(subtotal);
  if (checkoutDiscountEl) checkoutDiscountEl.textContent = `−${formatPrice(discount)}`;
  if (discountLineEl) discountLineEl.hidden = discount <= 0;
  if (checkoutFoodTotalEl) checkoutFoodTotalEl.textContent = formatPrice(foodTotal);
  if (checkoutDeliveryEl) {
    if (subtotal >= storeSettings.free_delivery_threshold) {
      checkoutDeliveryEl.textContent = "бесплатно";
    } else if (deliveryEstimate.loading) {
      checkoutDeliveryEl.textContent = "…";
    } else if (!deliveryEstimate.ok) {
      checkoutDeliveryEl.textContent = "—";
    } else {
      checkoutDeliveryEl.textContent = deliveryFee > 0 ? formatPrice(deliveryFee) : "бесплатно";
    }
  }
  if (checkoutCartTotalEl) checkoutCartTotalEl.textContent = formatPrice(finalTotal);

  syncLoyaltyInput(subtotal);
  updateMinOrderHints(subtotal);
  updateDeliveryHint(subtotal);
  return finalTotal;
}

function renderCartList(targetItemsEl, targetTotalEl) {
  const entries = getCartEntries();
  const subtotal = getCartSubtotal();
  const displayTotal = page === "checkout" ? updateCheckoutTotals(subtotal) : subtotal;

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

    targetTotalEl.textContent = formatPrice(displayTotal);
  } else if (page === "checkout") {
    updateCheckoutTotals(subtotal);
    if (subtotal < storeSettings.free_delivery_threshold && deliveryAddressEl?.value.trim().length >= 8) {
      clearTimeout(deliveryEstimateTimer);
      deliveryEstimateTimer = setTimeout(() => requestDeliveryEstimate(), 400);
    }
  } else {
    updateMinOrderHints(subtotal);
  }

  saveCart();
  updateCheckoutChrome(subtotal, entries.length);

  if (page === "menu" || page === "home") renderProducts();

  const belowMin = entries.length > 0 && subtotal < storeSettings.min_order_amount;
  if (goCheckout) {
    const disabled = entries.length === 0 || belowMin;
    goCheckout.classList.toggle("is-disabled", disabled);
    goCheckout.setAttribute("aria-disabled", disabled ? "true" : "false");
  }
  if (checkoutHint) {
    if (!entries.length) checkoutHint.textContent = "Добавьте блюда в меню.";
    else if (belowMin) checkoutHint.textContent = minOrderHintText();
    else checkoutHint.textContent = "";
  }
}

function updateCheckoutChrome(total, count) {
  if (!bonusPreview) return;
  const discount = page === "checkout" ? loyaltySpendAmount : 0;
  const earnBase = Math.max(0, total - discount);
  const previewPoints = count ? Math.max(1, Math.floor(earnBase * 0.03)) : 0;

  if (authUser && count) {
    bonusPreview.textContent = `+${previewPoints} бонусов с этого заказа`;
  } else if (count) {
    bonusPreview.textContent = "Войдите — будем копить бонусы";
  } else {
    bonusPreview.textContent = "";
  }
}

function renderCart() {
  renderCartList(cartItemsEl, cartTotalEl);
}

function renderCheckoutCart() {
  renderCartList(checkoutCartItemsEl, checkoutCartTotalEl);
}

function refreshProductViews() {
  if (page === "menu" || page === "home") renderProducts();
  renderCart();
  renderCheckoutCart();
}

function addToCart(productId, toastName) {
  const product = products.find((item) => item.id === Number(productId));
  if (!product) return;
  cart[productId] = (cart[productId] || 0) + 1;
  refreshProductViews();

  if (toastName && typeof window.showAdamToast === "function") {
    window.showAdamToast(`«${toastName}» добавлено в корзину`);
  }
}

function decreaseCartItem(productId) {
  if (!cart[productId]) return;
  cart[productId] -= 1;
  if (cart[productId] <= 0) delete cart[productId];
  refreshProductViews();
}

function bindProductGridClicks(root) {
  root?.addEventListener("click", (event) => {
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
}

bindProductGridClicks(productsEl);

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
  refreshProductViews();
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

useLoyaltyPoints?.addEventListener("change", () => {
  const subtotal = getCartSubtotal();
  if (loyaltyAmountWrap) loyaltyAmountWrap.hidden = !useLoyaltyPoints.checked;
  if (useLoyaltyPoints.checked && loyaltyPointsInput) {
    const max = maxLoyaltySpend(subtotal);
    loyaltyPointsInput.value = String(max > 0 ? max : 0);
  }
  renderCheckoutCart();
});

loyaltyPointsInput?.addEventListener("input", () => {
  renderCheckoutCart();
});

deliveryAddressEl?.addEventListener("input", () => {
  clearTimeout(deliveryEstimateTimer);
  deliveryEstimateTimer = setTimeout(() => requestDeliveryEstimate(), 600);
});

orderForm?.addEventListener("submit", async (event) => {
  event.preventDefault();

  const entries = getCartEntries();
  if (!entries.length) {
    setMessage("Добавьте хотя бы одно блюдо в корзину.", "error");
    return;
  }

  const subtotal = getCartSubtotal();
  if (subtotal < storeSettings.min_order_amount) {
    setMessage(minOrderHintText() + `. Сейчас в корзине ${Math.round(subtotal)} ₽.`, "error");
    return;
  }

  const formData = new FormData(orderForm);
  const address = String(formData.get("address") || "").trim();
  if (subtotal < storeSettings.free_delivery_threshold) {
    if (address.length < 8) {
      setMessage("Укажите полный адрес доставки.", "error");
      return;
    }
    if (!deliveryEstimate.ok) {
      await requestDeliveryEstimate();
    }
    if (!deliveryEstimate.ok) {
      setMessage(deliveryEstimate.error || "Не удалось рассчитать доставку. Проверьте адрес.", "error");
      return;
    }
  }

  const emailRaw = String(formData.get("email") || "").trim();
  const payload = {
    customer_name: formData.get("customer_name"),
    phone: formData.get("phone"),
    email: emailRaw || null,
    address: formData.get("address"),
    comment: formData.get("comment") || "",
    items: entries.map(({ product, quantity }) => ({ product_id: product.id, quantity })),
    loyalty_points_to_spend: getLoyaltySpendForCheckout(subtotal),
  };

  try {
    const response = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(await readApiError(response));
    }

    const order = await response.json();

    if (order.payment_required && order.payment_url) {
      window.location.href = order.payment_url;
      return;
    }

    cart = {};
    if (useLoyaltyPoints) useLoyaltyPoints.checked = false;
    if (loyaltyAmountWrap) loyaltyAmountWrap.hidden = true;
    orderForm.reset();
    refreshProductViews();

    let bonusText = "";
    if (order.loyalty_points_earned) {
      bonusText = ` Начислено баллов: ${order.loyalty_points_earned}.`;
    }
    if (order.loyalty_points_spent) {
      bonusText = ` Списано бонусов: ${order.loyalty_points_spent}.${bonusText}`;
    }
    setMessage(
      `Заказ #${order.id} принят. За заказ: ${formatPrice(order.food_total)}, за доставку: ${formatPrice(order.delivery_fee)}, итого: ${formatPrice(order.total)}.${bonusText}`,
      "success",
    );

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

async function readApiError(response) {
  const text = await response.text();
  try {
    const data = JSON.parse(text);
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || String(item)).join(". ");
    }
  } catch {
    /* not JSON */
  }
  if (text && text.length < 200) return text;
  return "Не удалось оформить заказ. Попробуйте ещё раз или позвоните в кафе.";
}

async function hydrateCheckoutAccount() {
  if (!accountBanner) return;
  try {
    const response = await fetch("/api/auth/me", { credentials: "same-origin" });
    const data = await response.json();
    authUser = data.authenticated ? data : null;

    if (data.authenticated) {
      accountBanner.hidden = false;
      accountBanner.innerHTML = `Вы вошли. <a href="/account">Баллы: ${data.loyalty_points}</a>.`;
      if (orderEmail && !orderEmail.value) orderEmail.value = data.email;

      if (loyaltySpendPanel) {
        loyaltySpendPanel.hidden = false;
        const subtotal = getCartSubtotal();
        syncLoyaltyInput(subtotal);
      }
    } else {
      accountBanner.hidden = true;
      accountBanner.textContent = "";
      if (loyaltySpendPanel) loyaltySpendPanel.hidden = true;
    }

    const subtotal = getCartSubtotal();
    updateCheckoutChrome(subtotal, getCartEntries().length);
    if (page === "checkout") renderCheckoutCart();
  } catch {
    authUser = null;
    accountBanner.hidden = true;
    if (loyaltySpendPanel) loyaltySpendPanel.hidden = true;
  }
}

async function loadStoreSettings() {
  try {
    const response = await fetch("/api/store/settings");
    if (response.ok) {
      storeSettings = await response.json();
    }
  } catch {
    /* defaults */
  }
  if (storeSettings.payment_enabled) {
    checkoutPaymentHintEl?.removeAttribute("hidden");
    if (orderSubmitBtn) orderSubmitBtn.textContent = "Оформить и оплатить";
  }
}

async function loadProducts() {
  const response = await fetch("/api/products");
  products = await response.json();
  renderCategoryFilters();
  renderProducts();
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
    await loadStoreSettings();
    await loadProducts();
    if (page === "checkout") await hydrateCheckoutAccount();

    if (productsEl && products.length === 0) {
      productsEl.innerHTML = `<p class="cart-empty">Меню пустое. Проверьте базу данных.</p>`;
    }
  } catch {
    if (productsEl) {
      productsEl.innerHTML = `<p class="cart-empty">Не удалось загрузить меню. Проверьте подключение к PostgreSQL и запуск сервера.</p>`;
    }
  }
}

boot();
