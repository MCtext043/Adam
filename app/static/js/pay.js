const orderId = window.PAY_ORDER_ID;
const token = window.PAY_TOKEN || "";
const params = new URLSearchParams(window.location.search);
const payLoading = document.getElementById("payLoading");
const payBlock = document.getElementById("payBlock");
const paySuccess = document.getElementById("paySuccess");
const payError = document.getElementById("payError");
const payQrCode = document.getElementById("payQrCode");
const payMobileBtn = document.getElementById("payMobileBtn");
const payFoodTotalEl = document.getElementById("payFoodTotal");
const payDeliveryTotalEl = document.getElementById("payDeliveryTotal");
const payAmountEl = document.getElementById("payAmount");
let pollTimer = null;

const formatPrice = (value) =>
  new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value);

function showError(text) {
  payError.hidden = false;
  payError.textContent = text;
  payLoading.hidden = true;
}

function showPaid() {
  payLoading.hidden = true;
  payBlock.hidden = true;
  paySuccess.hidden = false;
  if (pollTimer) clearInterval(pollTimer);
}

function isMobile() {
  return window.matchMedia("(max-width: 768px)").matches;
}

function renderQr(qrData) {
  payQrCode.innerHTML = "";
  // eslint-disable-next-line no-undef
  new QRCode(payQrCode, {
    text: qrData,
    width: 300,
    height: 300,
    correctLevel: QRCode.CorrectLevel.M,
  });
  payBlock.hidden = false;
  payLoading.hidden = true;

  if (isMobile() && payMobileBtn) {
    payMobileBtn.hidden = false;
    payMobileBtn.onclick = () => window.open(qrData, "_blank", "noopener");
  }
}

async function pollStatus() {
  const response = await fetch(
    `/api/orders/${orderId}/payment/status?token=${encodeURIComponent(token)}`,
    { credentials: "same-origin" },
  );
  if (!response.ok) return;
  const data = await response.json();
  if (data.status === "paid") showPaid();
}

async function loadOrderInfo() {
  const response = await fetch(
    `/api/orders/${orderId}/payment/info?token=${encodeURIComponent(token)}`,
    { credentials: "same-origin" },
  );
  if (!response.ok) return null;
  return response.json();
}

function renderPaymentBreakdown(info) {
  if (!info) return;
  if (payFoodTotalEl) payFoodTotalEl.textContent = formatPrice(info.food_total ?? 0);
  if (payDeliveryTotalEl) {
    const fee = info.delivery_fee ?? 0;
    payDeliveryTotalEl.textContent = fee > 0 ? formatPrice(fee) : "бесплатно";
  }
  if (payAmountEl) payAmountEl.textContent = formatPrice(info.total ?? 0);
}

async function startPayment() {
  if (!window.ELPLAT_ENABLED) {
    showError("Оплата СБП не настроена. Свяжитесь с кафе.");
    return;
  }
  if (!token) {
    showError("Неверная ссылка на оплату.");
    return;
  }

  const info = await loadOrderInfo();
  if (info?.payment_status === "paid") {
    renderPaymentBreakdown(info);
    showPaid();
    return;
  }
  if (info) renderPaymentBreakdown(info);

  if (params.get("done") === "1") {
    await pollStatus();
    if (!paySuccess.hidden) return;
  }

  try {
    const response = await fetch(
      `/api/orders/${orderId}/payment/qr?token=${encodeURIComponent(token)}`,
      { method: "POST", credentials: "same-origin" },
    );
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Не удалось создать QR");
    }
    if (data.paid) {
      renderPaymentBreakdown(data);
      showPaid();
      return;
    }
    renderPaymentBreakdown(data);
    renderQr(data.qr_data);
    pollTimer = setInterval(pollStatus, 2500);
    pollStatus();
  } catch (error) {
    showError(error.message || "Ошибка оплаты");
  }
}

startPayment();
