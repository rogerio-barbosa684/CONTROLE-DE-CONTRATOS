-- Migration: Sync via log com resolucao por timestamp
-- Execute no SQL Editor do Supabase

-- Adicionar updated_at e deleted_at em payments
ALTER TABLE payments ADD COLUMN IF NOT EXISTS updated_at TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS deleted_at TEXT;

-- Adicionar updated_at e deleted_at em additives
ALTER TABLE additives ADD COLUMN IF NOT EXISTS updated_at TEXT;
ALTER TABLE additives ADD COLUMN IF NOT EXISTS deleted_at TEXT;

-- Adicionar updated_at e deleted_at em certidoes
ALTER TABLE certidoes ADD COLUMN IF NOT EXISTS updated_at TEXT;
ALTER TABLE certidoes ADD COLUMN IF NOT EXISTS deleted_at TEXT;

-- Adicionar updated_at e deleted_at em licitacoes
ALTER TABLE licitacoes ADD COLUMN IF NOT EXISTS updated_at TEXT;
ALTER TABLE licitacoes ADD COLUMN IF NOT EXISTS deleted_at TEXT;

-- Adicionar updated_at e deleted_at em destinatarios
ALTER TABLE destinatarios ADD COLUMN IF NOT EXISTS updated_at TEXT;
ALTER TABLE destinatarios ADD COLUMN IF NOT EXISTS deleted_at TEXT;

-- Criar tabela sync_log
CREATE TABLE IF NOT EXISTS sync_log (
  id SERIAL PRIMARY KEY,
  entity TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action TEXT NOT NULL,
  machine_id TEXT DEFAULT '',
  data_hash TEXT DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (now()::text)
);
CREATE INDEX IF NOT EXISTS idx_sync_log_entity ON sync_log(entity, entity_id);
CREATE INDEX IF NOT EXISTS idx_sync_log_created ON sync_log(created_at);

-- Preencher updated_at existente com created_at para registros sem timestamp
UPDATE payments SET updated_at = created_at WHERE updated_at IS NULL;
UPDATE additives SET updated_at = created_at WHERE updated_at IS NULL;
UPDATE certidoes SET updated_at = criado_em WHERE updated_at IS NULL;
UPDATE licitacoes SET updated_at = criado_em WHERE updated_at IS NULL;
UPDATE destinatarios SET updated_at = criado_em WHERE updated_at IS NULL;
UPDATE contracts SET updated_at = created_at WHERE updated_at IS NULL;
