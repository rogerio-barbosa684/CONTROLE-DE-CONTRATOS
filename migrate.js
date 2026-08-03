// Script para migrar dados do SQLite para o Supabase PostgreSQL
// Uso: node supabase/migrate.js

import sqlite3 from 'sqlite3'
import { createClient } from '@supabase/supabase-js'
import { readFileSync, writeFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const baseDir = resolve(__dirname, '..')

// Carrega .env manualmente (sem dotenv)
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
      // Tenta inserir um por um
      for (const row of batch) {
        const { error: e2 } = await supabase.from(supabaseTable).upsert(row, { onConflict: 'id' })
        if (e2) console.error(`    Erro no registro ${row.id || row.username}:`, e2.message)
      }
    }
  }
  console.log(`  ${table}: ${rows.length} registros migrados`)
}

function existsSync(p) {
  try { readFileSync(p); return true } catch { return false }
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
        password_hash: u.password_hash, role: u.role,
        active: u.active, created_at: u.created_at
      })
      if (error) console.error(`  Erro user ${u.username}:`, error.message)
    }
    console.log(`  users: ${users.length} registros migrados`)
  }

  await migrate('companies', 'companies')
  await migrate('contracts', 'contracts')
  await migrate('payments', 'payments')
  await migrate('additives', 'additives')
  await migrate('audit_log', 'audit_log', r => ({
    id: r.id, user_id: r.user_id, action: r.action,
    entity: r.entity, entity_id: r.entity_id,
    details: r.details, created_at: r.created_at
  }))
  await migrate('destinatarios', 'destinatarios')

  // Migrar email_config
  const emailRows = await query("SELECT * FROM config_email")
  if (emailRows.length) {
    const e = emailRows[0]
    await supabase.from('email_config').upsert({
      id: 1, smtp_server: e.smtp_server, smtp_port: e.smtp_port,
      email_remetente: e.email_remetente,
      email_senha_enc: e.email_senha_enc || '',
      email_destinatario: e.email_destinatario || ''
    })
    console.log('  email_config: 1 registro migrado')
  }

  db.close()
  console.log('=== Migracao concluida! ===')
}

main().catch(console.error)
