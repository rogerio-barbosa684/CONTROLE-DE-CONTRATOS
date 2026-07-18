-- Supabase SQL Schema for Controle de Contratos
-- Execute no SQL Editor do Supabase

-- Users
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (now()::text)
);

-- Companies
CREATE TABLE IF NOT EXISTS companies (
  id TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  cnpj TEXT DEFAULT '',
  criado_em TEXT NOT NULL DEFAULT (now()::text)
);

-- Contracts
CREATE TABLE IF NOT EXISTS contracts (
  id TEXT PRIMARY KEY,
  numero TEXT UNIQUE NOT NULL,
  fornecedor TEXT NOT NULL,
  cnpj TEXT,
  objeto TEXT NOT NULL,
  valor_total REAL NOT NULL DEFAULT 0,
  inicio TEXT NOT NULL,
  fim TEXT NOT NULL,
  tem_parcelas INTEGER NOT NULL DEFAULT 0,
  qtd_parcelas INTEGER,
  valor_parcela REAL,
  dia_vencimento INTEGER,
  responsavel TEXT,
  setor TEXT,
  obs TEXT,
  tipo TEXT,
  empresa_id TEXT,
  forma_pagamento TEXT,
  arquivo_contrato TEXT,
  created_by INTEGER,
  created_at TEXT NOT NULL DEFAULT (now()::text),
  updated_at TEXT
);

-- Payments
CREATE TABLE IF NOT EXISTS payments (
  id TEXT PRIMARY KEY,
  contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  descricao TEXT NOT NULL,
  vencimento TEXT NOT NULL,
  valor REAL NOT NULL DEFAULT 0,
  contrato_num TEXT,
  data_pagamento TEXT,
  valor_pago REAL,
  forma_pagamento TEXT,
  status TEXT NOT NULL DEFAULT 'pendente',
  obs TEXT,
  comprovante TEXT,
  created_by INTEGER,
  paid_by INTEGER,
  created_at TEXT NOT NULL DEFAULT (now()::text)
);

-- Additives
CREATE TABLE IF NOT EXISTS additives (
  id TEXT PRIMARY KEY,
  contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  numero TEXT,
  data_aditivo TEXT NOT NULL,
  tipo TEXT NOT NULL,
  nova_data_fim TEXT,
  acrescimo_valor REAL,
  descricao TEXT NOT NULL,
  arquivo_contrato TEXT,
  created_by INTEGER,
  created_at TEXT NOT NULL DEFAULT (now()::text)
);

-- Audit Log
CREATE TABLE IF NOT EXISTS audit_log (
  id SERIAL PRIMARY KEY,
  user_id INTEGER,
  action TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id TEXT,
  details TEXT,
  created_at TEXT NOT NULL DEFAULT (now()::text)
);

-- Email Recipients
CREATE TABLE IF NOT EXISTS destinatarios (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  nome TEXT DEFAULT '',
  empresa_ids TEXT DEFAULT '[]',
  criado_em TEXT NOT NULL DEFAULT (now()::text)
);

-- Email Config
CREATE TABLE IF NOT EXISTS email_config (
  id INTEGER PRIMARY KEY DEFAULT 1,
  smtp_server TEXT NOT NULL DEFAULT 'smtp.gmail.com',
  smtp_port INTEGER NOT NULL DEFAULT 587,
  email_remetente TEXT DEFAULT '',
  email_senha_enc TEXT DEFAULT '',
  email_destinatario TEXT DEFAULT ''
);

-- Insert initial admin user (password will be set by the API on first run)
INSERT INTO users (username, full_name, password_hash, role)
VALUES ('admin', 'Administrador', '$2b$12$placeholder', 'admin')
ON CONFLICT (username) DO NOTHING;

-- Insert placeholder email config
INSERT INTO email_config (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;
