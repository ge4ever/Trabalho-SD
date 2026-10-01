/**
 * Banco SD - Interface Mobile First
 * Inspirado nas cores e tipografia de vitorette.com
 */

// Estado global da aplicação
const state = {
  activeKey: "alice@pix.local",
  accounts: {
    "alice@pix.local": { titular: "Alice Silva", saldo: 1250.75 },
    "bob@pix.local": { titular: "Bob Santos", saldo: 340.20 },
  },
  saldoVisible: true,
  saldoAtual: 0.0,
  titularAtual: "Carregando...",
  history: [],
};

// Formatação monetária BRL
function formatCurrency(value) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

// Inicialização
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initVisibility();
  initAccount();
  setupEventListeners();
  loadBalance();
});

// ==========================================================================
// Tema Claro / Escuro (Inspirado em vitorette.com)
// ==========================================================================

function initTheme() {
  const savedTheme = localStorage.getItem("theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

  if (savedTheme === "dark" || (!savedTheme && prefersDark)) {
    document.documentElement.classList.add("dark");
    updateThemeIcon(true);
  } else {
    document.documentElement.classList.remove("dark");
    updateThemeIcon(false);
  }
}

function toggleTheme() {
  const isDark = document.documentElement.classList.toggle("dark");
  localStorage.setItem("theme", isDark ? "dark" : "light");
  updateThemeIcon(isDark);
}

function updateThemeIcon(isDark) {
  const sunIcon = document.getElementById("theme-icon-sun");
  const moonIcon = document.getElementById("theme-icon-moon");
  if (sunIcon && moonIcon) {
    sunIcon.style.display = isDark ? "block" : "none";
    moonIcon.style.display = isDark ? "none" : "block";
  }
}

// ==========================================================================
// Visibilidade do Saldo (Toggle Olho)
// ==========================================================================

function initVisibility() {
  const savedVisibility = localStorage.getItem("saldo_visible");
  state.saldoVisible = savedVisibility !== "false";
  updateVisibilityUI();
}

function toggleSaldoVisibility() {
  state.saldoVisible = !state.saldoVisible;
  localStorage.setItem("saldo_visible", state.saldoVisible);
  updateVisibilityUI();
}

function updateVisibilityUI() {
  const balanceDisplay = document.getElementById("balance-display");
  const eyeOpenIcon = document.getElementById("eye-open-icon");
  const eyeClosedIcon = document.getElementById("eye-closed-icon");

  if (state.saldoVisible) {
    balanceDisplay.textContent = formatCurrency(state.saldoAtual);
    balanceDisplay.classList.remove("balance-hidden");
    if (eyeOpenIcon) eyeOpenIcon.style.display = "block";
    if (eyeClosedIcon) eyeClosedIcon.style.display = "none";
  } else {
    balanceDisplay.textContent = "••••••••";
    balanceDisplay.classList.add("balance-hidden");
    if (eyeOpenIcon) eyeOpenIcon.style.display = "none";
    if (eyeClosedIcon) eyeClosedIcon.style.display = "block";
  }
}

// ==========================================================================
// Gestão de Conta Ativa
// ==========================================================================

function initAccount() {
  const accountSelect = document.getElementById("account-select");
  if (accountSelect) {
    accountSelect.value = state.activeKey;
    updateUserBadge(state.activeKey);
  }
}

function switchAccount(key) {
  state.activeKey = key;
  updateUserBadge(key);
  loadBalance();
}

function updateUserBadge(key) {
  const nameEl = document.getElementById("user-current-name");
  const avatarEl = document.getElementById("user-avatar");
  const pillKeyEl = document.getElementById("active-key-display");

  const account = state.accounts[key] || { titular: key.split("@")[0] };
  if (nameEl) nameEl.textContent = account.titular;
  if (avatarEl) avatarEl.textContent = account.titular.charAt(0).toUpperCase();
  if (pillKeyEl) pillKeyEl.textContent = key;
}

// ==========================================================================
// Consulta de Saldo via REST
// ==========================================================================

async function loadBalance() {
  const refreshBtn = document.getElementById("refresh-balance-btn");
  if (refreshBtn) refreshBtn.classList.add("spinning");

  try {
    const res = await fetch(`/pix/saldo/${encodeURIComponent(state.activeKey)}`);
    const data = await res.json();

    if (res.ok && data.sucesso) {
      state.saldoAtual = parseFloat(data.saldo || 0);
      state.titularAtual = data.titular;
      const nameEl = document.getElementById("user-current-name");
      if (nameEl) nameEl.textContent = data.titular;
    } else {
      console.warn("Conta não localizada ou saldo indisponível:", data);
      state.saldoAtual = 0.0;
    }
  } catch (err) {
    console.error("Erro ao carregar saldo:", err);
  } finally {
    updateVisibilityUI();
    if (refreshBtn) {
      setTimeout(() => refreshBtn.classList.remove("spinning"), 400);
    }
  }
}

// ==========================================================================
// Envio e Verificação de Pix via REST
// ==========================================================================

async function handleSendPix(e) {
  e.preventDefault();

  const recipientInput = document.getElementById("pix-destinatario");
  const amountInput = document.getElementById("pix-valor");
  const submitBtn = document.getElementById("btn-submit-pix");

  const recipient = (recipientInput?.value || "").trim();
  const rawAmount = amountInput?.value.replace(",", ".") || "";
  const amount = parseFloat(rawAmount);

  if (!recipient) {
    alert("Por favor, informe a chave Pix do destinatário.");
    recipientInput?.focus();
    return;
  }

  if (isNaN(amount) || amount <= 0) {
    alert("Por favor, informe um valor válido maior que zero.");
    amountInput?.focus();
    return;
  }

  // Ativa loading no botão
  submitBtn.disabled = true;
  submitBtn.classList.add("loading");

  try {
    const response = await fetch("/pix/verificar", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        chave_pix: state.activeKey,
        valor: amount,
      }),
    });

    const data = await response.json();
    showReceiptModal(data, recipient, amount);

    // Se autorizado, recarrega o saldo atualizado e adiciona ao histórico
    if (data.sucesso) {
      amountInput.value = "";
      loadBalance();
    }

    addHistoryItem(data.sucesso, recipient, amount, data.mensagem);

  } catch (error) {
    console.error("Erro na requisição Pix:", error);
    showReceiptModal(
      {
        sucesso: false,
        titular: state.titularAtual,
        saldo: state.saldoAtual,
        valor: amount,
        mensagem: "Erro ao comunicar com o servidor Pix. Verifique a conexão.",
      },
      recipient,
      amount
    );
  } finally {
    submitBtn.disabled = false;
    submitBtn.classList.remove("loading");
  }
}

// ==========================================================================
// Comprovante / Modal de Feedback
// ==========================================================================

function showReceiptModal(data, recipient, amount) {
  const modal = document.getElementById("receipt-modal");
  const iconCircle = document.getElementById("receipt-icon-circle");
  const statusTitle = document.getElementById("receipt-status-title");
  const statusMsg = document.getElementById("receipt-status-msg");

  const rValor = document.getElementById("receipt-valor");
  const rDest = document.getElementById("receipt-destinatario");
  const rOrigem = document.getElementById("receipt-origem");
  const rSaldo = document.getElementById("receipt-saldo");
  const rData = document.getElementById("receipt-data");
  const rMensagem = document.getElementById("receipt-mensagem");

  if (data.sucesso) {
    iconCircle.className = "receipt-icon-circle success";
    iconCircle.innerHTML = `
      <svg viewBox="0 0 24 24">
        <path d="M20 6L9 17l-5-5"/>
      </svg>
    `;
    statusTitle.textContent = "Pix Autorizado!";
    statusMsg.textContent = "A transação foi validada com sucesso pelo sistema.";
  } else {
    iconCircle.className = "receipt-icon-circle error";
    iconCircle.innerHTML = `
      <svg viewBox="0 0 24 24">
        <path d="M18 6L6 18M6 6l12 12"/>
      </svg>
    `;
    statusTitle.textContent = "Pix Não Autorizado";
    statusMsg.textContent = data.mensagem || "Não foi possível concluir a transação.";
  }

  rValor.textContent = formatCurrency(amount);
  rDest.textContent = recipient;
  rOrigem.textContent = `${data.titular || state.titularAtual} (${state.activeKey})`;
  rSaldo.textContent = formatCurrency(data.saldo);
  rData.textContent = new Date().toLocaleString("pt-BR");
  rMensagem.textContent = data.mensagem || "-";

  modal.classList.add("show");
}

function closeReceiptModal() {
  const modal = document.getElementById("receipt-modal");
  if (modal) modal.classList.remove("show");
}

// ==========================================================================
// Histórico de Sessão
// ==========================================================================

function addHistoryItem(sucesso, recipient, amount, mensagem) {
  state.history.unshift({
    sucesso,
    recipient,
    amount,
    mensagem,
    date: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
  });

  renderHistory();
}

function renderHistory() {
  const listEl = document.getElementById("history-list");
  if (!listEl) return;

  if (state.history.length === 0) {
    listEl.innerHTML = `<div class="history-empty">Nenhuma transação realizada nesta sessão.</div>`;
    return;
  }

  listEl.innerHTML = state.history
    .map(
      (item) => `
    <div class="history-item">
      <div class="history-meta">
        <span class="history-dest">${item.recipient}</span>
        <span class="history-date">${item.date} • ${item.mensagem}</span>
      </div>
      <div class="history-amount-col">
        <span class="history-val">${formatCurrency(item.amount)}</span>
        <span class="status-badge ${item.sucesso ? "success" : "error"}">
          ${item.sucesso ? "Aprovado" : "Rejeitado"}
        </span>
      </div>
    </div>
  `
    )
    .join("");
}

// ==========================================================================
// Event Listeners e Atalhos
// ==========================================================================

function setupEventListeners() {
  // Tema
  document.getElementById("theme-toggle-btn")?.addEventListener("click", toggleTheme);

  // Visibilidade de Saldo
  document.getElementById("toggle-visibility-btn")?.addEventListener("click", toggleSaldoVisibility);
  document.getElementById("refresh-balance-btn")?.addEventListener("click", () => loadBalance());

  // Troca de conta
  document.getElementById("account-select")?.addEventListener("change", (e) => {
    switchAccount(e.target.value);
  });

  // Formulário Pix
  document.getElementById("pix-form")?.addEventListener("submit", handleSendPix);

  // Fechar Modal
  document.getElementById("btn-close-receipt")?.addEventListener("click", closeReceiptModal);
  document.getElementById("receipt-modal")?.addEventListener("click", (e) => {
    if (e.target.id === "receipt-modal") closeReceiptModal();
  });

  // Pílulas de Chaves Sugeridas
  document.querySelectorAll(".chip-recipient").forEach((chip) => {
    chip.addEventListener("click", () => {
      const destInput = document.getElementById("pix-destinatario");
      if (destInput) {
        destInput.value = chip.dataset.key;
        destInput.focus();
      }
    });
  });

  // Pílulas de Valores Rápidos
  document.querySelectorAll(".chip-amount").forEach((chip) => {
    chip.addEventListener("click", () => {
      const amountInput = document.getElementById("pix-valor");
      if (amountInput) {
        const added = parseFloat(chip.dataset.amount || 0);
        const current = parseFloat(amountInput.value.replace(",", ".") || 0);
        amountInput.value = (current + added).toFixed(2).replace(".", ",");
        amountInput.focus();
      }
    });
  });

  // Ações Rápidas
  document.getElementById("action-pix")?.addEventListener("click", () => {
    document.getElementById("pix-destinatario")?.focus();
  });

  document.getElementById("action-refresh")?.addEventListener("click", () => {
    loadBalance();
  });
}
