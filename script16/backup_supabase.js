import { createClient } from '@supabase/supabase-js'
import { readFileSync, writeFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const envPath = resolve(__dirname, '.env')
for (const line of readFileSync(envPath, 'utf8').split('\n')) {
  const s = line.trim()
  if (s && !s.startsWith('#')) {
    const [k, ...v] = s.split('=')
    if (k) process.env[k.trim()] = v.join('=').trim()
  }
}

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY)
const data = {}
const tabelas = ['users', 'companies', 'contracts', 'payments', 'additives', 'audit_log', 'destinatarios', 'email_config']

for (const t of tabelas) {
  const { data: rows } = await supabase.from(t).select('*')
  data[t] = rows || []
  process.stdout.write(`  ${t}: ${(rows || []).length} registros\n`)
}
data.exportado_em = new Date().toISOString()

const ts = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')
const caminho = resolve(__dirname, `backup-supabase-${ts}.json`)
writeFileSync(caminho, JSON.stringify(data, null, 2), 'utf8')
console.log(`\nBackup salvo em: ${caminho}`)
console.log(`Tamanho: ${(Buffer.byteLength(JSON.stringify(data)) / 1024).toFixed(1)} KB`)
