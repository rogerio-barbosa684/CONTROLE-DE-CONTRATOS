# AGENTS.md - Controle de Contratos e Pagamentos

## Visão Geral

Sistema web para gestão de contratos, pagamentos/parcelas e vencimentos de empresas.
Single Page Application (SPA) com backend Supabase + Netlify Functions.

## Stack

- **Frontend**: HTML/CSS/JS puro (`index.html`) — sem frameworks
- **Backend**: Netlify Functions (`netlify/functions/api.js`) + Supabase (PostgreSQL)
- **Backend legado**: `api.js` (Flask-like, mantido para compatibilidade)
- **Banco local**: IndexedDB (offline/backup)
- **Banco remoto**: Supabase (PostgreSQL)
- **Autenticação**: JWT via cookies HttpOnly + CSRF token

## Estrutura de Arquivos

```
├── index.html                  # Frontend completo (HTML + CSS + JS inline)
├── api.js                      # Backend legado (compatibilidade)
├── netlify/functions/api.js    # Backend principal (Netlify Functions)
├── supabase/schema.sql         # Schema PostgreSQL
├── supabase/migrate.js         # Migração SQLite → Supabase
├── backup_supabase.js          # Script de backup
├── AGENTS.md                   # Este arquivo
└── README.md                   # Documentação de deploy
```

## Sistema de Perfis (Roles)

### Três roles disponíveis

| Role | Constante | Descrição |
|------|-----------|-----------|
| Administrador | `admin` | Acesso total ao sistema |
| Administrador de Setor | `setor_admin` | Acesso restrito a setores + gestão de usuários |
| Usuário | `user` | Acesso restrito a setores e empresas |

### Regras de acesso por role

#### `admin` (Administrador Global)
- Ver TODOS contratos, pagamentos e aditivos
- Criar/editar/excluir USUÁRIOS (qualquer perfil)
- Gerenciar EMPRESAS (criar, editar, inativar, excluir)
- Gerenciar SETORES (criar, editar, inativar, excluir)
- Gerenciar TIPOS DE SERVIÇO (criar, inativar, excluir)
- Configurar E-MAIL (SMTP)
- Ver HISTÓRICO de ações
- EXCLUIR contratos e pagamentos

#### `setor_admin` (Administrador de Setor)
- Ver contratos/pagamentos DOS SEUS SETORES
- Criar/editar USUÁRIOS (mas só com perfil `user`)
- Atribuir setores que ELE MESMO tem acesso ao novo usuário
- Na lista de usuários: só vê os dos seus setores
- NÃO pode criar usuários `admin` ou `setor_admin`
- NÃO pode gerenciar Empresas, Setores, Tipos, E-mail, Histórico
- Menu "Configuração" só mostra: "Minha Conta" e "Usuários"

#### `user` (Usuário Comum)
- Ver contratos/pagamentos DOS SEUS SETORES E EMPRESAS
- NÃO pode criar/usuários
- NÃO pode gerenciar nenhuma configuração
- Acesso apenas a: Dashboard, Contratos, Pagamentos, Minha Conta

### Funções de validação no backend

```javascript
// Aceita admin E setor_admin (rotas de gestão de usuários)
function requireAdmin(user) {
  if (!user || (user.role !== 'admin' && user.role !== 'setor_admin')) {
    return json({ ok: false, erro: 'Acesso restrito ao administrador' }, 403)
  }
  return null
}

// Aceita SOMente admin global (rotas de config: empresas, setores, tipos, etc)
function requireGlobalAdmin(user) {
  if (!user || user.role !== 'admin') {
    return json({ ok: false, erro: 'Acesso restrito ao administrador global' }, 403)
  }
  return null
}
```

### Rotas protegidas por cada função

**`requireAdmin()`** (admin + setor_admin):
- `GET /api/users` — listar usuários
- `POST /api/users` — criar usuário
- `PUT /api/users/:id` — editar usuário
- `DELETE /api/users/:id` — inativar usuário

**`requireGlobalAdmin()`** (só admin):
- `DELETE /api/companies/:id` — excluir empresa
- `DELETE /api/contracts/:id` — excluir contrato (+ pagamentos e aditivos)
- `DELETE /api/payments/:id` — excluir pagamento
- `POST /api/sectors` — criar setor
- `PUT /api/sectors/:id` — editar setor
- `DELETE /api/sectors/:id` — excluir setor

## Regra Especial: Setor "Financeiro"

Se um usuário (qualquer role) tem o setor **"Financeiro"** vinculado, ele automaticamente:
- Vê TODOS os setores (filtra por setor é desabilitado)
- Em `getLoggedUserSetorIds()` retorna `null` → sem filtro
- Afeta: Dashboard, Lista de Contratos, Lista de Pagamentos
- Afeta: criação de usuários (pode atribuir qualquer setor)

## Tabelas/Banco de Dados

### IndexedDB (local, backup offline)
- `contratos` — contratos cadastrados
- `pagamentos` — parcelas/pagamentos
- `tipos` — tipos de serviço
- `empresas` — empresas
- `user_empresas` — vínculo usuário → empresas
- `destinatarios` — destinatários de e-mail
- `sectors` — setores
- `user_setores` — vínculo usuário → setores

### Supabase (PostgreSQL, remoto)
- `users` — usuários (id, username, full_name, password_hash, role, active, created_at)
- `contracts` — contratos
- `payments` — pagamentos/parcelas
- `additives` — aditivos contratuais
- `companies` — empresas
- `sectors` — setores
- `user_empresas` — vínculo usuário-empresa
- `user_setores` — vínculo usuário-setor
- `destinatarios` — destinatários de e-mail
- `audit_log` — log de auditoria
- `config_email` — configuração SMTP

## Funcionalidades Principais

1. **Dashboard** — Cards resumo + tabela de próximos vencimentos
2. **Contratos** — CRUD completo com filtros, paginação, exportação Excel
3. **Pagamentos** — CRUD com baixa, estorno, pagamentos em lote
4. **Aditivos** — Registro de aditivos contratuais (prazo, valor, ambos)
5. **Configuração** — Usuários, Empresas, Setores, Tipos, Destinatários, E-mail, Histórico
6. **Assistente Virtual** — Chat integrado com respostas sobre o sistema
7. **Modo Escuro** — Toggle tema claro/escuro
8. **Notificações** — Alertas de vencimento

## Convenções de Código

- JavaScript vanilla, sem bundler
- Funções globais no escopo window
- Estilos inline no `<style>` do `<head>`
- IDs dos elementos seguem padrão: `f-` (form), `filtro-` (filtros), `tb-` (tabelas), `cfg-` (config), `mu-` (modal usuário), `mc-` (minha conta), `mp-` (modal pagamento), `bx-` (baixa), `ad-` (aditivo)
- Escape de HTML: função `escapeHtml()` para prevenir XSS
- Formatação de moeda: `fmtMoeda()`
- Formatação de data: `fmtData()`
- UID único: `uid()` (gera ID randômico)
