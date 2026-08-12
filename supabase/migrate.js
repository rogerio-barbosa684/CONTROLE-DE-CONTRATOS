// Script para migrar dados do SQLite para o Supabase PostgreSQL
// Uso: node supabase/migrate.js

import sqlite3 from 'sqlite3'
import { createClient } from '@supabase/supabase-js'
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const baseDir = resolve(__dirname, '..')

function existsSync(p) {
  try { readFileSync(p); return true } catch { return false }
}

// Carrega .env manualmente
const envPath = resolve(baseDir, '.env')
if (existsSync(envPath)) {
  for (const line of readFileSync(envPath, 'utf8').split('\n')) {
    const s = line.trim()
    if (s && !s.startsWith('#')) {
      const [k, ...v] = s.split('=')
      if (k) process.env[k.trim()] = v.join('=').trim()
    }
  }
}

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const dbPath = resolve(baseDir, 'contratos.db')

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env')
  process.exit(1)
}

if (!existsSync(dbPath)) {
  console.error('Arquivo contratos.db nao encontrado em', dbPath)
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)
const db = new sqlite3.Database(dbPath)

function query(sql) {
  return new Promise((resolve, reject) => {
    db.all(sql, (err, rows) => { if (err) reject(err); else resolve(rows) })
  })
}

async function migrate(table, supabaseTable, transform = r => r) {
  console.log(`Migrando ${table}...`)
  const rows = await query(`SELECT * FROM ${table}`)
  if (!rows.length) { console.log(`  ${table}: 0 registros, ignorando`); return }
  const batchSize = 100
  for (let i = 0; i < rows.length; i += batchSize) {
    const batch = rows.slice(i, i + batchSize).map(transform)
    const { error } = await supabase.from(supabaseTable).upsert(batch, { onConflict: 'id' })
    if (error) {
      console.error(`  Erro em ${table} lote ${i}:`, error.message)
      for (const row of batch) {
        const { error: e2 } = await supabase.from(supabaseTable).upsert(row, { onConflict: 'id' })
        if (e2) console.error(`    Erro no registro ${row.id || row.username}:`, e2.message)
      }
    }
  }
  console.log(`  ${table}: ${rows.length} registros migrados`)
}

async function main() {
  console.log('=== Migracao SQLite -> Supabase ===')
  console.log(`Banco: ${dbPath}`)
  console.log(`Supabase: ${SUPABASE_URL}`)

  // Migrar users (preservando hash das senhas)
  const users = await query('SELECT * FROM users')
  if (users.length) {
    console.log('Migrando users...')
    for (const u of users) {
      const { error } = await supabase.from('users').upsert({
        id: u.id, username: u.username, full_name: u.full_name,
        email: u.email || '', password_hash: u.password_hash,
        role: u.role, active: u.active,
        password_changed_at: u.password_changed_at || null,
        created_at: u.created_at
      })
      if (error) console.error(`  Erro user ${u.username}:`, error.message)
    }
    console.log(`  users: ${users.length} registros migrados`)
  }

  await migrate('companies', 'companies')
  await migrate('contracts', 'contracts')
  await migrate('payments', 'payments')
  await migrate('additives', 'additives')
  await migrate('sectors', 'sectors')

  // Migrar destinatarios (incluindo setores e alertas)
  const destinatarios = await query('SELECT * FROM destinatarios')
  if (destinatarios.length) {
    console.log('Migrando destinatarios...')
    for (const d of destinatarios) {
      let setores = d.setores || '[]'
      let alertas = d.alertas || '[]'
      if (typeof setores === 'string' && !setores.startsWith('[')) {
        setores = JSON.stringify([setores])
      }
      if (typeof alertas === 'string' && !alertas.startsWith('[')) {
        alertas = JSON.stringify([alertas])
      }
      const { error } = await supabase.from('destinatarios').upsert({
        id: d.id, email: d.email, nome: d.nome || '',
        empresa_ids: d.empresa_ids || '[]',
        setores: setores, alertas: alertas
      })
      if (error) console.error(`  Erro destinatario ${d.email}:`, error.message)
    }
    console.log(`  destinatarios: ${destinatarios.length} registros migrados`)
  }

  // Migrar audit_log
  await migrate('audit_log', 'audit_log', r => ({
    id: r.id, user_id: r.user_id, action: r.action,
    entity: r.entity, entity_id: r.entity_id,
    details: r.details, created_at: r.created_at
  }))

  // Migrar certidoes
  await migrate('certidoes', 'certidoes', r => ({
    id: r.id, empresa_id: r.empresa_id || '',
    tipo: r.tipo || '', data_emissao: r.data_emissao || '',
    data_validade: r.data_validade || '',
    status: r.status || 'pendente',
    arquivo_nome: r.arquivo_nome || '',
    arquivo_dados: r.arquivo_dados || '',
    observacoes: r.observacoes || '',
    criado_em: r.criado_em
  }))

  // Migrar licitacoes
  await migrate('licitacoes', 'licitacoes', r => ({
    id: r.id, empresa_id: r.empresa_id || '',
    numero_licitacao: r.numero_licitacao || '',
    edital: r.edital || '', objeto: r.objeto || '',
    contrato_id: r.contrato_id || '', valor: r.valor || 0,
    data_homologacao: r.data_homologacao || '',
    data_inicio: r.data_inicio || '', data_fim: r.data_fim || '',
    status: r.status || 'em_andamento',
    arquivo_edital_nome: r.arquivo_edital_nome || '',
    arquivo_edital_dados: r.arquivo_edital_dados || '',
    arquivo_contrato_nome: r.arquivo_contrato_nome || '',
    arquivo_contrato_dados: r.arquivo_contrato_dados || '',
    observacoes: r.observacoes || '',
    criado_em: r.criado_em
  }))

  // Migrar email_config a partir do config_email.json
  const configPath = resolve(baseDir, 'config_email.json')
  if (existsSync(configPath)) {
    const emailCfg = JSON.parse(readFileSync(configPath, 'utf8'))
    console.log('Migrando email_config...')
    const { error } = await supabase.from('email_config').upsert({
      id: 1,
      smtp_server: emailCfg.smtp_server || 'smtp.gmail.com',
      smtp_port: emailCfg.smtp_port || 587,
      email_remetente: emailCfg.email_remetente || '',
      email_senha_enc: emailCfg.email_senha_enc || '',
      email_destinatario: emailCfg.email_destinatario || ''
    })
    if (error) console.error('  Erro email_config:', error.message)
    else console.log('  email_config: 1 registro migrado')
  }

  db.close()
  console.log('=== Migracao concluida! ===')
}

main().catch(console.error)
