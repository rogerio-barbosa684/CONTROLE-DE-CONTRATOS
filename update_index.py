import sys

html_content = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Controle de Contratos - Local</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Segoe UI', sans-serif;
      background: #f0f2f5;
      color: #333;
    }

    header {
      background: #1a3c5e;
      color: white;
      padding: 16px 32px;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    header h1 { font-size: 1.3rem; }

    nav {
      background: #24527a;
      display: flex;
      gap: 4px;
      padding: 8px 32px;
    }
    nav button {
      background: transparent;
      border: none;
      color: #cde;
      padding: 8px 18px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.9rem;
      transition: background 0.2s;
    }
    nav button:hover, nav button.active {
      background: #1a3c5e;
      color: white;
    }

    main {
      max-width: 1600px;
      margin: 32px auto;
      padding: 0 16px;
    }

    .card {
      background: white;
      border-radius: 10px;
      padding: 28px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      margin-bottom: 24px;
    }
    .card h2 {
      font-size: 1.1rem;
      color: #1a3c5e;
      margin-bottom: 20px;
      border-bottom: 2px solid #e8eef4;
      padding-bottom: 10px;
    }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
    }
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .form-group.full { grid-column: 1 / -1; }
    label {
      font-size: 0.82rem;
      font-weight: 600;
      color: #555;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    input, select, textarea {
      padding: 9px 12px;
      border: 1.5px solid #d0d7e3;
      border-radius: 6px;
      font-size: 0.95rem;
      transition: border-color 0.2s;
      background: #fafbfd;
    }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: #24527a;
      background: white;
    }
    textarea { resize: vertical; min-height: 70px; }

    .toggle-row {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 0;
    }
    .toggle {
      position: relative;
      width: 46px;
      height: 24px;
    }
    .toggle input { opacity: 0; width: 0; height: 0; }
    .toggle-slider {
      position: absolute;
      inset: 0;
      background: #ccc;
      border-radius: 24px;
      cursor: pointer;
      transition: background 0.3s;
    }
    .toggle-slider:before {
      content: '';
      position: absolute;
      width: 18px; height: 18px;
      left: 3px; top: 3px;
      background: white;
      border-radius: 50%;
      transition: transform 0.3s;
    }
    .toggle input:checked + .toggle-slider { background: #24527a; }
    .toggle input:checked + .toggle-slider:before { transform: translateX(22px); }
    .toggle-label { font-size: 0.95rem; font-weight: 500; }

    .btn {
      padding: 10px 24px;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.9rem;
      font-weight: 600;
      transition: opacity 0.2s, transform 0.1s;
    }
    .btn:hover { opacity: 0.88; transform: translateY(-1px); }
    .btn-primary { background: #24527a; color: white; }
    .btn-success { background: #2e7d52; color: white; }
    .btn-warning { background: #d4820a; color: white; }
    .btn-danger  { background: #c0392b; color: white; }
    .btn-sm { padding: 5px 12px; font-size: 0.8rem; }
    .btn-row { display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }
    th {
      background: #eef2f7;
      padding: 10px 12px;
      text-align: left;
      font-size: 0.78rem;
      text-transform: uppercase;
      color: #555;
      letter-spacing: 0.04em;
    }
    td {
      padding: 10px 12px;
      border-bottom: 1px solid #f0f2f5;
      vertical-align: middle;
    }
    tr:hover td { background: #f7f9fc; }
    #tb-contratos td { white-space: nowrap; }

    .badge {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
    }
    .badge-ativo    { background: #d4edda; color: #1a5c35; }
    .badge-vencido  { background: #fde8e8; color: #8b1a1a; }
    .badge-pago     { background: #d4edda; color: #1a5c35; }
    .badge-pendente { background: #fff3cd; color: #7d5a00; }
    .badge-atrasado { background: #fde8e8; color: #8b1a1a; }
    .badge-aditivo  { background: #e0e7ff; color: #2d3ab5; }

    .section-hidden { display: none !important; }

    .modal-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.45);
      z-index: 100;
      align-items: center;
      justify-content: center;
    }
    .modal-overlay.open { display: flex; }
    .modal {
      background: white;
      border-radius: 12px;
      padding: 32px;
      width: 90%;
      max-width: 620px;
      max-height: 90vh;
      overflow-y: auto;
      box-shadow: 0 8px 32px rgba(0,0,0,0.18);
    }
    .modal h3 {
      font-size: 1.1rem;
      color: #1a3c5e;
      margin-bottom: 20px;
      border-bottom: 2px solid #e8eef4;
      padding-bottom: 10px;
    }
    .modal-close {
      float: right;
      background: none;
      border: none;
      font-size: 1.4rem;
      cursor: pointer;
      color: #888;
      line-height: 1;
    }

    .info-box {
      background: #eef6ff;
      border-left: 4px solid #24527a;
      padding: 12px 16px;
      border-radius: 0 6px 6px 0;
      font-size: 0.88rem;
      margin-bottom: 16px;
    }

    .summary-cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .summary-card {
      background: white;
      border-radius: 10px;
      padding: 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.07);
      border-top: 4px solid #24527a;
    }
    .summary-card.green { border-top-color: #2e7d52; }
    .summary-card.orange { border-top-color: #d4820a; }
    .summary-card.red { border-top-color: #c0392b; }
    .summary-card .value {
      font-size: 1.6rem;
      font-weight: 700;
      color: #1a3c5e;
    }
    .summary-card .label {
      font-size: 0.78rem;
      color: #888;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-top: 4px;
    }

    .page { display: none; }
    .page.active { display: block; }

    .historico-item {
      border-left: 3px solid #24527a;
      padding: 8px 14px;
      margin-bottom: 8px;
      background: #f7f9fc;
      border-radius: 0 6px 6px 0;
      font-size: 0.88rem;
    }
    .historico-item .hist-date { font-size: 0.78rem; color: #888; }
    
    #app-content { display: none; }
  </style>
</head>
<body>

<!-- LOGIN -->
<div id="login-content" style="max-width:400px; margin: 100px auto;">
  <div class="card" style="text-align:center;">
    <svg width="40" height="40" fill="none" viewBox="0 0 24 24" style="margin-bottom:12px;">
      <rect x="3" y="2" width="13" height="18" rx="2" fill="#7ab3d4"/>
      <rect x="8" y="2" width="13" height="18" rx="2" fill="#1a3c5e" fill-opacity="0.15" stroke="#1a3c5e" stroke-width="1.5"/>
      <rect x="8" y="2" width="13" height="18" rx="2" fill="#a8c8e8"/>
      <line x1="11" y1="8"  x2="18" y2="8"  stroke="#1a3c5e" stroke-width="1.5" stroke-linecap="round"/>
      <line x1="11" y1="11" x2="18" y2="11" stroke="#1a3c5e" stroke-width="1.5" stroke-linecap="round"/>
      <line x1="11" y1="14" x2="15" y2="14" stroke="#1a3c5e" stroke-width="1.5" stroke-linecap="round"/>
    </svg>
    <h2 style="border:none; padding:0;">Acesso Restrito</h2>
    <div id="login-error" style="color:#c0392b; font-weight:bold; font-size:0.9rem; margin-bottom:16px; display:none;">Usuário ou senha incorretos!</div>
    <div class="form-group" style="text-align:left;">
      <label>Usuário</label>
      <input type="text" id="log-user" />
    </div>
    <div class="form-group" style="text-align:left; margin-top:12px;">
      <label>Senha</label>
      <input type="password" id="log-pass" />
    </div>
    <button class="btn btn-primary" style="width:100%; margin-top:20px;" onclick="doLogin()">Entrar no Sistema</button>
    </div>
</div>

<div id="app-content">
<header>
  <svg width="28" height="28" fill="none" viewBox="0 0 24 24">
    <rect x="3" y="2" width="13" height="18" rx="2" fill="#7ab3d4"/>
    <rect x="8" y="2" width="13" height="18" rx="2" fill="white" fill-opacity="0.15" stroke="white" stroke-width="1.5"/>
    <rect x="8" y="2" width="13" height="18" rx="2" fill="#a8c8e8"/>
    <line x1="11" y1="8"  x2="18" y2="8"  stroke="#1a3c5e" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="11" y1="11" x2="18" y2="11" stroke="#1a3c5e" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="11" y1="14" x2="15" y2="14" stroke="#1a3c5e" stroke-width="1.5" stroke-linecap="round"/>
  </svg>
  <h1>Controle de Contratos e Pagamentos</h1>
  <span id="header-user" style="margin-left:auto; color:#cde; font-size:0.85rem;"></span>
  <button style="margin-left:12px; background:transparent; border:none; color:#cde; cursor:pointer; font-weight:bold; font-size:0.9rem;" onclick="doLogout()">Sair</button>
</header>

<nav>
  <button class="active" onclick="showPage('dashboard',this)">Dashboard</button>
  <button onclick="showPage('contratos',this)">Contratos</button>
  <button onclick="showPage('novo-contrato',this)">+ Novo Contrato</button>
  <button onclick="showPage('pagamentos',this)">Pagamentos</button>
  <button id="nav-usuarios" onclick="showPage('usuarios',this)" style="display:none">Usuários</button>
  <button onclick="showPage('configuracao',this)">Configuração</button>
</nav>

<main>

  <!-- DASHBOARD -->
  <div id="page-dashboard" class="page active">
    <div class="summary-cards" id="summary-cards"></div>
    <div class="card">
      <div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;align-items:end">
        <div class="form-group" style="min-width:220px">
          <label>FILTRAR POR FORNECEDOR / CNPJ / CPF</label>
          <input type="text" id="filtro-dash-parte" placeholder="Nome ou CNPJ/CPF" oninput="renderDashboard()"/>
        </div>
        <div class="form-group" style="min-width:160px">
          <label>FILTRAR POR VENCIMENTO (ATE)</label>
          <input type="date" id="filtro-dash-venc" onchange="renderDashboard()"/>
        </div>
      </div>
      <h2>Próximos Vencimentos</h2>
      <div style="overflow-x:auto">
        <table>
          <thead>
            <tr>
              <th>Contrato</th><th>Fornecedor/Cliente</th><th>CNPJ/CPF</th>
              <th>Parcela</th><th>Vencimento</th><th>Valor</th><th>Status</th>
            </tr>
          </thead>
          <tbody id="tb-vencimentos"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- LISTA DE CONTRATOS -->
  <div id="page-contratos" class="page">
    <div class="card">
      <h2>Contratos Cadastrados</h2>
      <div style="overflow-x:auto">
        <table>
          <thead>
            <tr>
              <th>Nº Contrato</th><th>Objeto</th><th>Parte</th>
              <th>Valor</th><th>Vigência</th><th>Anexo</th><th>Status</th><th style="white-space:nowrap">Ações</th>
            </tr>
          </thead>
          <tbody id="tb-contratos"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- NOVO CONTRATO -->
  <div id="page-novo-contrato" class="page">
    <div class="card">
      <h2 id="form-title">Novo Contrato</h2>

      <div class="form-grid">
        <div class="form-group">
          <label>Nº do Contrato *</label>
          <input type="text" id="f-numero" placeholder="Ex: CT-2024-001" oninput="toUpper(this)"/>
        </div>
        <div class="form-group">
          <label>Tipo</label>
          <select id="f-tipo">
            <option>Serviço</option>
            <option>Fornecimento</option>
            <option>Locação</option>
            <option>Obra</option>
            <option>Consultoria</option>
            <option>Outro</option>
          </select>
        </div>
        <div class="form-group full">
          <label>Objeto do Contrato *</label>
          <input type="text" id="f-objeto" placeholder="Descrição resumida do objeto" oninput="toUpper(this)"/>
        </div>
        <div class="form-group">
          <label>Fornecedor / Cliente *</label>
          <input type="text" id="f-parte" placeholder="Nome ou razão social" oninput="toUpper(this)"/>
        </div>
        <div class="form-group">
          <label>CNPJ / CPF</label>
        <input type="text" id="f-doc" placeholder="00.000.000/0001-00"
          oninput="onDocInput(this)" onblur="onDocBlur(this)" maxlength="18"/>
        <small id="f-doc-tipo" style="margin-top:2px;font-size:0.78rem;color:#888;"></small>
      </div>
        <div class="form-group">
          <label>Valor Total (R$) *</label>
          <input type="number" id="f-valor" placeholder="0,00" min="0" step="0.01"/>
        </div>
        <div class="form-group">
          <label>Data de Início *</label>
          <input type="date" id="f-inicio"/>
        </div>
        <div class="form-group">
          <label>Data de Fim *</label>
          <input type="date" id="f-fim"/>
        </div>
        <div class="form-group">
          <label>Responsável Interno</label>
          <input type="text" id="f-responsavel" placeholder="Nome do responsável" oninput="toUpper(this)"/>
        </div>
        <div class="form-group">
          <label>Setor</label>
          <input type="text" id="f-setor" placeholder="Departamento"/>
        </div>
        <div class="form-group full">
          <label>Observações</label>
          <textarea id="f-obs" placeholder="Informações adicionais..."></textarea>
        </div>
        <div class="form-group full">
          <label>Documento do Contrato (PDF/Imagem)</label>
          <input type="file" id="f-arquivo" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" style="background:#fff; padding:6px; cursor:pointer;" onchange="onArquivoChange(this)"/>
        <small id="f-arquivo-info" style="color:#888;margin-top:4px;display:none;">
          Arquivo atual: <span id="f-arquivo-nome"></span>
          <button class="anexo-btn" onclick="removerArquivoContrato()" style="margin-left:8px;">Remover</button>
        </small>
        </div>
      </div>

      <!-- TOGGLE PARCELAS -->
      <div style="margin-top:20px; padding: 16px; background:#f7f9fc; border-radius:8px; border:1.5px solid #e0e7ef;">
        <div class="toggle-row">
          <label class="toggle">
            <input type="checkbox" id="f-tem-parcelas" onchange="toggleParcelas()"/>
            <span class="toggle-slider"></span>
          </label>
          <span class="toggle-label">Este contrato possui pagamentos / parcelas</span>
        </div>

        <div id="secao-parcelas" class="section-hidden">
          <div class="form-grid" style="margin-top:12px;">
            <div class="form-group">
              <label>Forma de Pagamento</label>
              <select id="f-forma-pgto">
                <option value="mensal">Mensal</option>
                <option value="unico">Pagamento Único</option>
                <option value="parcelado">Parcelado (qtd. definida)</option>
                <option value="avulso">Avulso (lançamento manual)</option>
              </select>
            </div>
            <div class="form-group" id="grp-qtd-parcelas">
              <label>Qtd. de Parcelas</label>
              <input type="number" id="f-qtd-parcelas" min="1" placeholder="Ex: 12"/>
            </div>
            <div class="form-group" id="grp-dia-venc">
              <label>Dia de Vencimento</label>
              <input type="number" id="f-dia-venc" min="1" max="31" placeholder="Ex: 10"/>
            </div>
            <div class="form-group" id="grp-valor-parcela">
              <label>Valor da Parcela (R$)</label>
              <input type="number" id="f-valor-parcela" min="0" step="0.01" placeholder="0,00"/>
            </div>
          </div>
        </div>
      </div>

      <div class="btn-row">
        <button class="btn btn-primary" onclick="salvarContrato()">Salvar Contrato</button>
        <button class="btn" style="background:#e8eef4;color:#333;" onclick="limparFormContrato()">Limpar</button>
      </div>
    </div>
  </div>

  <!-- PAGAMENTOS -->
  <div id="page-pagamentos" class="page">
    <div class="card">
      <h2>Pagamentos / Parcelas</h2>
      <div style="display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; align-items:flex-end;">
        <div class="form-group" style="min-width:220px;">
          <label>Filtrar por Contrato</label>
          <select id="filtro-contrato" onchange="renderPagamentos()">
            <option value="">Todos</option>
          </select>
        </div>
        <div class="form-group" style="min-width:160px;">
          <label>Filtrar por Status</label>
          <select id="filtro-status" onchange="renderPagamentos()">
            <option value="">Todos</option>
            <option value="pendente">Pendente</option>
            <option value="pago">Pago</option>
            <option value="atrasado">Atrasado</option>
          </select>
        </div>
      </div>
      <div style="overflow-x:auto">
        <table>
          <thead>
            <tr>
              <th>Contrato</th><th>Descrição</th><th>Vencimento</th>
              <th>Valor</th><th>Pagamento</th><th>Anexo</th><th>Status</th><th>Ações</th>
            </tr>
          </thead>
          <tbody id="tb-pagamentos"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- USUARIOS -->
  <div id="page-usuarios" class="page">
    <div class="card">
      <h2>Gerenciar Usuários</h2>
      <div style="margin-bottom:16px;">
        <button class="btn btn-primary" onclick="abrirModalUsuario()">+ Novo Usuário</button>
      </div>
      <div style="overflow-x:auto">
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Usuário</th><th>Nome</th><th>Perfil</th><th>Ativo</th><th>Criado em</th><th>Ações</th>
            </tr>
          </thead>
          <tbody id="tb-usuarios"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- CONFIGURACAO -->
  <div id="page-configuracao" class="page">
    <div class="card">
      <h2>Configuração de E-mail</h2>
      <p style="margin-bottom:16px;color:#666;font-size:0.9rem;">Configure o servidor SMTP para envio de lembretes de vencimento.</p>
      <div class="form-grid">
        <div class="form-group">
          <label>Servidor SMTP</label>
          <input type="text" id="cfg-smtp" placeholder="smtp.gmail.com"/>
        </div>
        <div class="form-group">
          <label>Porta SMTP</label>
          <input type="number" id="cfg-porta" placeholder="587"/>
        </div>
        <div class="form-group">
          <label>E-mail Remetente</label>
          <input type="email" id="cfg-email" placeholder="seu@email.com"/>
        </div>
        <div class="form-group">
          <label>Senha do E-mail</label>
          <input type="password" id="cfg-senha" placeholder="senha ou app password"/>
        </div>
        <div class="form-group">
          <label>E-mail Destinatário</label>
          <input type="email" id="cfg-dest" placeholder="destinatario@email.com"/>
        </div>
      </div>
      <div class="btn-row">
        <button class="btn btn-primary" onclick="salvarConfig()">Salvar Configuração</button>
        <button class="btn btn-success" onclick="enviarLembrete()">Enviar Lembrete Agora</button>
      </div>
      <div id="cfg-msg" style="margin-top:12px;display:none;" class="info-box"></div>
    </div>
    <div class="card">
      <h2>Informações do Sistema</h2>
      <p style="color:#666">Versão standalone: dados salvos no navegador (IndexedDB).</p>
      <p style="color:#666">Versão servidor: execute <code>python app.py</code> para usar banco SQLite compartilhado.</p>
    </div>
  </div>

</main>
</div>

<!-- MODAL: NOVO/EDITAR USUARIO -->
<div class="modal-overlay" id="modal-usuario">
  <div class="modal">
    <button class="modal-close" onclick="fecharModal('modal-usuario')">×</button>
    <h3 id="modal-usuario-titulo">Novo Usuário</h3>
    <div class="form-grid">
      <div class="form-group">
        <label>Usuário (login) *</label>
        <input type="text" id="mu-username" placeholder="Ex: joao.silva"/>
      </div>
      <div class="form-group">
        <label>Nome Completo *</label>
        <input type="text" id="mu-nome" placeholder="Nome completo"/>
      </div>
      <div class="form-group">
        <label>Senha *</label>
        <input type="password" id="mu-senha" placeholder="Mínimo 6 caracteres"/>
      </div>
      <div class="form-group">
        <label>Perfil</label>
        <select id="mu-perfil">
          <option value="user">Usuário</option>
          <option value="admin">Administrador</option>
        </select>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="salvarUsuario()">Salvar</button>
      <button class="btn" style="background:#e8eef4;color:#333;" onclick="fecharModal('modal-usuario')">Cancelar</button>
    </div>
  </div>
</div>

<!-- MODAL: DETALHE DO CONTRATO -->
<div class="modal-overlay" id="modal-detalhe">
  <div class="modal">
    <button class="modal-close" onclick="fecharModal('modal-detalhe')">×</button>
    <h3>Detalhe do Contrato</h3>
    <div id="detalhe-content"></div>
    <div class="btn-row" id="detalhe-btns"></div>
  </div>
</div>

<!-- MODAL: NOVO PAGAMENTO / PARCELA AVULSA -->
<div class="modal-overlay" id="modal-pagamento">
  <div class="modal">
    <button class="modal-close" onclick="fecharModal('modal-pagamento')">×</button>
    <h3>Lançar Pagamento</h3>
    <div class="form-grid">
      <div class="form-group full">
        <label>Contrato</label>
        <select id="mp-contrato" onchange="preencherDescricaoPgto()"></select>
      </div>
      <div class="form-group full">
        <label>Descrição</label>
        <input type="text" id="mp-desc" placeholder="Ex: Parcela 1/12, NF 1234..."/>
      </div>
      <div class="form-group">
        <label>Valor (R$)</label>
        <input type="number" id="mp-valor" min="0" step="0.01"/>
      </div>
      <div class="form-group">
        <label>Vencimento</label>
        <input type="date" id="mp-vencimento"/>
      </div>
      <div class="form-group">
        <label>Data de Pagamento</label>
        <input type="date" id="mp-datapgto"/>
      </div>
      <div class="form-group">
        <label>Forma de Pagamento</label>
        <select id="mp-forma">
          <option>Transferência</option>
          <option>Boleto</option>
          <option>PIX</option>
          <option>Cheque</option>
          <option>Outro</option>
        </select>
      </div>
      <div class="form-group full">
        <label>Observação</label>
        <input type="text" id="mp-obs" placeholder=""/>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="salvarPagamento()">Salvar</button>
      <button class="btn" style="background:#e8eef4;color:#333;" onclick="fecharModal('modal-pagamento')">Cancelar</button>
    </div>
  </div>
</div>

<!-- MODAL: REGISTRAR PAGAMENTO (baixar parcela) -->
<div class="modal-overlay" id="modal-baixar">
  <div class="modal">
    <button class="modal-close" onclick="fecharModal('modal-baixar')">×</button>
    <h3>Registrar Pagamento</h3>
    <div id="baixar-info" class="info-box"></div>
    <div class="form-grid">
      <div class="form-group">
        <label>Data do Pagamento *</label>
        <input type="date" id="bx-data"/>
      </div>
      <div class="form-group">
        <label>Valor Pago (R$) *</label>
        <input type="number" id="bx-valor" min="0" step="0.01"/>
      </div>
      <div class="form-group">
        <label>Forma de Pagamento</label>
        <select id="bx-forma">
          <option>Transferência</option>
          <option>Boleto</option>
          <option>PIX</option>
          <option>Cheque</option>
          <option>Outro</option>
        </select>
      </div>
      <div class="form-group full">
        <label>Comprovante (Imagem/PDF)</label>
        <input type="file" id="bx-arquivo" accept=".pdf,.png,.jpg,.jpeg" style="background:#fff; padding:6px;" />
      </div>
      <div class="form-group full">
        <label>Observação</label>
        <input type="text" id="bx-obs"/>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn btn-success" onclick="confirmarBaixa()">Confirmar Pagamento</button>
      <button class="btn" style="background:#e8eef4;color:#333;" onclick="fecharModal('modal-baixar')">Cancelar</button>
    </div>
  </div>
</div>

<!-- MODAL: ADITIVO -->
<div class="modal-overlay" id="modal-aditivo">
  <div class="modal">
    <button class="modal-close" onclick="fecharModal('modal-aditivo')">×</button>
    <h3>Registrar Aditivo</h3>
    <div id="aditivo-info" class="info-box"></div>
    <div class="form-grid">
      <div class="form-group">
        <label>Nº do Aditivo</label>
        <input type="text" id="ad-numero" placeholder="Ex: 1º Aditivo"/>
      </div>
      <div class="form-group">
        <label>Data do Aditivo</label>
        <input type="date" id="ad-data"/>
      </div>
      <div class="form-group full">
        <label>Tipo de Aditivo</label>
        <select id="ad-tipo" onchange="toggleCamposAditivo()">
          <option value="prazo">Prazo</option>
          <option value="valor">Valor</option>
          <option value="prazo_valor">Prazo + Valor</option>
          <option value="outro">Outro</option>
        </select>
      </div>
      <div class="form-group" id="ad-grp-nova-data">
        <label>Nova Data de Fim</label>
        <input type="date" id="ad-nova-data"/>
      </div>
      <div class="form-group" id="ad-grp-novo-valor">
        <label>Acréscimo de Valor (R$)</label>
        <input type="number" id="ad-novo-valor" min="0" step="0.01" placeholder="0,00"/>
      </div>
      <div class="form-group full">
        <label>Objeto / Justificativa *</label>
        <textarea id="ad-objeto" placeholder="Descreva o motivo e o objeto do aditivo..."></textarea>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn btn-warning" onclick="salvarAditivo()">Salvar Aditivo</button>
      <button class="btn" style="background:#e8eef4;color:#333;" onclick="fecharModal('modal-aditivo')">Cancelar</button>
    </div>
  </div>
</div>

<script>
// ===================== LOGIN =====================
function doLogin() {
  const u = document.getElementById('log-user').value;
  const p = document.getElementById('log-pass').value;
  fetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:u, password:p}) })
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        sessionStorage.setItem('logged_in', 'true');
        sessionStorage.setItem('user', JSON.stringify(data.user));
        document.getElementById('login-error').style.display = 'none';
        checkLogin();
      } else {
        document.getElementById('login-error').style.display = 'block';
      }
    })
    .catch(() => {
      document.getElementById('login-error').style.display = 'block';
    });
}
function doLogout() {
  fetch('/api/logout', { method:'POST' }).catch(()=>{});
  sessionStorage.removeItem('logged_in');
  sessionStorage.removeItem('user');
  checkLogin();
}
function checkLogin() {
  if (sessionStorage.getItem('logged_in') === 'true') {
    document.getElementById('login-content').style.display = 'none';
    document.getElementById('app-content').style.display = 'block';
    const user = JSON.parse(sessionStorage.getItem('user') || '{}');
    document.getElementById('header-user').textContent = user.full_name ? (user.full_name + ' (' + user.username + ')') : '';
    if (user.role === 'admin') {
      document.getElementById('nav-usuarios').style.display = '';
    }
    loadDataFromDB();
    // Fetch CSRF token in background
    getCsrfToken();
  } else {
    document.getElementById('login-content').style.display = 'block';
    document.getElementById('app-content').style.display = 'none';
  }
}

// ===================== INDEXED DB =====================
let db;
let cachedContratos = [];
let cachedPagamentos = [];

const requestDB = indexedDB.open("ControleContratos", 1);
requestDB.onupgradeneeded = (e) => {
  db = e.target.result;
  if (!db.objectStoreNames.contains("contratos")) db.createObjectStore("contratos", { keyPath: "id" });
  if (!db.objectStoreNames.contains("pagamentos")) db.createObjectStore("pagamentos", { keyPath: "id" });
};
requestDB.onsuccess = (e) => {
  db = e.target.result;
  checkLogin();
};

function loadDataFromDB() {
  if(!db) return;
  const t = db.transaction(["contratos", "pagamentos"], "readonly");
  t.objectStore("contratos").getAll().onsuccess = e => {
    cachedContratos = e.target.result || [];
    t.objectStore("pagamentos").getAll().onsuccess = e2 => {
      cachedPagamentos = e2.target.result || [];
      showPage('dashboard', document.querySelector('nav button'));
    };
  };
}

function getContratos() { return cachedContratos; }
function saveContratos(arr) {
  cachedContratos = arr;
  const t = db.transaction("contratos", "readwrite");
  t.objectStore("contratos").clear();
  arr.forEach(a => t.objectStore("contratos").put(a));
}
function getPagamentos() { return cachedPagamentos; }
function savePagamentos(arr) {
  cachedPagamentos = arr;
  const t = db.transaction("pagamentos", "readwrite");
  t.objectStore("pagamentos").clear();
  arr.forEach(a => t.objectStore("pagamentos").put(a));
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve({ name: file.name, data: reader.result });
    reader.onerror = error => reject(error);
  });
}
function downloadBase64(base64Data, fileName) {
  const link = document.createElement('a');
  link.href = base64Data;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2); }

let _arquivoContrato = null;

function onArquivoChange(input) {
  if (input.files && input.files[0]) {
    _arquivoContrato = input.files[0];
    const info = document.getElementById('f-arquivo-info');
    const nome = document.getElementById('f-arquivo-nome');
    if (info && nome) {
      info.style.display = 'block';
      nome.innerText = input.files[0].name;
    }
  } else {
    removerArquivoContrato();
  }
}

function removerArquivoContrato() {
  _arquivoContrato = null;
  const el = document.getElementById('f-arquivo');
  if (el) el.value = '';
  const info = document.getElementById('f-arquivo-info');
  const nome = document.getElementById('f-arquivo-nome');
  if (info) info.style.display = 'none';
  if (nome) nome.innerText = '';
}

// ===================== NAVEGAÇÃO =====================
function showPage(id, btn) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + id).classList.add('active');
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  if(btn) btn.classList.add('active');

  if (id === 'dashboard') renderDashboard();
  if (id === 'contratos') renderContratos();
  if (id === 'pagamentos') renderPagamentos();
  if (id === 'novo-contrato') { limparFormContrato(); }
}

// ===================== MODAIS =====================
function abrirModal(id) { document.getElementById(id).classList.add('open'); }
function fecharModal(id) { document.getElementById(id).classList.remove('open'); }

// ===================== FORM CONTRATO =====================
function toggleParcelas() {
  const checked = document.getElementById('f-tem-parcelas').checked;
  document.getElementById('secao-parcelas').classList.toggle('section-hidden', !checked);
  atualizarCamposParcela();
}

function atualizarCamposParcela() {
  const forma = document.getElementById('f-forma-pgto').value;
  document.getElementById('grp-qtd-parcelas').style.display =
    (forma === 'parcelado') ? '' : 'none';
  document.getElementById('grp-dia-venc').style.display =
    (forma === 'mensal' || forma === 'parcelado') ? '' : 'none';
  document.getElementById('grp-valor-parcela').style.display =
    (forma !== 'avulso') ? '' : 'none';
}

document.getElementById('f-forma-pgto').addEventListener('change', atualizarCamposParcela);

function limparFormContrato() {
  ['f-numero','f-objeto','f-parte','f-doc','f-valor','f-inicio',
   'f-fim','f-responsavel','f-setor','f-obs','f-qtd-parcelas',
   'f-dia-venc','f-valor-parcela'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  removerArquivoContrato();
  document.getElementById('f-tipo').value = 'Serviço';
  document.getElementById('f-tem-parcelas').checked = false;
  document.getElementById('secao-parcelas').classList.add('section-hidden');
  document.getElementById('form-title').textContent = 'Novo Contrato';
  window._editandoContrato = null;
  atualizarCamposParcela();
}

async function salvarContrato() {
  const numero = document.getElementById('f-numero').value.trim();
  const objeto = document.getElementById('f-objeto').value.trim();
  const parte  = document.getElementById('f-parte').value.trim();
  const valor  = parseFloat(document.getElementById('f-valor').value) || 0;
  const inicio = document.getElementById('f-inicio').value;
  const fim    = document.getElementById('f-fim').value;
  if (!numero || !objeto || !parte || !inicio || !fim) {
    alert('Preencha os campos obrigatórios: Nº, Objeto, Parte, Início e Fim.'); return;
  }

  const temParcelas = document.getElementById('f-tem-parcelas').checked;
  let pgtoConfig = null;
  if (temParcelas) {
    pgtoConfig = {
      forma: document.getElementById('f-forma-pgto').value,
      qtdParcelas: parseInt(document.getElementById('f-qtd-parcelas').value) || null,
      diaVenc: parseInt(document.getElementById('f-dia-venc').value) || null,
      valorParcela: parseFloat(document.getElementById('f-valor-parcela').value) || null
    };
  }

  const contratos = getContratos();
  
  let arquivoB64 = null;
  if (_arquivoContrato instanceof File) {
    arquivoB64 = await fileToBase64(_arquivoContrato);
  }

  if (window._editandoContrato) {
    const idx = contratos.findIndex(c => c.id === window._editandoContrato);
    if (idx !== -1) {
      if (!arquivoB64) {
        if (_arquivoContrato && !(_arquivoContrato instanceof File)) {
          arquivoB64 = _arquivoContrato;
        } else {
          arquivoB64 = contratos[idx].arquivo;
        }
      }
      contratos[idx] = { ...contratos[idx],
        numero, objeto, parte, valor, inicio, fim,
        tipo: document.getElementById('f-tipo').value,
        doc: document.getElementById('f-doc').value,
        responsavel: document.getElementById('f-responsavel').value,
        setor: document.getElementById('f-setor').value,
        obs: document.getElementById('f-obs').value,
        temParcelas, pgtoConfig, arquivo: arquivoB64,
        aditivos: contratos[idx].aditivos || []
      };

      // Regerar parcelas na edicao: preserva pagas, remove nao pagas, cria novas
      const pagamentos = getPagamentos();
      const paidPayments = pagamentos.filter(p =>
        p.contratoId === window._editandoContrato && p.dataPagamento !== null
      );
      const otherPayments = pagamentos.filter(p =>
        p.contratoId !== window._editandoContrato
      );

      if (temParcelas && pgtoConfig && pgtoConfig.forma !== 'avulso') {
        const valorJaPago = paidPayments.reduce((s, p) => s + (p.valorPago || p.valor || 0), 0);
        const saldoRestante = valor - valorJaPago;
        const qtdNovaTotal = pgtoConfig.qtdParcelas;
        const qtdPagas = paidPayments.length;
        const qtdRestantes = Math.max(0, qtdNovaTotal - qtdPagas);

        const novasParcelas = [];
        if (qtdRestantes > 0 && saldoRestante > 0) {
          const valorParcela = saldoRestante / qtdRestantes;
          let inicioNovas = inicio;
          if (paidPayments.length > 0) {
            const lastDate = paidPayments.reduce((latest, p) =>
              p.vencimento > latest ? p.vencimento : latest, '0000-00-00'
            );
            const d = new Date(lastDate + 'T12:00:00');
            d.setMonth(d.getMonth() + 1);
            inicioNovas = d.toISOString().slice(0, 10);
          }
          for (let i = 0; i < qtdRestantes; i++) {
            const d = new Date(inicioNovas + 'T12:00:00');
            d.setMonth(d.getMonth() + i);
            novasParcelas.push({
              id: uid(), contratoId: window._editandoContrato,
              contratoNum: numero,
              descricao: `Parcela ${qtdPagas + i + 1}/${qtdNovaTotal}`,
              valor: Math.round(valorParcela * 100) / 100,
              vencimento: d.toISOString().slice(0, 10),
              dataPagamento: null, valorPago: null, formaPgto: null,
              obs: '', comprovante: null, status: 'pendente'
            });
          }
        }
        savePagamentos(otherPayments.concat(paidPayments).concat(novasParcelas));
      } else {
        // Sem parcelas: mantem so as pagas
        savePagamentos(otherPayments.concat(paidPayments));
      }
    }
    window._editandoContrato = null;
  } else {
    if (contratos.find(c => c.numero === numero)) {
      alert('Já existe um contrato com esse número.'); return;
    }
    const contrato = {
      id: uid(), numero, objeto, parte, valor, inicio, fim,
      tipo: document.getElementById('f-tipo').value,
      doc: document.getElementById('f-doc').value,
      responsavel: document.getElementById('f-responsavel').value,
      setor: document.getElementById('f-setor').value,
      obs: document.getElementById('f-obs').value,
      temParcelas, pgtoConfig, arquivo: arquivoB64,
      aditivos: [],
      criadoEm: new Date().toISOString()
    };
    contratos.push(contrato);

    if (temParcelas && pgtoConfig && pgtoConfig.forma !== 'avulso') {
      gerarParcelasAuto(contrato);
    }
  }

  saveContratos(contratos);
  alert('Contrato salvo com sucesso!');
  limparFormContrato();
  document.querySelectorAll('nav button')[1].click(); // Goto contratos
}

function gerarParcelasAuto(contrato) {
  const cfg = contrato.pgtoConfig;
  const pagamentos = getPagamentos();
  const inicio = new Date(contrato.inicio + 'T12:00:00');

  if (cfg.forma === 'unico') {
    pagamentos.push({
      id: uid(), contratoId: contrato.id, contratoNum: contrato.numero,
      descricao: 'Pagamento Único',
      valor: cfg.valorParcela || contrato.valor,
      vencimento: contrato.fim,
      dataPagamento: null, formaPgto: null, obs: '',
      status: 'pendente'
    });
  } else if (cfg.forma === 'mensal' || cfg.forma === 'parcelado') {
    const qtd = cfg.qtdParcelas || calcularMeses(contrato.inicio, contrato.fim);
    const dia  = cfg.diaVenc || 10;
    const valorP = cfg.valorParcela || (contrato.valor / qtd);

    for (let i = 0; i < qtd; i++) {
      const d = new Date(inicio.getFullYear(), inicio.getMonth() + i, dia);
      pagamentos.push({
        id: uid(), contratoId: contrato.id, contratoNum: contrato.numero,
        descricao: `Parcela ${i+1}/${qtd}`,
        valor: Math.round(valorP * 100) / 100,
        vencimento: d.toISOString().slice(0,10),
        dataPagamento: null, formaPgto: null, obs: '',
        status: 'pendente'
      });
    }
  }
  savePagamentos(pagamentos);
}

function calcularMeses(inicio, fim) {
  const a = new Date(inicio), b = new Date(fim);
  return Math.max(1, (b.getFullYear()-a.getFullYear())*12 + b.getMonth()-a.getMonth());
}

// ===================== LISTAR CONTRATOS =====================
function renderContratos() {
  const lista = getContratos();
  const tb = document.getElementById('tb-contratos');
  const hoje = new Date(); hoje.setHours(0,0,0,0);

  if (!lista.length) {
    tb.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#aaa;padding:32px">Nenhum contrato cadastrado.</td></tr>';
    return;
  }

  tb.innerHTML = lista.map(c => {
    const fim = new Date(c.fim + 'T12:00:00');
    const ativo = fim >= hoje;
    const status = ativo ? 'ativo' : 'vencido';
    const labelStatus = ativo ? 'Ativo' : 'Vencido';
    const aditivosBadge = c.aditivos?.length
      ? `<span class="badge badge-aditivo">${c.aditivos.length} adit.</span>` : '';
    
    // Anexo UI
    const anexoUI = c.arquivo 
      ? `<button class="btn btn-sm btn-light" style="padding:4px 8px;font-size:0.75rem;" onclick="baixarAnexo('${c.id}')">Ver Anexo</button>` 
      : '—';

    return `<tr>
      <td><strong>${escapeHtml(c.numero)}</strong></td>
      <td>${escapeHtml(c.objeto)}</td>
      <td>${escapeHtml(c.parte)}</td>
      <td>R$ ${fmtMoeda(c.valor)}</td>
      <td>${fmtData(c.inicio)} → ${fmtData(c.fim)}</td>
      <td>${anexoUI}</td>
      <td><span class="badge badge-${status}">${escapeHtml(labelStatus)}</span> ${aditivosBadge}</td>
      <td style="display:flex;gap:4px;flex-wrap:nowrap;white-space:nowrap">
        <button class="btn btn-sm btn-primary" onclick="abrirDetalhe('${c.id}')">Ver</button>
        <button class="btn btn-sm btn-warning" onclick="abrirAditivo('${c.id}')">Adit</button>
        <button class="btn btn-sm btn-danger" onclick="excluirContrato('${c.id}')">Exc</button>
      </td>
    </tr>`;
  }).join('');
}

window.baixarAnexo = function(id) {
  const c = getContratos().find(x => x.id === id);
  if(c && c.arquivo) downloadBase64(c.arquivo.data, c.arquivo.name);
}

// ===================== DETALHE =====================
function abrirDetalhe(id) {
  const c = getContratos().find(x => x.id === id);
  if (!c) return;
  const pagamentos = getPagamentos().filter(p => p.contratoId === id);

  let html = `
    <div class="form-grid" style="margin-bottom:16px;">
      <div><label>Nº Contrato</label><p><strong>${escapeHtml(c.numero)}</strong></p></div>
      <div><label>Tipo</label><p>${escapeHtml(c.tipo)}</p></div>
      <div class="full"><label>Objeto</label><p>${escapeHtml(c.objeto)}</p></div>
      <div><label>Parte</label><p>${escapeHtml(c.parte)}</p></div>
      <div><label>CNPJ/CPF</label><p>${escapeHtml(c.doc)||'—'}</p></div>
      <div><label>Valor Total</label><p>R$ ${fmtMoeda(c.valor)}</p></div>
      <div><label>Vigência</label><p>${fmtData(c.inicio)} → ${fmtData(c.fim)}</p></div>
      <div><label>Responsável</label><p>${escapeHtml(c.responsavel)||'—'}</p></div>
      <div><label>Setor</label><p>${escapeHtml(c.setor)||'—'}</p></div>
    </div>`;

  if (c.obs) html += `<div class="info-box">${escapeHtml(c.obs)}</div>`;
  if (c.arquivo) {
    html += `<div class="info-box">Documento do Contrato: <button onclick="baixarAnexo('${c.id}')" style="background:transparent;border:none;color:#1a3c5e;cursor:pointer;font-weight:bold;">${escapeHtml(c.arquivo.name)}</button></div>`;
  }

  if (c.aditivos?.length) {
    html += `<h4 style="margin:16px 0 8px;color:#1a3c5e;">Histórico de Aditivos</h4>`;
    html += c.aditivos.map(a => `
      <div class="historico-item">
        <strong>${escapeHtml(a.numero)}</strong> — ${escapeHtml(a.tipo)} — ${fmtData(a.data)}
        <div>${escapeHtml(a.objeto)}</div>
        ${a.novaData ? `<div>Nova data fim: <strong>${fmtData(a.novaData)}</strong></div>` : ''}
        ${a.novoValor ? `<div>Acréscimo: <strong>R$ ${fmtMoeda(a.novoValor)}</strong></div>` : ''}
      </div>`).join('');
  }

  if (pagamentos.length) {
    html += `<h4 style="margin:16px 0 8px;color:#1a3c5e;">Pagamentos</h4>`;
    html += `<table><thead><tr><th>Descrição</th><th>Vencimento</th><th>Valor</th><th>Comprovante</th><th>Status</th></tr></thead><tbody>`;
    html += pagamentos.map(p => {
      const st = calcStatusPgto(p);
      const comp = p.comprovante ? `<button class="anexo-btn" onclick="baixarComprovante('${p.id}')">Ver</button>` : '<span style="color:#aaa">-</span>';
      return `<tr><td>${escapeHtml(p.descricao)}</td><td>${fmtData(p.vencimento)}</td><td>R$ ${fmtMoeda(p.valor)}</td><td>${comp}</td><td><span class="badge badge-${st}">${escapeHtml(st)}</span></td></tr>`;
    }).join('');
    html += `</tbody></table>`;
  }

  document.getElementById('detalhe-content').innerHTML = html;

  const btns = document.getElementById('detalhe-btns');
  btns.innerHTML = `<button class="btn btn-primary" onclick="editarContrato('${id}'); fecharModal('modal-detalhe')">Editar</button>`;
  if (c.temParcelas) {
    btns.innerHTML += `<button class="btn btn-success" onclick="abrirLancarPgto('${id}')">+ Pgto</button>`;
  }

  abrirModal('modal-detalhe');
}

function editarContrato(id) {
  const c = getContratos().find(x => x.id === id);
  if (!c) return;
  window._editandoContrato = id;
  document.getElementById('f-numero').value = c.numero;
  document.getElementById('f-objeto').value = c.objeto;
  document.getElementById('f-parte').value  = c.parte;
  document.getElementById('f-doc').value    = c.doc || '';
  document.getElementById('f-valor').value  = c.valor;
  document.getElementById('f-inicio').value = c.inicio;
  document.getElementById('f-fim').value    = c.fim;
  document.getElementById('f-tipo').value   = c.tipo;
  document.getElementById('f-responsavel').value = c.responsavel || '';
  document.getElementById('f-setor').value  = c.setor || '';
  document.getElementById('f-obs').value    = c.obs || '';
  document.getElementById('f-tem-parcelas').checked = c.temParcelas;
  document.getElementById('f-arquivo').value = ''; // file input cannot be pre-filled
  if (c.arquivo) {
    _arquivoContrato = c.arquivo;
    const info = document.getElementById('f-arquivo-info');
    const nome = document.getElementById('f-arquivo-nome');
    if (info && nome) {
      info.style.display = 'block';
      nome.innerText = c.arquivo.name || 'Arquivo anexado';
    }
  } else {
    removerArquivoContrato();
  }
  document.getElementById('form-title').textContent = 'Editar Contrato';
  toggleParcelas();
  if (c.pgtoConfig) {
    document.getElementById('f-forma-pgto').value = c.pgtoConfig.forma || 'mensal';
    document.getElementById('f-qtd-parcelas').value = c.pgtoConfig.qtdParcelas || '';
    document.getElementById('f-dia-venc').value = c.pgtoConfig.diaVenc || '';
    document.getElementById('f-valor-parcela').value = c.pgtoConfig.valorParcela || '';
    atualizarCamposParcela();
  }
  showPage('novo-contrato', document.querySelectorAll('nav button')[2]);
}

function excluirContrato(id) {
  if (!confirm('Excluir este contrato e todos os seus pagamentos?')) return;
  saveContratos(getContratos().filter(c => c.id !== id));
  savePagamentos(getPagamentos().filter(p => p.contratoId !== id));
  renderContratos();
  renderDashboard();
}

// ===================== ADITIVO =====================
let _aditivoContratoId = null;

function abrirAditivo(id) {
  _aditivoContratoId = id;
  const c = getContratos().find(x => x.id === id);
  document.getElementById('aditivo-info').innerHTML =
    `<strong>Contrato:</strong> ${c.numero} — ${c.objeto}<br>
     <strong>Vigência atual:</strong> ${fmtData(c.inicio)} → ${fmtData(c.fim)}<br>
     <strong>Valor atual:</strong> R$ ${fmtMoeda(c.valor)}`;
  document.getElementById('ad-numero').value = `${(c.aditivos?.length||0)+1}º Aditivo`;
  document.getElementById('ad-data').value = new Date().toISOString().slice(0,10);
  document.getElementById('ad-tipo').value = 'prazo';
  document.getElementById('ad-nova-data').value = '';
  document.getElementById('ad-novo-valor').value = '';
  document.getElementById('ad-objeto').value = '';
  toggleCamposAditivo();
  abrirModal('modal-aditivo');
}

window.toggleCamposAditivo = function() {
  const tipo = document.getElementById('ad-tipo').value;
  document.getElementById('ad-grp-nova-data').style.display  = (tipo==='prazo'||tipo==='prazo_valor') ? '' : 'none';
  document.getElementById('ad-grp-novo-valor').style.display = (tipo==='valor'||tipo==='prazo_valor') ? '' : 'none';
}

function salvarAditivo() {
  const objeto = document.getElementById('ad-objeto').value.trim();
  if (!objeto) { alert('Informe o objeto/justificativa.'); return; }

  const contratos = getContratos();
  const idx = contratos.findIndex(c => c.id === _aditivoContratoId);
  if (idx === -1) return;

  const tipo     = document.getElementById('ad-tipo').value;
  const novaData = document.getElementById('ad-nova-data').value;
  const novoValor= parseFloat(document.getElementById('ad-novo-valor').value) || null;
  const tipoLabel = {prazo:'Prazo',valor:'Valor',prazo_valor:'Prazo + Valor',outro:'Outro'}[tipo];

  const aditivo = {
    id: uid(),
    numero: document.getElementById('ad-numero').value || `${(contratos[idx].aditivos?.length||0)+1}º Aditivo`,
    data:   document.getElementById('ad-data').value,
    tipo:   tipoLabel, objeto, novaData: novaData||null, novoValor,
    criadoEm: new Date().toISOString()
  };

  if (!contratos[idx].aditivos) contratos[idx].aditivos = [];
  contratos[idx].aditivos.push(aditivo);

  if (novaData && (tipo==='prazo'||tipo==='prazo_valor')) contratos[idx].fim = novaData;
  if (novoValor && (tipo==='valor'||tipo==='prazo_valor')) contratos[idx].valor += novoValor;

  saveContratos(contratos);
  fecharModal('modal-aditivo');
  renderContratos();
}

// ===================== PAGAMENTOS =====================
let _baixaId = null;

function calcStatusPgto(p) {
  if (p.dataPagamento) return 'pago';
  const hoje = new Date(); hoje.setHours(0,0,0,0);
  const venc  = new Date(p.vencimento + 'T12:00:00');
  return venc < hoje ? 'atrasado' : 'pendente';
}

function renderPagamentos() {
  const filtroContrato = document.getElementById('filtro-contrato').value;
  const filtroStatus   = document.getElementById('filtro-status').value;
  const contratos = getContratos();

  const sel = document.getElementById('filtro-contrato');
  const cur = sel.value;
  sel.innerHTML = '<option value="">Todos</option>' +
    contratos.map(c => `<option value="${c.id}" ${c.id===cur?'selected':''}>${c.numero} — ${c.parte}</option>`).join('');

  let lista = getPagamentos();
  if (filtroContrato) lista = lista.filter(p => p.contratoId === filtroContrato);

  lista = lista.map(p => ({...p, _status: calcStatusPgto(p)}));
  if (filtroStatus) lista = lista.filter(p => p._status === filtroStatus);

  lista.sort((a,b)=> a.vencimento.localeCompare(b.vencimento));

  const tb = document.getElementById('tb-pagamentos');
  if (!lista.length) {
    tb.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#aaa;padding:32px">Nenhum pagamento.</td></tr>';
    return;
  }
  tb.innerHTML = lista.map(p => {
    const st = p._status;
    const c  = contratos.find(x => x.id === p.contratoId);
    
    const anexoUI = p.comprovante 
      ? `<button class="btn btn-sm btn-light" style="padding:4px 8px;font-size:0.75rem;" onclick="baixarComprovante('${p.id}')">Ver</button>` 
      : '—';
      
    const acoes = st !== 'pago'
      ? `<button class="btn btn-sm btn-success" onclick="abrirBaixa('${p.id}')">Baixar</button>
         <button class="btn btn-sm btn-danger" onclick="excluirPgto('${p.id}')">Exc</button>`
      : `<button class="btn btn-sm btn-danger" onclick="excluirPgto('${p.id}')">Exc</button>`;
      
    return `<tr>
      <td><strong>${escapeHtml(p.contratoNum)}</strong>${c?`<br><small style="color:#888">${escapeHtml(c.parte)}</small>`:''}</td>
      <td>${escapeHtml(p.descricao)}</td>
      <td>${fmtData(p.vencimento)}</td>
      <td>R$ ${fmtMoeda(p.valor)}</td>
      <td>${p.dataPagamento ? fmtData(p.dataPagamento) : '—'}</td>
      <td>${anexoUI}</td>
      <td><span class="badge badge-${st}">${escapeHtml(st)}</span></td>
      <td style="display:flex;gap:4px;">${acoes}</td>
    </tr>`;
  }).join('');
}

window.baixarComprovante = function(id) {
  const p = getPagamentos().find(x => x.id === id);
  if(p && p.comprovante) downloadBase64(p.comprovante.data, p.comprovante.name);
}

function abrirLancarPgto(contratoId) {
  fecharModal('modal-detalhe');
  const contratos = getContratos();
  const sel = document.getElementById('mp-contrato');
  sel.innerHTML = contratos.filter(c=>c.temParcelas)
    .map(c=>`<option value="${c.id}" ${c.id===contratoId?'selected':''}>${escapeHtml(c.numero)} — ${escapeHtml(c.parte)}</option>`).join('');
  document.getElementById('mp-desc').value = '';
  document.getElementById('mp-valor').value = '';
  document.getElementById('mp-vencimento').value = '';
  document.getElementById('mp-datapgto').value = '';
  document.getElementById('mp-obs').value = '';
  abrirModal('modal-pagamento');
}

function salvarPagamento() {
  const contratoId = document.getElementById('mp-contrato').value;
  const desc  = document.getElementById('mp-desc').value.trim();
  const valor = parseFloat(document.getElementById('mp-valor').value) || 0;
  const venc  = document.getElementById('mp-vencimento').value;
  if (!contratoId || !venc) { alert('Informe o contrato e o vencimento.'); return; }

  const c = getContratos().find(x=>x.id===contratoId);
  const pagamentos = getPagamentos();
  const dataPgto = document.getElementById('mp-datapgto').value || null;

  pagamentos.push({
    id: uid(), contratoId, contratoNum: c.numero,
    descricao: desc || 'Pagamento avulso',
    valor, vencimento: venc,
    dataPagamento: dataPgto,
    formaPgto: document.getElementById('mp-forma').value,
    obs: document.getElementById('mp-obs').value,
    status: dataPgto ? 'pago' : 'pendente'
  });
  savePagamentos(pagamentos);
  fecharModal('modal-pagamento');
  renderPagamentos();
}

function abrirBaixa(id) {
  _baixaId = id;
  const p = getPagamentos().find(x=>x.id===id);
  const c = getContratos().find(x=>x.id===p.contratoId);
  document.getElementById('bx-arquivo').value = ''; // clear input
  document.getElementById('baixar-info').innerHTML =
    `<strong>${escapeHtml(c?.numero)}</strong> — ${escapeHtml(p.descricao)}<br>
     Vencimento: ${fmtData(p.vencimento)} | Valor: R$ ${fmtMoeda(p.valor)}`;
  document.getElementById('bx-data').value  = new Date().toISOString().slice(0,10);
  document.getElementById('bx-valor').value = p.valor;
  document.getElementById('bx-obs').value   = '';
  abrirModal('modal-baixar');
}

async function confirmarBaixa() {
  const data  = document.getElementById('bx-data').value;
  const valor = parseFloat(document.getElementById('bx-valor').value);
  if (!data) { alert('Informe a data do pagamento.'); return; }

  const arqInput = document.getElementById('bx-arquivo');
  let comprovanteB64 = null;
  if(arqInput.files.length > 0) {
    comprovanteB64 = await fileToBase64(arqInput.files[0]);
  }

  const pagamentos = getPagamentos();
  const idx = pagamentos.findIndex(p=>p.id===_baixaId);
  if (idx===-1) return;
  pagamentos[idx].dataPagamento = data;
  pagamentos[idx].valorPago     = valor;
  pagamentos[idx].formaPgto     = document.getElementById('bx-forma').value;
  pagamentos[idx].obs           = document.getElementById('bx-obs').value;
  if(comprovanteB64) pagamentos[idx].comprovante = comprovanteB64;

  savePagamentos(pagamentos);
  fecharModal('modal-baixar');
  renderPagamentos();
  renderDashboard();
}

function excluirPgto(id) {
  if (!confirm('Excluir este pagamento?')) return;
  savePagamentos(getPagamentos().filter(p=>p.id!==id));
  renderPagamentos();
  renderDashboard();
}

// ===================== DASHBOARD =====================
function renderDashboard() {
  const contratos  = getContratos();
  const pagamentos = getPagamentos();
  const hoje = new Date(); hoje.setHours(0,0,0,0);

  const ativos   = contratos.filter(c => new Date(c.fim+'T12:00:00') >= hoje).length;
  const vencidos  = contratos.length - ativos;
  const pendentes = pagamentos.filter(p => calcStatusPgto(p)==='pendente').length;
  const atrasados = pagamentos.filter(p => calcStatusPgto(p)==='atrasado').length;
  const totalPend = pagamentos
    .filter(p => calcStatusPgto(p) !== 'pago')
    .reduce((s,p)=>s+p.valor, 0);

  document.getElementById('summary-cards').innerHTML = `
    <div class="summary-card">
      <div class="value">${contratos.length}</div>
      <div class="label">Total de Contratos</div>
    </div>
    <div class="summary-card green">
      <div class="value">${ativos}</div>
      <div class="label">Contratos Ativos</div>
    </div>
    <div class="summary-card red">
      <div class="value">${vencidos}</div>
      <div class="label">Contratos Vencidos</div>
    </div>
    <div class="summary-card orange">
      <div class="value">${pendentes + atrasados}</div>
      <div class="label">Pgtos. Pendentes</div>
    </div>
    <div class="summary-card red">
      <div class="value">${atrasados}</div>
      <div class="label">Pgtos. em Atraso</div>
    </div>
    <div class="summary-card">
      <div class="value" style="font-size:1.4rem">R$ ${fmtMoeda(totalPend)}</div>
      <div class="label">Valor a Pagar</div>
    </div>`;

  const filtroParte = (document.getElementById('filtro-dash-parte').value||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
  const filtroVenc = document.getElementById('filtro-dash-venc').value;

  const prox = pagamentos
    .map(p => ({...p, _status: calcStatusPgto(p)}))
    .filter(p => p._status !== 'pago')
    .filter(p => {
      if (!filtroParte) return true;
      const c = contratos.find(x=>x.id===p.contratoId);
      if (!c) return false;
      const txt = (c.parte+' '+c.doc).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
      return txt.indexOf(filtroParte)!==-1;
    })
    .filter(p => {
      if (!filtroVenc) return true;
      return p.vencimento <= filtroVenc;
    })
    .sort((a,b) => a.vencimento.localeCompare(b.vencimento))
    .slice(0, 10);

  const tb = document.getElementById('tb-vencimentos');
  if (!prox.length) {
    tb.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#aaa;padding:32px">Nenhum pagamento pendente.</td></tr>';
    return;
  }
  const cts = getContratos();
  tb.innerHTML = prox.map(p => {
    const c = cts.find(x=>x.id===p.contratoId);
    return `<tr>
      <td><strong>${escapeHtml(p.contratoNum)}</strong></td>
      <td>${escapeHtml(c?.parte)||'—'}</td>
      <td>${escapeHtml(c?.cnpjCpf)||'—'}</td>
      <td>${escapeHtml(p.descricao)}</td>
      <td>${fmtData(p.vencimento)}</td>
      <td>R$ ${fmtMoeda(p.valor)}</td>
      <td><span class="badge badge-${p._status}">${escapeHtml(p._status)}</span></td>
    </tr>`;
  }).join('');
}

// ===================== HELPERS =====================
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}
function fmtMoeda(v) { return (parseFloat(v)||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}); }
function fmtData(d) { if (!d) return '—'; const [y,m,dia] = d.slice(0,10).split('-'); return `${dia}/${m}/${y}`; }

// ===================== FORMATACAO CPF/CNPJ =====================
function formatarDoc(valor) {
  const nums = valor.replace(/\D/g,'');
  if (nums.length <= 11) {
    return nums.substring(0,11)
      .replace(/(\d{3})(\d)/,'$1.$2')
      .replace(/(\d{3})(\d)/,'$1.$2')
      .replace(/(\d{3})(\d{1,2})$/,'$1-$2');
  } else {
    return nums.substring(0,14)
      .replace(/(\d{2})(\d)/,'$1.$2')
      .replace(/(\d{3})(\d)/,'$1.$2')
      .replace(/(\d{3})(\d)/,'$1/$2')
      .replace(/(\d{4})(\d{1,2})$/,'$1-$2');
  }
}

function onDocInput(el) {
  const nums = el.value.replace(/\D/g,'');
  el.value = formatarDoc(nums);
  const span = document.getElementById('f-doc-tipo');
  if (!span) return;
  const len = nums.length;
  if (len === 11) span.innerHTML = '<span class="doc-tipo doc-cpf">CPF</span>';
  else if (len === 14) span.innerHTML = '<span class="doc-tipo doc-cnpj">CNPJ</span>';
  else span.innerHTML = '';
}

function onDocBlur(el) {
  el.value = formatarDoc(el.value);
  const nums = el.value.replace(/\D/g,'');
  const span = document.getElementById('f-doc-tipo');
  if (!span) return;
  const len = nums.length;
  if (len === 11) span.innerHTML = '<span class="doc-tipo doc-cpf">CPF</span>';
  else if (len === 14) span.innerHTML = '<span class="doc-tipo doc-cnpj">CNPJ</span>';
  else span.innerHTML = '';
}

function toUpper(el) {
  el.value = el.value.toUpperCase();
}

// ===================== MODAL USUARIO =====================
let _editandoUsuario = null;

function abrirModalUsuario(dados) {
  _editandoUsuario = dados ? dados.id : null;
  document.getElementById('modal-usuario-titulo').textContent = dados ? 'Editar Usuário' : 'Novo Usuário';
  document.getElementById('mu-username').value = dados ? dados.username : '';
  document.getElementById('mu-username').disabled = !!dados;
  document.getElementById('mu-nome').value = dados ? dados.full_name : '';
  document.getElementById('mu-senha').value = '';
  document.getElementById('mu-senha').required = !dados;
  document.getElementById('mu-perfil').value = dados ? dados.role : 'user';
  abrirModal('modal-usuario');
}

function salvarUsuario() {
  const username = document.getElementById('mu-username').value.trim();
  const full_name = document.getElementById('mu-nome').value.trim();
  const password = document.getElementById('mu-senha').value;
  const role = document.getElementById('mu-perfil').value;
  if (!username || !full_name) { alert('Preencha usuário e nome completo.'); return; }
  if (!_editandoUsuario && !password) { alert('Informe a senha.'); return; }

  if (_editandoUsuario) {
    fetch('/api/users/' + _editandoUsuario, {
      method:'PUT', headers:csrfHeaders(),
      body:JSON.stringify({full_name, role})
    }).then(r=>r.json()).then(d=>{
      if(d.ok){ fecharModal('modal-usuario'); renderUsuarios(); }
      else alert(d.erro || 'Erro ao atualizar');
    }).catch(()=>{ alert('Servidor offline. Use o modo servidor para gerenciar usuários.'); });
  } else {
    fetch('/api/users', {
      method:'POST', headers:csrfHeaders(),
      body:JSON.stringify({username, full_name, password, role})
    }).then(r=>r.json()).then(d=>{
      if(d.ok){ fecharModal('modal-usuario'); renderUsuarios(); }
      else alert(d.erro || 'Erro ao criar');
    }).catch(()=>{ alert('Servidor offline. Use o modo servidor para gerenciar usuários.'); });
  }
}

function excluirUsuario(id) {
  if (!confirm('Excluir este usuário?')) return;
  fetch('/api/users/' + id, { method:'DELETE', headers:csrfHeaders() })
    .then(r=>r.json()).then(d=>{
      if(d.ok) renderUsuarios();
      else alert(d.erro || 'Erro ao excluir');
    }).catch(()=>{ alert('Servidor offline.'); });
}

function renderUsuarios() {
  const tb = document.getElementById('tb-usuarios');
  fetch('/api/users')
    .then(r=>r.json()).then(users=>{
      if (!Array.isArray(users)) { tb.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#aaa;padding:32px">Servidor offline</td></tr>'; return; }
      tb.innerHTML = users.map(u => `<tr>
        <td>${escapeHtml(String(u.id))}</td><td>${escapeHtml(u.username)}</td><td>${escapeHtml(u.full_name)}</td>
        <td>${escapeHtml(u.role === 'admin' ? 'Admin' : 'Usuário')}</td>
        <td>${u.active ? '<span class="badge badge-ativo">Sim</span>' : '<span class="badge badge-vencido">Não</span>'}</td>
        <td>${escapeHtml(u.created_at || '-')}</td>
        <td style="display:flex;gap:4px;">
          <button class="btn btn-sm btn-primary" onclick='abrirModalUsuario(${JSON.stringify(u).replace(/'/g,"&#39;").replace(/</g,"\\u003c").replace(/>/g,"\\u003e")})'>Editar</button>
          <button class="btn btn-sm btn-danger" onclick="excluirUsuario(${Number(u.id)})">Exc</button>
        </td>
      </tr>`).join('');
    }).catch(()=>{
      tb.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#aaa;padding:32px">Servidor offline</td></tr>';
    });
}

// ===================== CONFIGURACAO =====================
function carregarConfig() {
  fetch('/api/config-email')
    .then(r=>r.json()).then(cfg => {
      if (cfg.smtp_server) document.getElementById('cfg-smtp').value = cfg.smtp_server || '';
      if (cfg.smtp_port) document.getElementById('cfg-porta').value = cfg.smtp_port || '';
      if (cfg.email_remetente) document.getElementById('cfg-email').value = cfg.email_remetente || '';
      if (cfg.email_senha) document.getElementById('cfg-senha').value = cfg.email_senha || '';
      if (cfg.email_destinatario) document.getElementById('cfg-dest').value = cfg.email_destinatario || '';
    }).catch(()=>{});
}

function salvarConfig() {
  const cfg = {
    smtp_server: document.getElementById('cfg-smtp').value.trim(),
    smtp_port: parseInt(document.getElementById('cfg-porta').value) || 587,
    email_remetente: document.getElementById('cfg-email').value.trim(),
    email_senha: document.getElementById('cfg-senha').value,
    email_destinatario: document.getElementById('cfg-dest').value.trim()
  };
  fetch('/api/config-email', {
    method:'POST', headers:csrfHeaders(), body:JSON.stringify(cfg)
  }).then(r=>r.json()).then(d=>{
    const msg = document.getElementById('cfg-msg');
    if(d.ok) { msg.className = 'ok-box'; msg.textContent = 'Configuração salva com sucesso!'; }
    else { msg.className = 'warn-box'; msg.textContent = d.erro || 'Erro ao salvar'; }
    msg.style.display = 'block';
    setTimeout(()=>{ msg.style.display = 'none'; }, 4000);
  }).catch(()=>{
    const msg = document.getElementById('cfg-msg');
    msg.className = 'warn-box';
    msg.textContent = 'Servidor offline. Inicie o servidor com "python app.py".';
    msg.style.display = 'block';
  });
}

function enviarLembrete() {
  const btn = document.querySelector('#page-configuracao .btn-success');
  btn.disabled = true; btn.textContent = 'Enviando...';
  fetch('/api/enviar-lembrete', { method:'POST', headers:csrfHeaders() })
    .then(r=>r.json()).then(d=>{
      const msg = document.getElementById('cfg-msg');
      if(d.ok) { msg.className = 'ok-box'; msg.textContent = d.msg || 'E-mail enviado!'; }
      else { msg.className = 'warn-box'; msg.textContent = d.erro || 'Erro ao enviar'; }
      msg.style.display = 'block';
      setTimeout(()=>{ msg.style.display = 'none'; }, 6000);
    }).catch(()=>{
      const msg = document.getElementById('cfg-msg');
      msg.className = 'warn-box';
      msg.textContent = 'Servidor offline. Inicie o servidor com "python app.py".';
      msg.style.display = 'block';
    }).finally(()=>{ btn.disabled = false; btn.textContent = 'Enviar Lembrete Agora'; });
}

// ===================== SHOW PAGE (atualizado) =====================
const _origShowPage = showPage;
showPage = function(id, btn) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + id).classList.add('active');
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  if(btn) btn.classList.add('active');

  if (id === 'dashboard') renderDashboard();
  if (id === 'contratos') renderContratos();
  if (id === 'pagamentos') renderPagamentos();
  if (id === 'novo-contrato') { limparFormContrato(); }
  if (id === 'usuarios') renderUsuarios();
  if (id === 'configuracao') carregarConfig();
};

// ===================== CSS ADICIONAL =====================
(function() {
  const style = document.createElement('style');
  style.textContent = '.ok-box{background:#d4edda;border-left:4px solid #2e7d52;padding:12px 16px;border-radius:0 6px 6px 0;font-size:0.88rem;margin-bottom:16px}.warn-box{background:#fff8e1;border-left:4px solid #d4820a;padding:12px 16px;border-radius:0 6px 6px 0;font-size:0.88rem;margin-bottom:16px}';
  document.head.appendChild(style);
})();

// ===================== CSRF TOKEN =====================
let csrfToken = null;

function getCsrfToken() {
  if (csrfToken) return Promise.resolve(csrfToken);
  return fetch('/api/me')
    .then(r => r.json())
    .then(d => { if (d.csrf_token) csrfToken = d.csrf_token; return csrfToken; })
    .catch(() => { csrfToken = ''; return ''; });
}

function csrfHeaders() {
  const h = {'Content-Type':'application/json'};
  if (csrfToken) h['X-CSRF-Token'] = csrfToken;
  return h;
}

// Check initial login state
checkLogin();
</script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print("index.html rewritten successfully.")
