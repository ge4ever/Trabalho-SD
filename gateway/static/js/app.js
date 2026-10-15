/**
 * Banco SD - Interface Mobile First
 * Inspirado nas cores e tipografia de vitorette.com
 * Integração completa com API Gateway REST e Segurança JWT
 */

// Estado global da aplicação
const state = {
  activeKey: "alice@pix.local",
  token: null,
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
document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  initVisibility();
  initAccount();
  setupEventListeners();
  
  // Realiza login inicial para obter JWT e carregar dados
  await authenticate(state.activeKey);
  await loadBalance();
  await loadHistory();
});

// ==========================================================================
// Segurança JWT e Requisições Autenticadas
// ==========================================================================

async function authenticate(key) {
  const badge = document.getElementById("jwt-badge");
  if (badge) {
    badge.textContent = "Autenticando JWT...";
    badge.style.color = "#d97706";
  }

  try {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chave_pix: key,
        senha: "123456",
      }),
    });

    const data = await res.json();
    if (res.ok && data.token) {
      state.token = data.token;
      if (badge) {
        badge.textContent = "JWT Autenticado 🔒";
        badge.style.color = "#16a34a";
      }
      return true;
    } else {
      console.error("Falha ao obter JWT:", data);
      if (badge) {
        badge.textContent = "JWT Não Autorizado ⚠️";
        badge.style.color = "#dc2626";
      }
      return false;
    }
  } catch (err) {
    console.error("Erro na comunicação com o Gateway para login:", err);
    if (badge) {
      badge.textContent = "Erro JWT Conexão ❌";
      badge.style.color = "#dc2626";
    }
    return false;
  }
}

async function authFetch(url, options = {}) {
  options.headers = options.headers || {};
  if (!state.token) {
    await authenticate(state.activeKey);
  }
  if (state.token) {
    options.headers["Authorization"] = `Bearer ${state.token}`;
  }

  let res = await fetch(url, options);

  // Se o token expirou ou é inválido, tenta renovar 1 vez
  if (res.status === 401) {
    console.warn("[AUTH] Token expirado ou rejeitado na borda (401). Renovando token JWT...");
    const ok = await authenticate(state.activeKey);
    if (ok) {
      options.headers["Authorization"] = `Bearer ${state.token}`;
      res = await fetch(url, options);
    }
  }

  return res;
}

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

async function switchAccount(key) {
  state.activeKey = key;
  updateUserBadge(key);
  await authenticate(key);
  await loadBalance();
  await loadHistory();
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
// Consulta de Saldo via REST (com JWT)
// ==========================================================================

async function loadBalance() {
  const refreshBtn = document.getElementById("refresh-balance-btn");
  if (refreshBtn) refreshBtn.classList.add("spinning");

  try {
    const res = await authFetch(`/pix/saldo/${encodeURIComponent(state.activeKey)}`);
    const data = await res.json();

    if (res.ok && data.sucesso) {
      state.saldoAtual = parseFloat(data.saldo || 0);
      state.titularAtual = data.titular;
      const nameEl = document.getElementById("user-current-name");
      if (nameEl) nameEl.textContent = data.titular;
    } else {
      console.warn("Conta não localizada ou erro ao obter saldo:", data);
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
// Transferência Real de Pix via REST (com JWT e Persistência no Banco)
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

  submitBtn.disabled = true;
  submitBtn.classList.add("loading");

  try {
    // Chamada oficial ao endpoint /pix/transferir com validação de payload no Gateway
    const response = await authFetch("/pix/transferir", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        chave_origem: state.activeKey,
        chave_destino: recipient,
        valor: amount,
        descricao: "Transferência Pix Web",
      }),
    });

    const data = await response.json();
    showReceiptModal(data, recipient, amount, response.status);

    // Se criada com sucesso (HTTP 201 Created), limpa valor e atualiza saldo e histórico
    if (response.status === 201 && data.sucesso) {
      amountInput.value = "";
      await loadBalance();
      await loadHistory();
    }

  } catch (error) {
    console.error("Erro na requisição Pix:", error);
    showReceiptModal(
      {
        sucesso: false,
        titular: state.titularAtual,
        saldo: state.saldoAtual,
        valor: amount,
        mensagem: "Erro ao comunicar com o servidor Gateway. Verifique a conexão.",
      },
      recipient,
      amount,
      500
    );
  } finally {
    submitBtn.disabled = false;
    submitBtn.classList.remove("loading");
  }
}

// ==========================================================================
// Comprovante / Modal de Feedback com Status Semântico
// ==========================================================================

function showReceiptModal(data, recipient, amount, statusCode = 200) {
  const modal = document.getElementById("receipt-modal");
  const iconCircle = document.getElementById("receipt-icon-circle");
  const statusTitle = document.getElementById("receipt-status-title");
  const statusMsg = document.getElementById("receipt-status-msg");

  const rId = document.getElementById("receipt-id");
  const rStatusCode = document.getElementById("receipt-status-code");
  const rValor = document.getElementById("receipt-valor");
  const rDest = document.getElementById("receipt-destinatario");
  const rOrigem = document.getElementById("receipt-origem");
  const rSaldo = document.getElementById("receipt-saldo");
  const rData = document.getElementById("receipt-data");
  const rMensagem = document.getElementById("receipt-mensagem");

  if (statusCode === 201 || data.sucesso) {
    iconCircle.className = "receipt-icon-circle success";
    iconCircle.innerHTML = `
      <svg viewBox="0 0 24 24">
        <path d="M20 6L9 17l-5-5"/>
      </svg>
    `;
    statusTitle.textContent = "Pix Realizado com Sucesso!";
    statusMsg.textContent = "A transferência foi liquidada e persistida no banco de dados.";
  } else {
    iconCircle.className = "receipt-icon-circle error";
    iconCircle.innerHTML = `
      <svg viewBox="0 0 24 24">
        <path d="M18 6L6 18M6 6l12 12"/>
      </svg>
    `;
    statusTitle.textContent = "Transferência Rejeitada";
    statusMsg.textContent = data.mensagem || "Não foi possível concluir a transação.";
  }

  if (rId) rId.textContent = data.transacao_id || "-";
  if (rStatusCode) {
    rStatusCode.textContent = `${statusCode} ${statusCode === 201 ? "Created" : statusCode === 400 ? "Bad Request" : statusCode === 401 ? "Unauthorized" : "Error"}`;
  }
  rValor.textContent = formatCurrency(amount);
  rDest.textContent = recipient;
  rOrigem.textContent = `${data.titular_origem || state.titularAtual} (${state.activeKey})`;
  rSaldo.textContent = formatCurrency(data.saldo !== undefined ? data.saldo : state.saldoAtual);
  rData.textContent = data.data_hora || new Date().toLocaleString("pt-BR");
  rMensagem.textContent = data.mensagem || (data.erros ? data.erros.join(", ") : "-");

  modal.classList.add("show");
}

function closeReceiptModal() {
  const modal = document.getElementById("receipt-modal");
  if (modal) modal.classList.remove("show");
}

// ==========================================================================
// Histórico Real Persistido no Banco de Dados
// ==========================================================================

async function loadHistory() {
  try {
    const res = await authFetch(`/pix/historico/${encodeURIComponent(state.activeKey)}`);
    if (res.ok) {
      const data = await res.json();
      renderHistory(data.transacoes || []);
    }
  } catch (err) {
    console.error("Erro ao carregar histórico do banco:", err);
  }
}

function renderHistory(items) {
  const listEl = document.getElementById("history-list");
  if (!listEl) return;

  if (!items || items.length === 0) {
    listEl.innerHTML = `<div class="history-empty">Nenhuma transação registrada no banco de dados para esta conta.</div>`;
    return;
  }

  listEl.innerHTML = items
    .map((item) => {
      const isSent = item.chave_origem === state.activeKey;
      return `
        <div class="history-item">
          <div class="history-meta">
            <span class="history-dest">
              ${isSent ? "Enviado para: " + item.chave_destino : "Recebido de: " + item.chave_origem}
            </span>
            <span class="history-date">
              ID: ${item.id} &bull; ${item.data_hora} &bull; ${item.mensagem || item.status}
            </span>
          </div>
          <div class="history-amount-col">
            <span class="history-val" style="color: ${isSent ? 'var(--color-text)' : '#16a34a'};">
              ${isSent ? "- " : "+ "}${formatCurrency(item.valor)}
            </span>
            <span class="status-badge ${item.status === 'CONCLUIDO' ? 'success' : 'error'}">
              ${item.status}
            </span>
          </div>
        </div>
      `;
    })
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
  document.getElementById("refresh-balance-btn")?.addEventListener("click", async () => {
    await loadBalance();
    await loadHistory();
  });

  // Troca de conta
  document.getElementById("account-select")?.addEventListener("change", async (e) => {
    await switchAccount(e.target.value);
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

  document.getElementById("action-refresh")?.addEventListener("click", async () => {
    await loadBalance();
    await loadHistory();
  });
}
