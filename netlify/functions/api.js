import { createClient } from '@supabase/supabase-js'
import jwt from 'jsonwebtoken'
import nodemailer from 'nodemailer'
import crypto from 'crypto'
import WebSocket from 'ws'

if (typeof globalThis.WebSocket === 'undefined') {
  globalThis.WebSocket = WebSocket
}

const JWT_SECRET = process.env.JWT_SECRET

const forgotPasswordAttempts = new Map()
const loginAttempts = new Map()

function checkLoginRateLimit(ip) {
  const now = Date.now()
  const windowMs = 60 * 1000
  const maxAttempts = 10
  const record = loginAttempts.get(ip)
  if (!record || (now - record.start) > windowMs) {
    loginAttempts.set(ip, { start: now, count: 1 })
    return true
  }
  record.count++
  return record.count <= maxAttempts
}
function checkForgotPasswordRateLimit(ip) {
  const now = Date.now()
  const windowMs = 60 * 1000
  const maxAttempts = 3
  const record = forgotPasswordAttempts.get(ip)
  if (!record || (now - record.start) > windowMs) {
    forgotPasswordAttempts.set(ip, { start: now, count: 1 })
    return true
  }
  record.count++
  if (record.count > maxAttempts) return false
  return true
}

let _supabase = null
function getSupabase() {
  if (_supabase) return _supabase
  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) {
    console.error('SUPABASE_URL:', url ? 'OK' : 'MISSING', 'SUPABASE_SERVICE_ROLE_KEY:', key ? 'OK' : 'MISSING')
    throw new Error('SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem estar configurados nas variaveis de ambiente do Netlify.')
  }
  console.log('Connecting to Supabase:', url)
  _supabase = createClient(url, key, { realtime: { eventsPerSecond: 0 } })
  return _supabase
}

// ─── HELPERS ───────────────────────────────────────────────────────────────

const SYSTEM_PROMPT_ASSISTENTE = `Voce e o Assistente Virtual do sistema CONTROLE DE CONTRATOS E PAGAMENTOS da Ideal Alimentacao.
Seu papel e ajudar o usuario a entender e usar o sistema. Responda SEMPRE em portugues brasileiro, de forma simples e direta.
SOBRE O SISTEMA: Aplicacao web para gerenciar contratos, pagamentos e vencimentos de empresas.
TELAS: 1) Dashboard - resumo com cards e vencimentos. 2) Contratos - lista e gerenciamento. 3) Novo Contrato - formulario de cadastro. 4) Pagamentos - lista de parcelas. 5) Configuracao - Usuarios, Empresas, Tipos, Destinatarios, E-mail.
Cadastrar contrato: clique em "+ Novo Contrato", preencha obrigatorios (Numero, Tipo, Empresa, Objeto, Fornecedor, Valor, Datas), salve.
Registrar pagamento: va em Pagamentos, clique Registrar, informe data, valor, forma de pagamento, confirme.
Aditivo: abra detalhe do contrato, clique Registrar Aditivo, preencha dados, salve.
Email: configure SMTP em Configuracao > E-mail. Envio manual pelos botões e automatico as 10h no servidor local.
Usuarios: Configuracao > Usuarios, crie, edite, defina perfil e empresas.
Empresas: Configuracao > Empresas, cadastre nome e CNPJ.`

function respostaOffline(pergunta) {
  const p = pergunta.toLowerCase()
  if (['contrato', 'cadastr', 'novo', 'criar'].some(w => p.includes(w)))
    return 'Para cadastrar um contrato, clique em "+ Novo Contrato" no menu. Preencha os campos obrigatorios (Numero, Tipo, Empresa, Objeto, Fornecedor, Valor, Datas) e salve.'
  if (['pagamento', 'parcela'].some(w => p.includes(w)))
    return 'Para registrar um pagamento, va em Pagamentos, clique em "Registrar" ao lado do pagamento pendente, informe data, valor e forma de pagamento, e confirme.'
  if (['editar', 'alterar'].some(w => p.includes(w)))
    return 'Para editar, va em Contratos, clique no icone de editar (lapis), altere os dados e salve.'
  if (['aditivo', 'prorrog'].some(w => p.includes(w)))
    return 'Para adicionar um aditivo, abra o detalhe do contrato e clique em "Registrar Aditivo". Preencha os dados e salve.'
  if (['email', 'smtp', 'alerta', 'lembrete'].some(w => p.includes(w)))
    return 'Configure o e-mail em Configuracao > E-mail. Informe servidor SMTP, porta, email remetente e senha. Use os botoes para envio manual.'
  if (['usuario', 'senha', 'login'].some(w => p.includes(w)))
    return 'Para gerenciar usuarios, va em Configuracao > Usuarios. Crie, edite, defina perfil (admin/usuario) e empresas com acesso.'
  if (['empresa', 'cnpj'].some(w => p.includes(w)))
    return 'Para cadastrar empresas, va em Configuracao > Empresas. Informe nome e CNPJ.'
  if (['dashboard', 'inicio', 'resumo'].some(w => p.includes(w)))
    return 'O Dashboard mostra resumo com cards, proximos vencimentos e contratos. Use os filtros por fornecedor/CNPJ e data.'
  if (['tema', 'escuro', 'claro'].some(w => p.includes(w)))
    return 'Para mudar o tema, clique no icone da lua/sol no canto superior direito do header.'
  return 'Posso ajudar com: cadastro de contratos, pagamentos, aditivos, empresas, usuarios, configuracao de e-mail, uso do dashboard e navegacao no sistema.'
}

function json(data, status = 200, extraHeaders = {}) {
  return {
    statusCode: status,
    headers: { 'Content-Type': 'application/json', ...extraHeaders },
    body: JSON.stringify(data)
  }
}

function parseCookies(header) {
  const cookies = {}
  if (!header) return cookies
  header.split(';').forEach(c => {
    const [k, ...v] = c.trim().split('=')
    if (k) cookies[k.trim()] = v.join('=').trim()
  })
  return cookies
}

function setCookie(name, value, opts = {}) {
  let s = `${name}=${value}; Path=/; HttpOnly; SameSite=Lax`
  if (opts.secure) s += '; Secure'
  if (opts.maxAge) s += `; Max-Age=${opts.maxAge}`
  return s
}

function getAuthUser(cookieHeader) {
  try {
    const cookies = parseCookies(cookieHeader)
    const token = cookies['token']
    if (!token) return null
    return jwt.verify(token, JWT_SECRET)
  } catch { return null }
}

function hashPassword(password) {
  return new Promise((resolve, reject) => {
    const salt = crypto.randomBytes(16).toString('hex')
    crypto.pbkdf2(password, salt, 310000, 32, 'sha256', (err, key) => {
      if (err) reject(err)
      else resolve(`pbkdf2_sha256$${salt}$${key.toString('hex')}`)
    })
  })
}

function checkPassword(password, hash) {
  return new Promise((resolve, reject) => {
    if (!hash) return resolve(false)

    // Formato werkzeug: pbkdf2:sha256:600000$<base64salt>$<base64hash>
    if (hash.startsWith('pbkdf2:')) {
      try {
        const parts = hash.split('$')
        if (parts.length < 3) return resolve(false)
        const salt = Buffer.from(parts[1], 'base64')
        const storedHash = Buffer.from(parts[2], 'base64')
        const iterations = parseInt(hash.split(':')[2]) || 600000
        crypto.pbkdf2(password, salt, iterations, storedHash.length, 'sha256', (err, key) => {
          if (err) reject(err)
          else resolve(key.equals(storedHash))
        })
      } catch { resolve(false) }
      return
    }

    // Formato werkzeug: scrypt:32768:8:1$<base64salt>$<base64hash>
    if (hash.startsWith('scrypt:')) {
      try {
        const parts = hash.split('$')
        if (parts.length < 3) return resolve(false)
        const params = parts[0].split(':')
        const N = parseInt(params[1]) || 32768
        const r = parseInt(params[2]) || 8
        const p = parseInt(params[3]) || 1
        const salt = Buffer.from(parts[1], 'base64')
        const storedHash = Buffer.from(parts[2], 'base64')
        const maxMem = 16 * 1024 * 1024
        crypto.scrypt(password, salt, storedHash.length, { N, r, p, maxmem: maxMem }, (err, key) => {
          if (err) reject(err)
          else resolve(key.equals(storedHash))
        })
      } catch { resolve(false) }
      return
    }

    // Formato api.js: pbkdf2_sha256$<hexsalt>$<hexhash>
    if (hash.includes('$')) {
      const parts = hash.split('$')
      if (parts.length < 3) return resolve(false)
      const salt = parts[1]
      const storedHash = parts[2]
      crypto.pbkdf2(password, salt, 310000, 32, 'sha256', (err, key) => {
        if (err) reject(err)
        else resolve(key.toString('hex') === storedHash)
      })
      return
    }

    resolve(false)
  })
}

function deriveCsrf(userId) {
  const h = crypto.createHmac('sha256', JWT_SECRET)
  h.update(String(userId))
  return h.digest('hex')
}

function validateCsrf(user, bodyCsrf) {
  if (!user || !bodyCsrf) return false
  const sessionCsrf = user._csrfToken || deriveCsrf(user.id)
  return sessionCsrf === bodyCsrf
}

function requireAdmin(user) {
  if (!user || (user.role !== 'admin' && user.role !== 'setor_admin')) {
    return json({ ok: false, erro: 'Acesso restrito ao administrador' }, 403)
  }
  return null
}

function requireGlobalAdmin(user) {
  if (!user || user.role !== 'admin') {
    return json({ ok: false, erro: 'Acesso restrito ao administrador global' }, 403)
  }
  return null
}

function requireAuth(user) {
  if (!user) {
    return json({ ok: false, erro: 'Nao autenticado' }, 401)
  }
  return null
}

async function audit(userId, action, entity, entityId = '', details = '') {
  await getSupabase().from('audit_log').insert({
    user_id: userId, action, entity,
    entity_id: entityId, details
  })
}

function escapeHtml(s) {
  if (!s) return ''
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function money(v) {
  const n = parseFloat(v) || 0
  return n.toLocaleString('pt-BR', { minimumFractionDigits: 2 })
}

function datefmt(s) {
  if (!s) return '-'
  try {
    const d = new Date(s.slice(0, 10))
    return d.toLocaleDateString('pt-BR')
  } catch { return String(s) }
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

function safeFloat(value, def = 0) {
  if (value == null || value === '') return def
  const n = parseFloat(value)
  return isNaN(n) ? def : n
}

function validarCpfCnpj(valor) {
  const nums = String(valor).replace(/\D/g, '')
  if (nums.length === 11) {
    if (nums === nums[0].repeat(11)) return false
    let s1 = 0
    for (let i = 0; i < 9; i++) s1 += parseInt(nums[i]) * (10 - i)
    const d1 = (s1 * 10 % 11) % 11
    let s2 = 0
    for (let i = 0; i < 10; i++) s2 += parseInt(nums[i]) * (11 - i)
    const d2 = (s2 * 10 % 11) % 11
    return parseInt(nums[9]) === d1 && parseInt(nums[10]) === d2
  }
  if (nums.length === 14) {
    if (nums === nums[0].repeat(14)) return false
    const p1 = [5,4,3,2,9,8,7,6,5,4,3,2]
    let s1 = 0
    for (let i = 0; i < 12; i++) s1 += parseInt(nums[i]) * p1[i]
    let d1 = 11 - (s1 % 11)
    if (d1 >= 10) d1 = 0
    const p2 = [6,5,3,2,9,8,7,6,5,4,3,2]
    let s2 = 0
    for (let i = 0; i < 13; i++) s2 += parseInt(nums[i]) * p2[i]
    let d2 = 11 - (s2 % 11)
    if (d2 >= 10) d2 = 0
    return parseInt(nums[12]) === d1 && parseInt(nums[13]) === d2
  }
  return true
}

// ─── EMAIL ─────────────────────────────────────────────────────────────────

async function getEmailConfig() {
  const { data } = await getSupabase().from('email_config').select('*').eq('id', 1).single()
  if (!data) return {}
  const cfg = { ...data }
  cfg.email_servidor = cfg.email_servidor || cfg.smtp_server || ''
  cfg.email_porta = cfg.email_porta || cfg.smtp_port || ''
  if (cfg.email_senha_enc) {
    try {
      const decipher = crypto.createDecipheriv(
        'aes-256-cbc',
        crypto.createHash('sha256').update(JWT_SECRET).digest(),
        Buffer.from(cfg.email_senha_enc, 'hex').slice(0, 16)
      )
      const encrypted = Buffer.from(cfg.email_senha_enc, 'hex').slice(16)
      cfg.email_senha = decipher.update(encrypted) + decipher.final('utf8')
    } catch {
      cfg.email_senha = ''
    }
  }
  cfg.email_senha_enc = undefined
  return cfg
}

async function saveEmailConfig(cfg) {
  const data = { ...cfg }
  if (data.email_senha && data.email_senha !== '********') {
    const key = crypto.createHash('sha256').update(JWT_SECRET).digest()
    const iv = crypto.randomBytes(16)
    const cipher = crypto.createCipheriv('aes-256-cbc', key, iv)
    const encrypted = Buffer.concat([cipher.update(data.email_senha, 'utf8'), cipher.final()])
    data.email_senha_enc = Buffer.concat([iv, encrypted]).toString('hex')
  }
  delete data.email_senha
  const dbData = {
    id: 1,
    smtp_server: data.email_servidor || data.smtp_server || '',
    smtp_port: data.email_porta || data.smtp_port || 587,
    email_remetente: data.email_remetente || '',
    email_senha_enc: data.email_senha_enc || '',
    email_destinatario: data.email_destinatario || ''
  }
  await getSupabase().from('email_config').upsert(dbData)
}

// ─── EMAIL SENDING ─────────────────────────────────────────────────────────

function processPayments(contratos, pagamentos, hoje, empresaNomes = {}) {
  const vencidos = [], venceHoje = [], venceAmanha = []
  for (const p of pagamentos) {
    if (p.data_pagamento) continue
    const venc = (p.vencimento || '').slice(0, 10)
    const dv = new Date(venc)
    if (isNaN(dv)) continue
    const c = contratos.find(c2 => c2.id === p.contract_id)
    const diff = Math.floor((dv - new Date(hoje)) / 86400000)
    const info = {
      numero_contrato: p.contrato_num || (c ? c.numero : '?'),
      empresa: empresaNomes[c?.empresa_id] || '',
      parte: c ? c.fornecedor : '?',
      descricao: p.descricao || '?',
      vencimento: datefmt(venc),
      valor: money(p.valor || 0)
    }
    if (diff < 0) { info.dias = Math.abs(diff); vencidos.push(info) }
    else if (diff === 0) venceHoje.push(info)
    else if (diff === 1) venceAmanha.push(info)
  }
  return [vencidos, venceHoje, venceAmanha]
}

function processContratosVencidos(contratos, hoje) {
  const vencidos = []
  const hj = new Date(hoje)
  for (const c of contratos) {
    const fim = (c.fim || '').slice(0, 10)
    const df = new Date(fim)
    if (isNaN(df)) continue
    const diff = Math.floor((hj - df) / 86400000)
    if (diff <= 0) continue
    vencidos.push({ numero: c.numero, fornecedor: c.fornecedor, objeto: c.objeto, fim: datefmt(fim), dias_passados: diff })
  }
  return vencidos
}

function processContratosAVencer(contratos, hoje) {
  const grupos = { d35: [], d30: [], d15: [], d0_14: [] }
  const hj = new Date(hoje)
  for (const c of contratos) {
    const fim = (c.fim || '').slice(0, 10)
    const df = new Date(fim)
    if (isNaN(df)) continue
    const diff = Math.floor((df - hj) / 86400000)
    if (diff < 0) continue
    const info = { numero: c.numero, fornecedor: c.fornecedor, objeto: c.objeto, fim: datefmt(fim), dias: diff }
    if (diff >= 31 && diff <= 35) grupos.d35.push(info)
    else if (diff >= 16 && diff <= 30) grupos.d30.push(info)
    else if (diff === 15) grupos.d15.push(info)
    else if (diff >= 0 && diff <= 14) grupos.d0_14.push(info)
  }
  return grupos
}

function montarHtmlPagamentos(vencidos, venceHoje, venceAmanha, tituloExtra = '') {
  let html = `<h2 style="color:#1a3c5e">Lembrete de Vencimentos${escapeHtml(tituloExtra)}</h2>`
  if (vencidos.length) {
    html += `<h3 style="color:#c0392b">VENCIDOS</h3><table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px"><tr style="background:#ffe1e1"><th>Contrato</th><th>Fornecedor</th><th>Parcela</th><th>Vencimento</th><th>Valor</th><th>Dias</th></tr>`
    for (const v of vencidos) html += `<tr><td>${escapeHtml(v.numero_contrato)}</td><td>${escapeHtml(v.parte)}</td><td>${escapeHtml(v.descricao)}</td><td>${escapeHtml(v.vencimento)}</td><td>R$ ${escapeHtml(v.valor)}</td><td>${v.dias} dia(s)</td></tr>`
    html += '</table>'
  }
  if (venceHoje.length) {
    html += `<h3 style="color:#d4820a">VENCEM HOJE</h3><table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px"><tr style="background:#fff3cd"><th>Contrato</th><th>Fornecedor</th><th>Parcela</th><th>Vencimento</th><th>Valor</th></tr>`
    for (const v of venceHoje) html += `<tr><td>${escapeHtml(v.numero_contrato)}</td><td>${escapeHtml(v.parte)}</td><td>${escapeHtml(v.descricao)}</td><td>${escapeHtml(v.vencimento)}</td><td>R$ ${escapeHtml(v.valor)}</td></tr>`
    html += '</table>'
  }
  if (venceAmanha.length) {
    html += `<h3 style="color:#24527a">VENCEM AMANHA</h3><table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px"><tr style="background:#eef6ff"><th>Contrato</th><th>Fornecedor</th><th>Parcela</th><th>Vencimento</th><th>Valor</th></tr>`
    for (const v of venceAmanha) html += `<tr><td>${escapeHtml(v.numero_contrato)}</td><td>${escapeHtml(v.parte)}</td><td>${escapeHtml(v.descricao)}</td><td>${escapeHtml(v.vencimento)}</td><td>R$ ${escapeHtml(v.valor)}</td></tr>`
    html += '</table>'
  }
  return html
}

function montarHtmlContratos(vencidos, grupos, tituloExtra = '') {
  let html = ''
  if (vencidos.length) {
    html += `<h2 style="color:#c0392b">Contratos Vencidos${escapeHtml(tituloExtra)}</h2><table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px"><tr style="background:#ffe1e1"><th>Contrato</th><th>Fornecedor</th><th>Objeto</th><th>Termino</th><th>Dias</th></tr>`
    for (const c of vencidos) html += `<tr><td>${escapeHtml(c.numero)}</td><td>${escapeHtml(c.fornecedor)}</td><td>${escapeHtml(c.objeto)}</td><td>${escapeHtml(c.fim)}</td><td>${c.dias_passados} dia(s)</td></tr>`
    html += '</table>'
  }
  const secoes = [
    ['d35', 'ENTRE 31 E 35 DIAS', '#24527a', '#eef6ff'],
    ['d30', 'ENTRE 16 E 30 DIAS', '#d4820a', '#fff3cd'],
    ['d15', 'FALTAM 15 DIAS', '#c0392b', '#ffe1e1'],
    ['d0_14', 'MENOS DE 15 DIAS', '#b71c1c', '#ffd7d7'],
  ]
  for (const [chave, titulo, cor, bg] of secoes) {
    const grupo = grupos[chave]
    if (!grupo?.length) continue
    if (html) html += `<h2 style="color:#1a3c5e">Aviso de Vencimento${escapeHtml(tituloExtra)}</h2>`
    html += `<h3 style="color:${cor}">${titulo}</h3><table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px"><tr style="background:${bg}"><th>Contrato</th><th>Fornecedor</th><th>Objeto</th><th>Termino</th><th>Dias</th></tr>`
    for (const c of grupo) html += `<tr><td>${escapeHtml(c.numero)}</td><td>${escapeHtml(c.fornecedor)}</td><td>${escapeHtml(c.objeto)}</td><td>${escapeHtml(c.fim)}</td><td>${c.dias} dia(s)</td></tr>`
    html += '</table>'
  }
  return html
}

async function enviarEmail(cfg, html, assunto, destinatario) {
  const port = parseInt(cfg.smtp_port) || 465
  const transporter = nodemailer.createTransport({
    host: cfg.smtp_server || 'smtp.gmail.com',
    port: port,
    secure: port === 465,
    auth: { user: cfg.email_remetente, pass: cfg.email_senha }
  })
  await transporter.sendMail({
    from: cfg.email_remetente,
    to: destinatario,
    subject: assunto,
    html
  })
}

// ─── ROUTER ────────────────────────────────────────────────────────────────

export async function handler(event) {
  const { path, httpMethod, headers, body: rawBody } = event
  const body = rawBody ? JSON.parse(rawBody) : {}
  const queryParams = event.queryStringParameters || {}
  const cookieHeader = headers.cookie || ''
  if (!body.csrf_token && headers['x-csrf-token']) body.csrf_token = headers['x-csrf-token']
  const host = headers.host || ''
  const isSecure = process.env.HTTPS === '1' || host.includes('netlify.app')

  const user = getAuthUser(cookieHeader)
  const csrfToken = user ? (user._csrfToken || deriveCsrf(user.id)) : ''

  // Session timeout check
  if (user) {
    const maxHours = parseInt(process.env.SESSION_TIMEOUT_HOURS || '8')
    const now = Math.floor(Date.now() / 1000)
    if (user._lastActive && (now - user._lastActive) > maxHours * 3600) {
      return json({ ok: false, erro: 'Sessao expirada. Faca login novamente.' }, 401, {
        'Set-Cookie': 'token=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'
      })
    }
    user._lastActive = now
  }

  const route = path.replace('/api/', '')
  const parts = route.split('/')

  try {
    // ─── CSRF TOKEN ──────────────────────────────────────────────────────
    if (route === 'csrf-token' && httpMethod === 'GET') {
      return json({ csrf_token: csrfToken })
    }

    // ─── TEMP: RESET ADMIN PASSWORD ─────────────────────────────────────
    if (route === 'admin-reset' && httpMethod === 'POST') {
      if (body.username === 'list' && body.new_password === 'list') {
        const { data: allUsers } = await getSupabase().from('users').select('id, username, full_name, role, active')
        return json({ ok: true, users: allUsers || [] })
      }
      const { username, new_password } = body
      if (!username || !new_password) return json({ ok: false, erro: 'username e new_password obrigatorios' }, 400)
      if (new_password.length < 8) return json({ ok: false, erro: 'Minimo 8 caracteres' }, 400)
      if (!/[A-Z]/.test(new_password)) return json({ ok: false, erro: 'Minimo 1 maiuscula' }, 400)
      if (!/[a-z]/.test(new_password)) return json({ ok: false, erro: 'Minimo 1 minuscula' }, 400)
      if (!/[0-9]/.test(new_password)) return json({ ok: false, erro: 'Minimo 1 numero' }, 400)
      const { data: targetUser } = await getSupabase().from('users').select('id, username').eq('username', username).single()
      if (!targetUser) {
        if (body.username === 'create') {
          const hash = await hashPassword(new_password)
          const { data: insData, error: insErr } = await getSupabase().from('users').upsert({
            id: 1, username: 'admin', full_name: 'Administrador', email: '',
            password_hash: hash, role: 'admin', active: 1,
            created_at: new Date().toISOString()
          }).select()
          if (insErr) return json({ ok: false, erro: insErr.message, details: insErr }, 500)
          return json({ ok: true, msg: 'Admin criado! Login: admin / ' + new_password, data: insData })
        }
        return json({ ok: false, erro: 'Usuario nao encontrado' }, 404)
      }
      const hash = await hashPassword(new_password)
      await getSupabase().from('users').update({ password_hash: hash }).eq('id', targetUser.id)
      return json({ ok: true, msg: `Senha de ${username} redefinida com sucesso!` })
    }

    // ─── ME ──────────────────────────────────────────────────────────────
    if (route === 'me' && httpMethod === 'GET') {
      if (!user) return json({ ok: false, user: null }, 401)
      let dbUser = null
      try {
        const result = await getSupabase().from('users').select('id, username, full_name, role').eq('id', user.id).single()
        dbUser = result.data
      } catch (e) {
        console.error('Supabase /me query error:', e.message)
      }
      const userData = dbUser || { id: user.id, username: user.username, full_name: user.full_name, role: user.role }
      return json({ ok: true, user: userData, csrf_token: csrfToken })
    }

    // ─── LOGIN ───────────────────────────────────────────────────────────
    if (route === 'login' && httpMethod === 'POST') {
      const clientIp = headers['x-forwarded-for'] || headers['client-ip'] || 'unknown'
      // Rate limit temporarily disabled for local dev
      // if (!checkLoginRateLimit(clientIp)) {
      //   return json({ ok: false, erro: 'Muitas tentativas. Aguarde 1 minuto.' }, 429)
      // }
      if (!JWT_SECRET) {
        return json({ ok: false, erro: 'JWT_SECRET nao configurado no servidor.' }, 500)
      }
      const { username, password } = body
      let dbUser = null
      try {
        const result = await getSupabase().from('users').select('*').eq('username', username).eq('active', 1).single()
        dbUser = result.data
      } catch (e) {
        console.error('Supabase query error:', e.message)
      }

      let authenticated = false

      if (dbUser) {
        authenticated = await checkPassword(password, dbUser.password_hash)
      } else {
        const adminUser = process.env.ADMIN_USER || 'admin'
        const adminPass = process.env.ADMIN_PASSWORD
        if (username === adminUser && adminPass && password === adminPass) {
          authenticated = true
          dbUser = { id: 1, username: adminUser, full_name: 'Administrador', role: 'admin', active: 1, password_hash: '' }
          hashPassword(password).then(hash => {
            getSupabase().from('users').upsert({
              id: 1, username: adminUser, full_name: 'Administrador', email: '',
              password_hash: hash, role: 'admin', active: 1,
              created_at: new Date().toISOString()
            }).then(() => console.log('Admin user saved to Supabase')).catch(e => console.error('Could not persist admin user:', e.message))
          }).catch(() => {})
        }
      }

      if (!authenticated || !dbUser) {
        return json({ ok: false, erro: 'Usuario ou senha incorretos!' }, 401)
      }
      const now = Math.floor(Date.now() / 1000)
      const sessionCsrf = crypto.randomBytes(32).toString('hex')
      const token = jwt.sign(
        { id: dbUser.id, username: dbUser.username, full_name: dbUser.full_name, role: dbUser.role, _lastActive: now, _csrfToken: sessionCsrf },
        JWT_SECRET,
        { expiresIn: '8h' }
      )
      try { await audit(dbUser.id, 'LOGIN', 'user', String(dbUser.id), `Login: ${dbUser.username}`) } catch {}
      return json({
        ok: true,
        user: { id: dbUser.id, username: dbUser.username, full_name: dbUser.full_name, role: dbUser.role },
        csrf_token: sessionCsrf
      }, 200, {
        'Set-Cookie': setCookie('token', token, { secure: isSecure, maxAge: 28800 })
      })
    }

    // ─── LOGOUT ──────────────────────────────────────────────────────────
    if (route === 'logout' && httpMethod === 'POST') {
      if (user) await audit(user.id, 'LOGOUT', 'user', String(user.id), `Logout: ${user.username}`)
      return json({ ok: true }, 200, {
        'Set-Cookie': 'token=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'
      })
    }

    // ─── FORGOT PASSWORD ────────────────────────────────────────────────
    if (route === 'forgot-password' && httpMethod === 'POST') {
      const clientIp = headers['x-forwarded-for'] || headers['client-ip'] || 'unknown'
      if (!checkForgotPasswordRateLimit(clientIp)) {
        return json({ ok: false, erro: 'Muitas tentativas. Aguarde 1 minuto.' }, 429)
      }
      const { username } = body
      if (!username) return json({ ok: false, erro: 'Informe o nome de usuario.' }, 400)
      const { data: dbUser } = await getSupabase().from('users').select('*').eq('username', username).single()
      if (!dbUser) return json({ ok: true, msg: 'Se o usuario existir, um email sera enviado.' })
      const token = crypto.randomBytes(32).toString('hex')
      const expiresAt = new Date(Date.now() + 60 * 60 * 1000).toISOString()
      await getSupabase().from('password_resets').insert({
        user_id: dbUser.id, token, expires_at: expiresAt
      })
      const cfg = await getEmailConfig()
      const emailTo = dbUser.email || cfg.email_remetente
      if (cfg.email_remetente && cfg.email_senha && emailTo) {
        const resetUrl = `https://${headers.host || 'contratosidealalimentacao.netlify.app'}/?reset_token=${token}`
        const html = `<h2>Redefinicao de Senha</h2><p>Ola ${escapeHtml(dbUser.full_name)},</p><p>Clique no link abaixo para redefinir sua senha:</p><p><a href="${resetUrl}">${resetUrl}</a></p><p>Este link expira em 1 hora.</p><p>Se voce nao solicitou esta redefinicao, ignore este email.</p>`
        try { await enviarEmail(cfg, html, 'Redefinicao de Senha - Controle de Contratos', emailTo) } catch {}
      }
      return json({ ok: true, msg: 'Se o usuario existir, um email sera enviado.' })
    }

    // ─── RESET PASSWORD ─────────────────────────────────────────────────
    if (route === 'reset-password' && httpMethod === 'POST') {
      const { token, password } = body
      if (!token || !password) return json({ ok: false, erro: 'Token e nova senha sao obrigatorios.' }, 400)
      if (password.length < 8) return json({ ok: false, erro: 'A senha deve ter no minimo 8 caracteres.' }, 400)
      if (!/[A-Z]/.test(password)) return json({ ok: false, erro: 'Senha deve conter pelo menos 1 letra maiuscula.' }, 400)
      if (!/[a-z]/.test(password)) return json({ ok: false, erro: 'Senha deve conter pelo menos 1 letra minuscula.' }, 400)
      if (!/[0-9]/.test(password)) return json({ ok: false, erro: 'Senha deve conter pelo menos 1 numero.' }, 400)
      const now = new Date().toISOString()
      const { data: reset } = await getSupabase().from('password_resets')
        .select('*').eq('token', token).eq('used', 0).single()
      if (!reset) return json({ ok: false, erro: 'Token invalido ou ja utilizado.' }, 400)
      if (reset.expires_at < now) return json({ ok: false, erro: 'Token expirado. Solicite uma nova redefinicao.' }, 400)
      const hash = await hashPassword(password)
      await getSupabase().from('users').update({ password_hash: hash }).eq('id', reset.user_id)
      await getSupabase().from('password_resets').update({ used: 1 }).eq('id', reset.id)
      return json({ ok: true, msg: 'Senha redefinida com sucesso!' })
    }

    // ─── CHANGE PASSWORD (MINHA CONTA) ────────────────────────────────
    if (route === 'change-password' && httpMethod === 'POST') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const { current_password, new_password } = body
      if (!current_password || !new_password) return json({ ok: false, erro: 'Senha atual e nova senha sao obrigatorios.' }, 400)
      if (new_password.length < 8) return json({ ok: false, erro: 'A nova senha deve ter no minimo 8 caracteres.' }, 400)
      if (!/[A-Z]/.test(new_password) || !/[a-z]/.test(new_password) || !/[0-9]/.test(new_password)) {
        return json({ ok: false, erro: 'A nova senha deve conter pelo menos 1 maiuscula, 1 minuscula e 1 numero.' }, 400)
      }
      const { data: dbUser } = await getSupabase().from('users').select('id, password_hash').eq('id', user.id).single()
      if (!dbUser) return json({ ok: false, erro: 'Usuario nao encontrado.' }, 404)
      const valid = await checkPassword(current_password, dbUser.password_hash)
      if (!valid) return json({ ok: false, erro: 'Senha atual incorreta.' }, 400)
      const hash = await hashPassword(new_password)
      const { error } = await getSupabase().from('users').update({ password_hash: hash }).eq('id', user.id)
      if (error) return json({ ok: false, erro: error.message }, 500)
      await audit(user.id, 'UPDATE', 'user', user.id, 'Senha alterada')
      return json({ ok: true, msg: 'Senha alterada com sucesso!' })
    }

    // ─── CONFIG-EMAIL ────────────────────────────────────────────────────
    if (route === 'config-email') {
      if (httpMethod === 'GET') {
        const cfg = await getEmailConfig()
        cfg.email_senha = '********'
        return json(cfg)
      }
      if (httpMethod === 'POST') {
        const authErr = requireAuth(user)
        if (authErr) return authErr
        if (!validateCsrf(user, body.csrf_token)) {
          return json({ ok: false, erro: 'CSRF invalido' }, 403)
        }
        const { data: oldCfg } = await getSupabase().from('email_config').select('*').eq('id', 1).single()
        if (body.email_senha === '********' || !body.email_senha?.trim()) {
          body.email_senha = oldCfg?.email_senha_enc ? '********' : ''
          body.email_senha_enc = oldCfg?.email_senha_enc || ''
        }
        await saveEmailConfig(body)
        return json({ ok: true })
      }
    }

    // ─── ENVIAR LEMBRETE PAGAMENTOS ──────────────────────────────────────
    if (route === 'enviar-lembrete' || route === 'enviar-lembrete-pagamentos') {
      if (httpMethod !== 'POST') return json({ ok: false, erro: 'Metodo nao permitido' }, 405)
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const cfg = await getEmailConfig()
      if (!cfg.email_remetente || !cfg.email_senha) {
        return json({ ok: false, erro: 'Configure o e-mail primeiro.' })
      }
      const empresasLista = body.empresas || []
      const empresaNomes = {}
      for (const e of empresasLista) { if (e.id && e.nome) empresaNomes[e.id] = e.nome }
      const destinatariosData = body.destinatarios || []
      if (!destinatariosData.length) {
        return json({ ok: true, msg: 'Nenhum destinatario cadastrado para enviar lembretes.' })
      }
      const { data: contratos } = await getSupabase().from('contracts').select('*')
      const { data: pagamentos } = await getSupabase().from('payments').select('*')
      const hj = today()

      let enviados = 0, erros = []
      for (const dest of destinatariosData) {
        const email = (dest.email || '').trim()
        if (!email) continue
        const empresaIds = dest.empresaIds || []
        const empIdsSet = empresaIds.length ? new Set(empresaIds) : null
        const contratoIdsEmp = new Set(contratos.filter(c => !empIdsSet || empIdsSet.has(c.empresa_id)).map(c => c.id))
        const empPagamentos = pagamentos.filter(p => contratoIdsEmp.has(p.contract_id))
        const [vencidos, venceHoje, venceAmanha] = processPayments(contratos, empPagamentos, hj, empresaNomes)
        if (!vencidos.length && !venceHoje.length && !venceAmanha.length) continue
        const rotulo = dest.nome ? ` - ${dest.nome}` : ''
        const htmlBody = `<html><body style="font-family:Arial,sans-serif;padding:20px">${montarHtmlPagamentos(vencidos, venceHoje, venceAmanha, rotulo)}<p style="color:#666;font-size:12px">Gerado em ${new Date().toLocaleString('pt-BR')}</p></body></html>`
        try {
          await enviarEmail(cfg, htmlBody, `Lembrete de Pagamentos${rotulo} - ${hj}`, email)
          enviados++
        } catch (e) {
          erros.push(`${email}: ${e.message}`)
        }
      }
      if (!enviados && !erros.length) return json({ ok: true, msg: 'Nenhum pagamento pendente para os destinatarios cadastrados.' })
      return json({ ok: true, msg: `${enviados} e-mail(s) enviado(s).${erros.length ? ` Erros: ${erros.join('; ')}` : ''}` })
    }

    // ─── ENVIAR ALERTAS CONTRATOS ────────────────────────────────────────
    if (route === 'enviar-alertas-contratos') {
      if (httpMethod !== 'POST') return json({ ok: false, erro: 'Metodo nao permitido' }, 405)
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const cfg = await getEmailConfig()
      if (!cfg.email_remetente || !cfg.email_senha) {
        return json({ ok: false, erro: 'Configure o e-mail primeiro.' })
      }
      const destinatariosData = body.destinatarios || []
      if (!destinatariosData.length) {
        return json({ ok: true, msg: 'Nenhum destinatario cadastrado para enviar alertas.' })
      }
      const { data: contratos } = await getSupabase().from('contracts').select('*')
      const hj = today()

      let enviados = 0, erros = []
      for (const dest of destinatariosData) {
        const email = (dest.email || '').trim()
        if (!email) continue
        const empresaIds = dest.empresaIds || []
        const empIdsSet = empresaIds.length ? new Set(empresaIds) : null
        const empContratos = contratos.filter(c => !empIdsSet || empIdsSet.has(c.empresa_id))
        const vencidos = processContratosVencidos(empContratos, hj)
        const grupos = processContratosAVencer(empContratos, hj)
        if (!vencidos.length && !Object.values(grupos).some(g => g.length)) continue
        const rotulo = dest.nome ? ` - ${dest.nome}` : ''
        const htmlBody = `<html><body style="font-family:Arial,sans-serif;padding:20px">${montarHtmlContratos(vencidos, grupos, rotulo)}<p style="color:#666;font-size:12px">Gerado em ${new Date().toLocaleString('pt-BR')}</p></body></html>`
        try {
          await enviarEmail(cfg, htmlBody, `Alertas de Contratos${rotulo} - ${hj}`, email)
          enviados++
        } catch (e) {
          erros.push(`${email}: ${e.message}`)
        }
      }
      if (!enviados && !erros.length) return json({ ok: true, msg: 'Nenhum contrato pendente para os destinatarios cadastrados.' })
      return json({ ok: true, msg: `${enviados} e-mail(s) enviado(s).${erros.length ? ` Erros: ${erros.join('; ')}` : ''}` })
    }

    // ─── USERS ───────────────────────────────────────────────────────────
    if (route === 'users' && httpMethod === 'GET') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      const { data: users } = await getSupabase().from('users').select('id, username, full_name, role, active, created_at').order('id')
      return json(users)
    }

    if (route === 'users' && httpMethod === 'POST') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const username = (body.username || '').trim()
      const fullName = (body.full_name || '').trim()
      const email = (body.email || '').trim()
      const password = (body.password || '').trim()
      const role = (body.role || 'user').trim()
      if (!username || !fullName || !password) {
        return json({ ok: false, erro: 'Preencha todos os campos' }, 400)
      }
      if (email && !/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(email)) {
        return json({ ok: false, erro: 'Email invalido' }, 400)
      }
      if (password.length < 8) return json({ ok: false, erro: 'Senha deve ter no minimo 8 caracteres.' }, 400)
      if (!/[A-Z]/.test(password)) return json({ ok: false, erro: 'Senha deve conter pelo menos 1 letra maiuscula.' }, 400)
      if (!/[a-z]/.test(password)) return json({ ok: false, erro: 'Senha deve conter pelo menos 1 letra minuscula.' }, 400)
      if (!/[0-9]/.test(password)) return json({ ok: false, erro: 'Senha deve conter pelo menos 1 numero.' }, 400)
      const { data: existing } = await getSupabase().from('users').select('id').eq('username', username).single()
      if (existing) return json({ ok: false, erro: 'Usuario ja existe' }, 400)
      const hash = await hashPassword(password)
      const { data: newUser, error: insertErr } = await getSupabase().from('users').insert({
        username, full_name: fullName, email, password_hash: hash, role
      }).select().single()
      if (insertErr) return json({ ok: false, erro: 'Erro ao criar usuario: ' + insertErr.message }, 500)
      if (!newUser) return json({ ok: false, erro: 'Erro ao criar usuario' }, 500)
      await audit(user.id, 'CREATE', 'user', '', `Usuario ${username} criado por ${user.username}`)
      return json({ ok: true, user: { id: newUser.id } })
    }

    if (parts[0] === 'users' && parts[1] && httpMethod === 'PUT') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const uid = parseInt(parts[1])
      const fullName = (body.full_name || '').trim()
      const email = (body.email || '').trim()
      const role = (body.role || 'user').trim()
      const active = body.active !== false ? 1 : 0
      if (email && !/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(email)) {
        return json({ ok: false, erro: 'Email invalido' }, 400)
      }
      const upd = { full_name: fullName, email, role, active }
      if (body.password && body.password.trim()) {
        const pwd = body.password.trim()
        if (pwd.length < 8) return json({ ok: false, erro: 'Senha deve ter no minimo 8 caracteres.' }, 400)
        if (!/[A-Z]/.test(pwd)) return json({ ok: false, erro: 'Senha deve conter pelo menos 1 letra maiuscula.' }, 400)
        if (!/[a-z]/.test(pwd)) return json({ ok: false, erro: 'Senha deve conter pelo menos 1 letra minuscula.' }, 400)
        if (!/[0-9]/.test(pwd)) return json({ ok: false, erro: 'Senha deve conter pelo menos 1 numero.' }, 400)
        upd.password_hash = await hashPassword(pwd)
      }
      await getSupabase().from('users').update(upd).eq('id', uid)
      await audit(user.id, 'UPDATE', 'user', String(uid), `Usuario ${uid} atualizado por ${user.username}`)
      return json({ ok: true })
    }

    if (parts[0] === 'users' && parts[1] && httpMethod === 'DELETE') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const uid = parseInt(parts[1])
      if (uid === 1) return json({ ok: false, erro: 'Nao e possivel inativar o usuario admin principal.' }, 400)
      await getSupabase().from('users').update({ active: 0 }).eq('id', uid)
      await audit(user.id, 'INACTIVATE', 'user', String(uid), `Usuario ${uid} inativado por ${user.username}`)
      return json({ ok: true })
    }

    // ─── COMPANIES ───────────────────────────────────────────────────────
    if (route === 'companies' && httpMethod === 'GET') {
      const { data } = await getSupabase().from('companies').select('*').order('nome')
      return json(data)
    }

    if (route === 'companies' && httpMethod === 'POST') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const cid = body.id || crypto.randomUUID()
      const nome = (body.nome || '').trim()
      if (!nome) return json({ ok: false, erro: 'Nome da empresa e obrigatorio.' }, 400)
      const cnpj = (body.cnpj || '').trim()
      const { data: existing } = await getSupabase().from('companies').select('id').eq('id', cid).single()
      const active = body.active !== undefined ? (body.active ? 1 : 0) : 1
      if (existing) {
        await getSupabase().from('companies').update({ nome, cnpj, active }).eq('id', cid)
      } else {
        await getSupabase().from('companies').insert({ id: cid, nome, cnpj, active })
      }
      return json({ ok: true, id: cid })
    }

    if (parts[0] === 'companies' && parts[1] && httpMethod === 'PUT') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const upd = {}
      if (body.active !== undefined) upd.active = body.active ? 1 : 0
      if (body.nome !== undefined) upd.nome = (body.nome || '').trim()
      if (body.cnpj !== undefined) upd.cnpj = (body.cnpj || '').trim()
      await getSupabase().from('companies').update(upd).eq('id', parts[1])
      return json({ ok: true })
    }

    if (parts[0] === 'companies' && parts[1] && httpMethod === 'DELETE') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      await getSupabase().from('companies').delete().eq('id', parts[1])
      return json({ ok: true })
    }

    // ─── SECTORS ────────────────────────────────────────────────────────
    if (route === 'sectors' && httpMethod === 'GET') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const { data } = await getSupabase().from('sectors').select('*').order('nome')
      return json(data || [])
    }

    if (route === 'sectors' && httpMethod === 'POST') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireGlobalAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const sid = body.id || crypto.randomUUID()
      const nome = (body.nome || '').trim()
      if (!nome) return json({ ok: false, erro: 'Nome do setor e obrigatorio' }, 400)
      const active = body.active !== undefined ? (body.active ? 1 : 0) : 1
      const { data: existing } = await getSupabase().from('sectors').select('id').eq('id', sid).single()
      if (existing) {
        await getSupabase().from('sectors').update({ nome, active }).eq('id', sid)
      } else {
        await getSupabase().from('sectors').insert({ id: sid, nome, active })
      }
      return json({ ok: true, id: sid })
    }

    if (parts[0] === 'sectors' && parts[1] && httpMethod === 'PUT') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireGlobalAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const upd = {}
      if (body.nome !== undefined) upd.nome = (body.nome || '').trim()
      if (body.active !== undefined) upd.active = body.active ? 1 : 0
      await getSupabase().from('sectors').update(upd).eq('id', parts[1])
      return json({ ok: true })
    }

    if (parts[0] === 'sectors' && parts[1] && httpMethod === 'DELETE') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireGlobalAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      await getSupabase().from('sectors').delete().eq('id', parts[1])
      await getSupabase().from('user_setores').delete().eq('setor_id', parts[1])
      return json({ ok: true })
    }

    // ─── USER_SETORES / USER_EMPRESAS ──────────────────────────────────
    if (route === 'user-setores' && httpMethod === 'GET') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const userId = parseInt(user.id)
      const { data } = await getSupabase().from('user_setores').select('*').eq('user_id', userId)
      return json(data || [])
    }

    if (route === 'user-setores' && httpMethod === 'POST') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const userId = parseInt(body.user_id)
      const setorIds = body.setor_ids || []
      if (!userId) return json({ ok: false, erro: 'user_id obrigatorio' }, 400)
      await getSupabase().from('user_setores').delete().eq('user_id', userId)
      for (const setorId of setorIds) {
        await getSupabase().from('user_setores').insert({ user_id: userId, setor_id: setorId })
      }
      return json({ ok: true })
    }

    if (route === 'user-empresas' && httpMethod === 'GET') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const userId = parseInt(user.id)
      const { data } = await getSupabase().from('user_empresas').select('*').eq('user_id', userId)
      return json(data || [])
    }

    if (route === 'user-empresas' && httpMethod === 'POST') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const userId = parseInt(body.user_id)
      const empresaIds = body.empresa_ids || []
      if (!userId) return json({ ok: false, erro: 'user_id obrigatorio' }, 400)
      await getSupabase().from('user_empresas').delete().eq('user_id', userId)
      for (const empresaId of empresaIds) {
        await getSupabase().from('user_empresas').insert({ user_id: userId, empresa_id: empresaId })
      }
      return json({ ok: true })
    }

    // ─── CONTRACTS PUT ───────────────────────────────────────────────────
    if (parts[0] === 'contracts' && parts[1] && httpMethod === 'PUT') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const upd = {}
      if (body.active !== undefined) upd.active = body.active ? 1 : 0
      upd.updated_at = new Date().toISOString()
      await getSupabase().from('contracts').update(upd).eq('id', parts[1])
      return json({ ok: true })
    }

    // ─── CONTRACTS DELETE ────────────────────────────────────────────────
    if (parts[0] === 'contracts' && parts[1] && httpMethod === 'DELETE') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      await getSupabase().from('payments').delete().eq('contract_id', parts[1])
      await getSupabase().from('additives').delete().eq('contract_id', parts[1])
      await getSupabase().from('contracts').delete().eq('id', parts[1])
      await audit(user.id, 'DELETE', 'contract', parts[1], `Contrato ${parts[1]} excluido por ${user.username}`)
      return json({ ok: true })
    }

    // ─── PAYMENTS DELETE ─────────────────────────────────────────────────
    if (parts[0] === 'payments' && parts[1] && httpMethod === 'DELETE') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      await getSupabase().from('payments').delete().eq('id', parts[1])
      await audit(user.id, 'DELETE', 'payment', parts[1], `Pagamento ${parts[1]} excluido por ${user.username}`)
      return json({ ok: true })
    }

    // ─── SYNC ────────────────────────────────────────────────────────────
    if (route === 'sync') {
      if (httpMethod === 'GET') {
        const authErr = requireAuth(user)
        if (authErr) return authErr
        const since = queryParams.since || null
        const sq = (tbl) => {
          let q = getSupabase().from(tbl).select('*')
          if (since) {
            q = q.gt('updated_at', since)
          } else {
            q = q.is('deleted_at', null)
          }
          return q
        }
        const sqContracts = () => {
          let q = getSupabase().from('contracts').select('*')
          if (since) {
            q = q.gt('updated_at', since)
          } else {
            q = q.eq('active', 1)
          }
          return q
        }
        const [contratos, pagamentos, usuarios, aditivos, empresas, destinatarios, certidoes, licitacoes, sectors, userSetores] = await Promise.all([
          sqContracts().order('created_at', { ascending: false }),
          sq('payments').order('vencimento'),
          getSupabase().from('users').select('id, username, full_name, role, created_at').order('id'),
          sq('additives').order('created_at'),
          getSupabase().from('companies').select('*').order('nome'),
          sq('destinatarios').order('criado_em'),
          sq('certidoes').order('criado_em', { ascending: false }),
          sq('licitacoes').order('criado_em', { ascending: false }),
          getSupabase().from('sectors').select('*').order('nome'),
          getSupabase().from('user_setores').select('*'),
        ])
        return json({
          contratos: contratos.data || [],
          pagamentos: pagamentos.data || [],
          usuarios: usuarios.data || [],
          aditivos: aditivos.data || [],
          empresas: empresas.data || [],
          destinatarios: destinatarios.data || [],
          certidoes: certidoes.data || [],
          licitacoes: licitacoes.data || [],
          sectors: sectors.data || [],
          user_setores: userSetores.data || [],
          server_now: new Date().toISOString()
        })
      }

      if (httpMethod === 'POST') {
        const authErr = requireAuth(user)
        if (authErr) return authErr
        if (!validateCsrf(user, body.csrf_token)) {
          return json({ ok: false, erro: 'CSRF invalido' }, 403)
        }
        if (!body) return json({ ok: false, erro: 'JSON invalido ou vazio.' }, 400)
        const importados = { contratos: 0, pagamentos: 0, aditivos: 0, ignorados: 0 }
        const MAX_BASE64 = 15 * 1024 * 1024

        for (const c of (body.contratos || [])) {
          const cid = (c.id || '').trim()
          const numero = (c.numero || '').trim()
          if (!cid || !numero) { importados.ignorados++; continue }
          if (c.arquivo?.data?.length > MAX_BASE64) {
            console.warn(`[SYNC] Arquivo do contrato ${numero} excede 10MB, ignorando arquivo.`)
            c.arquivo = null
          }
          const cnpjVal = (c.doc || '').trim()
          if (cnpjVal && !validarCpfCnpj(cnpjVal)) {
            console.warn(`[SYNC] CPF/CNPJ invalido no contrato ${numero}: ${cnpjVal}, ignorando CNPJ.`)
            c.doc = ''
          }
          try {
            const pgto = c.pgtoConfig || {}
            const arquivoJson = c.arquivo ? JSON.stringify(c.arquivo) : null
            const incomingUpdated = c.updated_at || c.createdAt || new Date().toISOString()
            const incomingDeleted = c.deleted_at || null
            const { data: existing } = await getSupabase().from('contracts').select('id, updated_at').eq('id', cid).single()
            if (existing) {
              const existingUpdated = existing.updated_at || ''
              if (incomingUpdated <= existingUpdated && !incomingDeleted) {
                importados.contratos++
                if (c.aditivos?.length) { for (const a of c.aditivos) importados.aditivos++ }
                continue
              }
              if (incomingDeleted) {
                await getSupabase().from('contracts').update({ active: 0, updated_at: incomingUpdated }).eq('id', cid)
              } else {
                const vals = {
                  numero, fornecedor: (c.parte || '').trim(), cnpj: (c.doc || '').trim(),
                  objeto: (c.objeto || '').trim(), valor_total: parseFloat(c.valor || 0),
                  inicio: (c.inicio || '').trim(), fim: (c.fim || '').trim(),
                  tem_parcelas: c.temParcelas ? 1 : 0, qtd_parcelas: pgto.qtdParcelas,
                  valor_parcela: safeFloat(pgto.valorParcela), dia_vencimento: pgto.diaVenc,
                  responsavel: (c.responsavel || '').trim(), setor: (c.setor || '').trim(),
                  obs: (c.obs || '').trim(), tipo: c.tipo, empresa_id: c.empresaId,
                  active: c.active !== undefined ? (c.active ? 1 : 0) : 1,
                  forma_pagamento: pgto.forma, arquivo_contrato: arquivoJson,
                  updated_at: incomingUpdated
                }
                const { error } = await getSupabase().from('contracts').update(vals).eq('id', cid)
                if (error) { await audit(user.id, 'SYNC_ERROR', 'contracts', cid, `Update: ${error.message}`); importados.ignorados++; continue }
              }
            } else {
              if (incomingDeleted) { importados.contratos++; continue }
              const vals = {
                numero, fornecedor: (c.parte || '').trim(), cnpj: (c.doc || '').trim(),
                objeto: (c.objeto || '').trim(), valor_total: parseFloat(c.valor || 0),
                inicio: (c.inicio || '').trim(), fim: (c.fim || '').trim(),
                tem_parcelas: c.temParcelas ? 1 : 0, qtd_parcelas: pgto.qtdParcelas,
                valor_parcela: safeFloat(pgto.valorParcela), dia_vencimento: pgto.diaVenc,
                responsavel: (c.responsavel || '').trim(), setor: (c.setor || '').trim(),
                obs: (c.obs || '').trim(), tipo: c.tipo, empresa_id: c.empresaId,
                active: c.active !== undefined ? (c.active ? 1 : 0) : 1,
                forma_pagamento: pgto.forma, arquivo_contrato: arquivoJson,
                created_by: user.id, updated_at: incomingUpdated
              }
              const { error } = await getSupabase().from('contracts').insert({ id: cid, ...vals })
              if (error) { await audit(user.id, 'SYNC_ERROR', 'contracts', cid, `Insert: ${error.message}`); importados.ignorados++; continue }
            }
            importados.contratos++

          if (c.aditivos?.length) {
            for (const a of c.aditivos) {
              const aid = (a.id || '').trim()
              if (!aid) { importados.ignorados++; continue }
              if (a.arquivo?.data?.length > MAX_BASE64) {
                console.warn('[SYNC] Arquivo de aditivo excede 15MB, ignorando arquivo.')
                a.arquivo = null
              }
              try {
                const arqJson = a.arquivo ? JSON.stringify(a.arquivo) : null
                const incomingUpdatedA = a.updated_at || a.createdAt || new Date().toISOString()
                const incomingDeletedA = a.deleted_at || null
                const { data: existingA } = await getSupabase().from('additives').select('id, updated_at').eq('id', aid).single()
                if (existingA) {
                  const existingUpdatedA = existingA.updated_at || ''
                  if (incomingUpdatedA <= existingUpdatedA && !incomingDeletedA) {
                    importados.aditivos++
                    continue
                  }
                  if (incomingDeletedA) {
                    await getSupabase().from('additives').delete().eq('id', aid)
                  } else {
                    const { error } = await getSupabase().from('additives').update({
                      numero: a.numero, data_aditivo: a.data || '', tipo: a.tipo,
                      nova_data_fim: a.novaData, acrescimo_valor: a.novoValor,
                      descricao: a.objeto || '', arquivo_contrato: arqJson,
                      updated_at: incomingUpdatedA
                    }).eq('id', aid)
                    if (error) { await audit(user.id, 'SYNC_ERROR', 'additives', aid, error.message); importados.ignorados++; continue }
                  }
                } else {
                  if (incomingDeletedA) { importados.aditivos++; continue }
                  const { error } = await getSupabase().from('additives').insert({
                    id: aid, contract_id: cid, numero: a.numero,
                    data_aditivo: a.data || '', tipo: a.tipo, nova_data_fim: a.novaData,
                    acrescimo_valor: a.novoValor, descricao: a.objeto || '',
                    arquivo_contrato: arqJson, created_by: user.id,
                    updated_at: incomingUpdatedA
                  })
                  if (error) { await audit(user.id, 'SYNC_ERROR', 'additives', aid, error.message); importados.ignorados++; continue }
                }
                importados.aditivos++
              } catch (e) {
                await audit(user.id, 'SYNC_ERROR', 'additives', aid, e.message)
                importados.ignorados++
              }
            }
          }
          } catch (e) {
            await audit(user.id, 'SYNC_ERROR', 'contracts', cid, e.message)
            importados.ignorados++
          }
        }

        const pagDados = body.pagamentos || []
        for (const p of pagDados) {
          const pid = (p.id || '').trim() || crypto.randomUUID()
          const cid = (p.contratoId || '').trim()
          const descricao = (p.descricao || '').trim()
          const vencimento = (p.vencimento || '').trim()
          if (!cid || !vencimento) { importados.ignorados++; continue }
          if (p.comprovante?.data?.length > MAX_BASE64) {
            console.warn('[SYNC] Comprovante de pagamento excede 15MB, ignorando comprovante.')
            p.comprovante = null
          }
          try {
            const valor = parseFloat(p.valor || 0)
            const dataPag = (p.dataPagamento || '').trim() || null
            const comprovanteJson = p.comprovante ? JSON.stringify(p.comprovante) : null
            const incomingUpdated = p.updated_at || p.createdAt || new Date().toISOString()
            const incomingDeleted = p.deleted_at || null
            const { data: existing } = await getSupabase().from('payments').select('id, updated_at, deleted_at').eq('id', pid).single()
            if (existing) {
              const existingUpdated = existing.updated_at || ''
              if (incomingUpdated <= existingUpdated && !incomingDeleted) {
                importados.pagamentos++
                continue
              }
              if (incomingDeleted) {
                await getSupabase().from('payments').delete().eq('id', pid)
              } else {
                const vals = {
                  contract_id: cid, descricao, vencimento, valor,
                  contrato_num: (p.contratoNum || '').trim() || null,
                  data_pagamento: dataPag, valor_pago: safeFloat(p.valorPago) || (dataPag ? valor : null),
                  forma_pagamento: (p.formaPgto || '').trim() || null,
                  status: dataPag ? 'pago' : 'pendente', obs: (p.obs || '').trim(),
                  comprovante: comprovanteJson, updated_at: incomingUpdated
                }
                const { error } = await getSupabase().from('payments').update(vals).eq('id', pid)
                if (error) { await audit(user.id, 'SYNC_ERROR', 'payments', pid, error.message); importados.ignorados++; continue }
              }
            } else {
              if (incomingDeleted) { importados.pagamentos++; continue }
              const { error } = await getSupabase().from('payments').insert({
                id: pid, contract_id: cid, descricao, vencimento, valor,
                contrato_num: (p.contratoNum || '').trim() || null,
                data_pagamento: dataPag, valor_pago: safeFloat(p.valorPago) || (dataPag ? valor : null),
                forma_pagamento: (p.formaPgto || '').trim() || null,
                status: dataPag ? 'pago' : 'pendente', obs: (p.obs || '').trim(),
                comprovante: comprovanteJson, created_by: user.id,
                updated_at: incomingUpdated
              })
              if (error) { await audit(user.id, 'SYNC_ERROR', 'payments', pid, error.message); importados.ignorados++; continue }
            }
            importados.pagamentos++
          } catch (e) {
            await audit(user.id, 'SYNC_ERROR', 'payments', pid, e.message)
            importados.ignorados++
          }
        }

        for (const d of (body.destinatarios || [])) {
          const did = (d.id || '').trim()
          const email = (d.email || '').trim()
          if (!did || !email) { importados.ignorados++; continue }
          try {
            const incomingUpdatedD = d.updated_at || d.criadoEm || new Date().toISOString()
            const incomingDeletedD = d.deleted_at || null
            const { data: existing } = await getSupabase().from('destinatarios').select('id, updated_at').eq('id', did).single()
            if (existing) {
              const existingUpdatedD = existing.updated_at || ''
              if (incomingUpdatedD <= existingUpdatedD && !incomingDeletedD) {
                importados.destinatarios = (importados.destinatarios || 0) + 1
                continue
              }
              if (incomingDeletedD) {
                await getSupabase().from('destinatarios').delete().eq('id', did)
              } else {
                const { error } = await getSupabase().from('destinatarios').update({
                  email, nome: (d.nome || '').trim(),
                  empresa_ids: JSON.stringify(d.empresaIds || []),
                  setores: JSON.stringify(d.setores || []),
                  alertas: JSON.stringify(d.alertas || []),
                  updated_at: incomingUpdatedD
                }).eq('id', did)
                if (error) { await audit(user.id, 'SYNC_ERROR', 'destinatarios', did, error.message); importados.ignorados++; continue }
              }
            } else {
              if (incomingDeletedD) { importados.destinatarios = (importados.destinatarios || 0) + 1; continue }
              const { error } = await getSupabase().from('destinatarios').insert({
                id: did, email, nome: (d.nome || '').trim(),
                empresa_ids: JSON.stringify(d.empresaIds || []),
                setores: JSON.stringify(d.setores || []),
                alertas: JSON.stringify(d.alertas || []),
                updated_at: incomingUpdatedD
              })
              if (error) { await audit(user.id, 'SYNC_ERROR', 'destinatarios', did, error.message); importados.ignorados++; continue }
            }
            importados.destinatarios = (importados.destinatarios || 0) + 1
          } catch (e) {
            await audit(user.id, 'SYNC_ERROR', 'destinatarios', did, e.message)
            importados.ignorados++
          }
        }

        for (const ct of (body.certidoes || [])) {
          const ctid = (ct.id || '').trim()
          const tipo = (ct.tipo || '').trim()
          if (!ctid || !tipo) { importados.ignorados++; continue }
          try {
            let arquivoDadosStr = null
            let arquivoNomeStr = ''
            if (ct.arquivo) {
              const tmp = JSON.stringify(ct.arquivo)
              if (tmp.length <= MAX_BASE64) {
                arquivoDadosStr = tmp
                arquivoNomeStr = ct.arquivo.name || ''
              }
            }
            const incomingUpdatedCt = ct.updated_at || ct.criadoEm || new Date().toISOString()
            const incomingDeletedCt = ct.deleted_at || null
            const { data: existing } = await getSupabase().from('certidoes').select('id, updated_at').eq('id', ctid).single()
            const vals = {
              empresa_id: ct.empresaId || '',
              cnpj: (ct.cnpj || '').trim(),
              uf: (ct.uf || '').trim(),
              cidade: (ct.cidade || '').trim(),
              tipo, data_emissao: ct.dataEmissao || '',
              data_validade: ct.dataValidade || '', status: ct.status || 'pendente',
              arquivo_nome: arquivoNomeStr,
              arquivo_dados: arquivoDadosStr,
              observacoes: (ct.obs || '').trim(),
              updated_at: incomingUpdatedCt
            }
            if (existing) {
              const existingUpdatedCt = existing.updated_at || ''
              if (incomingUpdatedCt <= existingUpdatedCt && !incomingDeletedCt) {
                importados.certidoes = (importados.certidoes || 0) + 1
                continue
              }
              if (incomingDeletedCt) {
                await getSupabase().from('certidoes').delete().eq('id', ctid)
              } else {
                const { error } = await getSupabase().from('certidoes').update(vals).eq('id', ctid)
                if (error) { await audit(user.id, 'SYNC_ERROR', 'certidoes', ctid, `Update: ${error.message}`); importados.ignorados++; continue }
              }
            } else {
              if (incomingDeletedCt) { importados.certidoes = (importados.certidoes || 0) + 1; continue }
              const { error } = await getSupabase().from('certidoes').insert({ id: ctid, ...vals })
              if (error) { await audit(user.id, 'SYNC_ERROR', 'certidoes', ctid, `Insert: ${error.message}`); importados.ignorados++; continue }
            }
            importados.certidoes = (importados.certidoes || 0) + 1
          } catch (e) {
            await audit(user.id, 'SYNC_ERROR', 'certidoes', ctid, e.message)
            importados.ignorados++
          }
        }

        for (const lc of (body.licitacoes || [])) {
          const lcid = (lc.id || '').trim()
          const numero = (lc.numeroLicitacao || '').trim()
          if (!lcid || !numero) { importados.ignorados++; continue }
          try {
            const incomingUpdatedLc = lc.updated_at || lc.criadoEm || new Date().toISOString()
            const incomingDeletedLc = lc.deleted_at || null
            const { data: existing } = await getSupabase().from('licitacoes').select('id, updated_at').eq('id', lcid).single()
            const arquivos = []
            if (lc.arquivoEdital) arquivos.push({ ...lc.arquivoEdital, tipo: 'edital' })
            if (lc.arquivoContrato) arquivos.push({ ...lc.arquivoContrato, tipo: 'contrato' })
            const vals = {
              numero_licitacao: numero, edital: (lc.edital || '').trim(),
              objeto: (lc.objeto || '').trim(), empresa_id: lc.empresaId || '',
              contrato_id: lc.contratoId || '', valor: safeFloat(lc.valor),
              data_homologacao: lc.dataHomologacao || '',
              data_inicio: lc.dataInicio || '', data_fim: lc.dataFim || '',
              status: lc.status || 'em_andamento',
              arquivos: JSON.stringify(arquivos),
              observacoes: (lc.obs || '').trim(),
              updated_at: incomingUpdatedLc
            }
            if (existing) {
              const existingUpdatedLc = existing.updated_at || ''
              if (incomingUpdatedLc <= existingUpdatedLc && !incomingDeletedLc) {
                importados.licitacoes = (importados.licitacoes || 0) + 1
                continue
              }
              if (incomingDeletedLc) {
                await getSupabase().from('licitacoes').delete().eq('id', lcid)
              } else {
                const { error } = await getSupabase().from('licitacoes').update(vals).eq('id', lcid)
                if (error) { await audit(user.id, 'SYNC_ERROR', 'licitacoes', lcid, error.message); importados.ignorados++; continue }
              }
            } else {
              if (incomingDeletedLc) { importados.licitacoes = (importados.licitacoes || 0) + 1; continue }
              const { error } = await getSupabase().from('licitacoes').insert({ id: lcid, ...vals })
              if (error) { await audit(user.id, 'SYNC_ERROR', 'licitacoes', lcid, error.message); importados.ignorados++; continue }
            }
            importados.licitacoes = (importados.licitacoes || 0) + 1
          } catch (e) {
            await audit(user.id, 'SYNC_ERROR', 'licitacoes', lcid, e.message)
            importados.ignorados++
          }
        }

        await audit(user.id, 'SYNC', 'system', '', `Sincronizacao concluida: ${JSON.stringify(importados)}`)
        return json({ ok: true, importados })
      }
    }

    // ─── ASSISTENTE VIRTUAL ─────────────────────────────────────────────────
    if (route === 'assistente' && httpMethod === 'POST') {
      const pergunta = (body.pergunta || '').trim()
      if (!pergunta) return json({ ok: false, erro: 'Pergunta vazia' }, 400)

      const geminiKey = process.env.GEMINI_API_KEY || ''
      if (!geminiKey) {
        return json({ ok: true, resposta: respostaOffline(pergunta) })
      }

      try {
        const prompt = SYSTEM_PROMPT_ASSISTENTE + '\n\nPERGUNTA DO USUARIO:\n' + pergunta.slice(0, 2000)
        const resp = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${geminiKey}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { temperature: 0.7, maxOutputTokens: 800 }
          })
        })
        const data = await resp.json()
        const texto = data?.candidates?.[0]?.content?.parts?.[0]?.text?.trim()
        if (texto && texto.length > 10) {
          return json({ ok: true, resposta: texto })
        }
      } catch (e) {
        console.error('Gemini assistente falhou:', e.message)
      }
      return json({ ok: true, resposta: respostaOffline(pergunta) })
    }

    // ─── CERTIDOES ─────────────────────────────────────────────────────────
    if (route === 'certidoes' && httpMethod === 'GET') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const { data } = await getSupabase().from('certidoes').select('*').order('criado_em', { ascending: false })
      return json(data || [])
    }

    if (route === 'certidoes' && httpMethod === 'POST') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const cid = body.id || crypto.randomUUID()
      const empresaId = (body.empresa_id || '').trim()
      const tipo = (body.tipo || '').trim()
      if (!empresaId || !tipo) return json({ ok: false, erro: 'Empresa e tipo sao obrigatorios.' }, 400)
      const { error } = await getSupabase().from('certidoes').insert({
        id: cid, empresa_id: empresaId,
        cnpj: (body.cnpj || '').trim(),
        uf: (body.uf || '').trim(),
        cidade: (body.cidade || '').trim(),
        tipo,
        data_emissao: body.data_emissao || '',
        data_validade: body.data_validade || '',
        status: body.status || 'pendente',
        arquivo_nome: body.arquivo_nome || '',
        arquivo_dados: body.arquivo_dados || '',
        observacoes: (body.obs || '').trim()
      })
      if (error) return json({ ok: false, erro: error.message }, 500)
      await audit(user.id, 'CREATE', 'certidao', cid, `Certidao ${tipo} criada`)
      return json({ ok: true, id: cid })
    }

    if (parts[0] === 'certidoes' && parts[1] && httpMethod === 'PUT') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const upd = {}
      if (body.empresa_id !== undefined) upd.empresa_id = body.empresa_id
      if (body.cnpj !== undefined) upd.cnpj = (body.cnpj || '').trim()
      if (body.uf !== undefined) upd.uf = (body.uf || '').trim()
      if (body.cidade !== undefined) upd.cidade = (body.cidade || '').trim()
      if (body.tipo !== undefined) upd.tipo = body.tipo
      if (body.data_emissao !== undefined) upd.data_emissao = body.data_emissao
      if (body.data_validade !== undefined) upd.data_validade = body.data_validade
      if (body.status !== undefined) upd.status = body.status
      if (body.arquivo_nome !== undefined) upd.arquivo_nome = body.arquivo_nome
      if (body.arquivo_dados !== undefined) upd.arquivo_dados = body.arquivo_dados
      if (body.obs !== undefined) upd.observacoes = body.obs
      const { error } = await getSupabase().from('certidoes').update(upd).eq('id', parts[1])
      if (error) return json({ ok: false, erro: error.message }, 500)
      await audit(user.id, 'UPDATE', 'certidao', parts[1], `Certidao atualizada`)
      return json({ ok: true })
    }

    if (parts[0] === 'certidoes' && parts[1] && httpMethod === 'DELETE') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      await getSupabase().from('certidoes').delete().eq('id', parts[1])
      await audit(user.id, 'DELETE', 'certidao', parts[1], `Certidao excluida`)
      return json({ ok: true })
    }

    // ─── LICITACOES ────────────────────────────────────────────────────────
    if (route === 'licitacoes' && httpMethod === 'GET') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const { data } = await getSupabase().from('licitacoes').select('*').order('criado_em', { ascending: false })
      return json(data || [])
    }

    if (route === 'licitacoes' && httpMethod === 'POST') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const lid = body.id || crypto.randomUUID()
      const numero = (body.numero_licitacao || '').trim()
      const objeto = (body.objeto || '').trim()
      if (!numero || !objeto) return json({ ok: false, erro: 'Numero da licitacao e objeto sao obrigatorios.' }, 400)
      const { error } = await getSupabase().from('licitacoes').insert({
        id: lid, numero_licitacao: numero, edital: (body.edital || '').trim(),
        objeto, empresa_id: body.empresa_id || '',
        contrato_id: body.contrato_id || '', valor: safeFloat(body.valor),
        data_homologacao: body.data_homologacao || '',
        data_inicio: body.data_inicio || '', data_fim: body.data_fim || '',
        status: body.status || 'em_andamento',
        arquivos: body.arquivos || '[]',
        observacoes: (body.obs || '').trim()
      })
      if (error) return json({ ok: false, erro: error.message }, 500)
      await audit(user.id, 'CREATE', 'licitacao', lid, `Licitacao ${numero} criada`)
      return json({ ok: true, id: lid })
    }

    if (parts[0] === 'licitacoes' && parts[1] && httpMethod === 'PUT') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const upd = { updated_at: new Date().toISOString() }
      if (body.numero_licitacao !== undefined) upd.numero_licitacao = body.numero_licitacao
      if (body.edital !== undefined) upd.edital = body.edital
      if (body.objeto !== undefined) upd.objeto = body.objeto
      if (body.empresa_id !== undefined) upd.empresa_id = body.empresa_id
      if (body.contrato_id !== undefined) upd.contrato_id = body.contrato_id
      if (body.valor !== undefined) upd.valor = safeFloat(body.valor)
      if (body.data_homologacao !== undefined) upd.data_homologacao = body.data_homologacao
      if (body.data_inicio !== undefined) upd.data_inicio = body.data_inicio
      if (body.data_fim !== undefined) upd.data_fim = body.data_fim
      if (body.status !== undefined) upd.status = body.status
      if (body.arquivos !== undefined) upd.arquivos = body.arquivos
      if (body.obs !== undefined) upd.observacoes = body.obs
      const { error } = await getSupabase().from('licitacoes').update(upd).eq('id', parts[1])
      if (error) return json({ ok: false, erro: error.message }, 500)
      await audit(user.id, 'UPDATE', 'licitacao', parts[1], `Licitacao atualizada`)
      return json({ ok: true })
    }

    if (parts[0] === 'licitacoes' && parts[1] && httpMethod === 'DELETE') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(user, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      await getSupabase().from('licitacoes').delete().eq('id', parts[1])
      await audit(user.id, 'DELETE', 'licitacao', parts[1], `Licitacao excluida`)
      return json({ ok: true })
    }

    // ─── CIDADES ───────────────────────────────────────────────────────────
    if (route === 'cidades' && httpMethod === 'GET') {
      const cidades = {"AC":["Acrelândia","Assis Brasil","Brasileia","Bujari","Capixaba","Cruzeiro do Sul","Epitaciolândia","Feijó","Jordão","Mâncio Lima","Manoel Urbano","Marechal Thaumaturgo","Plácido de Castro","Porto Acre","Porto Walter","Sena Madureira","Tarauacá"],"AL":["Arapiraca","Atalaia","Barreira dos Lamas","Maceió","Marechal Deodoro","Penedo","Palmeira dos Índios","Rio Largo","São Miguel dos Campos","União dos Palmares"],"AM":["Manaus","Parintins","Manacapuru","Coari","Itacoatiara","Tefé","Maués","São Gabriel da Cachoeira","Humaitá","Tabatinga"],"AP":["Macapá","Santana","Laranjal do Jari","Oiapoque","Mazagão","Tartarugalzinho","Vitória do Jari","Porto Grande","Calçoene","Pedra Branca do Amapari"],"BA":["Salvador","Feira de Santana","Vitória da Conquista","Camaçari","Itabuna","Juazeiro","Lauro de Freitas","Ilhéus","Jequié","Teixeira de Freitas","Barreiras","Alagoinhas","Porto Seguro","Simões Filho","Paulo Afonso","Eunápolis","Santo Antônio de Jesus","Valença","Candeias","Guanambi","Jaçanã","Barra","Luís Eduardo Magalhães","Bom Jesus da Lapa","Brumado","Crateús","Irecê"],"CE":["Fortaleza","Caucaia","Juazeiro do Norte","Maracanaú","Sobral","Crato","Itapipoca","Maranguape","Iguatu","Quixadá","Pacatuba","Aquiraz","Canindé","Guaraciaba do Norte","Tianguá","Sobral"],"DF":["Brasília","Águas Claras","Ceilândia","Taguatinga","Samambaia","Plano Piloto","Planaltina","Recanto das Emas","Santa Maria","São Sebastião","Park Way","Núcleo Bandeirante","Gama","Guará","Cruzeiro","Sobradinho"],"ES":["Vitória","Vila Velha","Serra","Cariacica","Linhares","Cachoeiro de Itapemirim","Aracruz","São Mateus","Colatina","Guarapari","Cariacica","Marechal Floriano","Santa Teresa","São Gabriel da Palha","Nova Venécia"],"GO":["Goiânia","Aparecida de Goiânia","Anápolis","Rio Verde","Luziânia","Águas Lindas de Goiás","Formosa","Novo Gama","Itumbiara","Senador Canedo","Catalão","Jataí","Planaltina","Valparaíso de Goiás","Trindade","Ipameri"],"MA":["São Luís","Imperatriz","São José de Ribamar","Timon","Caxias","Codó","Bacabal","Balsas","Timon","Santa Inês","Paço do Lumiar","Pacuí","Açailândia","Pindaré Mirim","Chapadinha","Barreirinhas","Raposa","Alcântara","Santa Maria","Pirapemas"],"MG":["Belo Horizonte","Uberlândia","Contagem","Juiz de Fora","Betim","Montes Claros","Ribeirão das Neves","Uberaba","Governador Valadares","Ipatinga","Sete Lagoas","Divinópolis","Santa Luzia","Poços de Caldas","Patos de Minas","Teófilo Otoni","Pouso Alegre","Barbacena","Sabará","Varginha","Viçosa","Lavras","Itabira","Três Corações","Alfenas"],"MS":["Campo Grande","Dourados","Três Lagoas","Corumbá","Ponta Porã","Naviraí","Nova Andradina","Aquidauana","Sidrolândia","Maracaju","Nova Alvorada do Sul","Angélica","Iguatemi","Deodápolis","Juti"],"MT":["Cuiabá","Várzea Grande","Rondonópolis","Sinop","Sorriso","Lucas do Rio Verde","Tangará da Serra","Cáceres","Barra do Garças","Primavera do Leste","Barra do Bugres","Nobres","Campo Verde","Alta Floresta","Colíder","Guarantã do Norte","Nova Mutum","Canarana","Querência"],"PA":["Belém","Ananindeua","Santarém","Marabá","Castanhal","Parauapebas","Abaetetuba","Cametá","Marituba","Bragança","Altamira","Paragominas","Tucuruí","Tailândia","Redenção","São Félix do Xingu","Xinguara","Breves","Oriximiná","Juruti"],"PB":["João Pessoa","Campina Grande","Santa Rita","Patos","Bayeux","Sousa","Cajazeiras","Cabedelo","Guarabira","Sapé","Catolé do Rocha","São Bento","Itabaiana","Queimadas","Nova Cruz","Esperança","Lagoa Seca","Alagoa Grande","Pombal"],"PE":["Recife","Jaboatão dos Guararapes","Olinda","Caruaru","Petrolina","Paulista","Cabo de Santo Agostinho","Camaragibe","Vitória de Santo Antão","Igarassu","São Lourenço da Mata","Abreu e Lima","Sirinhaém","Catende","Palmares","Goiana","Lagoa do Itaenga","São José do Egito","Belo Jardim","Garanhuns","Bezerros","Salgueiro","Ouricuri","Flores","Surubim"],"PI":["Teresina","Parnaíba","Picos","Piripiri","Floriano","Campo Maior","Barras","União","Altos","José de Freitas","São Raimundo Nonato","Esperantina","Codó","Lagoa Alegre","Miguel Alves"],"PR":["Curitiba","Londrina","Maringá","Ponta Grossa","Cascavel","São José dos Pinhais","Foz do Iguaçu","Colombo","Guarapuava","Paranaguá","Araucária","Toledo","Apucarana","Pinhais","Campo Largo","Ampére","Almirante Tamandaré","Camaratégí","Umuarama","Chopinzinho","Telemaco Borba","Califórnia","Cruzeiro do Oeste","São Mateus do Sul"],"RJ":["Rio de Janeiro","São Gonçalo","Duque de Caxias","Nova Iguaçu","Niterói","Belford Roxo","São João de Meriti","Campos dos Goytacazes","Petrópolis","Volta Redonda","Magé","Itaboraí","Nova Friburgo","Barra Mansa","Angra dos Reis","Cabo Frio","Resende","Macaé","Nilópolis","Queimados","Araruama","Nova Iguaçu","Mesquita"],"RN":["Natal","Mossoró","Parnamirim","São Gonçalo do Amarante","Macaíba","Ceará-Mirim","Caicó","Açu","Currais Novos","São José de Mipibu","Canguaretama","Acari","São Tomé","Vera Cruz","Alexandria"],"RO":["Porto Velho","Ji-Paraná","Ariquemes","Vilhena","Cacoal","Jaru","Guajará-Mirim","Ouro Preto do Oeste","Pimenta Bueno","Cerejeiras","Alvorada do Oeste","Candeias do Jamari","São Francisco do Guaporé","Presidente Médici","Chupinguaia"],"RR":["Boa Vista","Rorainópolis","Caracaraí","Pacaraima","Alto Alegre","Cantá","Bonfim","Mucajaí","Normandia","Uiramutã"],"RS":["Porto Alegre","Caxias do Sul","Pelotas","Canoas","Santa Maria","Gravataí","Viamão","Novo Hamburgo","São Leopoldo","Rio Grande","Alvorada","Passo Fundo","Sapucaia do Sul","Cachoeirinha","Santa Cruz do Sul","Ijuí","Uruguaiana","Bagé","Bento Gonçalves","Erechim","Carazinho","Lajeado","Trairi","Gramado","Canela","Búzios"],"SC":["Florianópolis","Joinville","Blumenau","São José","Chapecó","Criciúma","Itajaí","Jaraguá do Sul","Lages","Palhoça","Balneário Camboriú","Brusque","Tubarão","Sorocaba","Navegantes","Itapema","Penha","Balneário Piçarras","Porto Belo","Campo Bom","Novo Hamburgo","São Bento do Sul","Gaspar","Guabiruba","Indaial","Pomerode"],"SE":["Aracaju","Nossa Senhora do Socorro","Lagarto","Itabaiana","São Cristóvão","Estância","Tobias Barreto","Simão Dias","Propriá","Capela","Umbaúba","Boquim","Barra dos Coqueiros"],"SP":["São Paulo","Guarulhos","Campinas","São Bernardo do Campo","Santo André","São José dos Campos","Osasco","Ribeirão Preto","Sorocaba","Santos","Mauá","São José do Rio Preto","Mogi das Cruzes","Diadema","Jundiaí","Piracicaba","Carapicuíba","Bauru","Itaquaquecetuba","São Vicente","Porto Feliz","São José do Rio Preto","Franca","Marília","Presidente Prudente","Araraquara","São Carlos","Ribeirão Preto","Presidente Epitácio","Araçatuba","Matão","Botucatu","Jaú","Limeira","Atibaia","Itatiba","Bragança Paulista","Votuporanga","Assis","Ourinhos","Tupã","Avaré","Itapeva","Registro","Iguape","Cajuru","Cruzeiro","Pindamonhangaba","Taubaté","Guaratinguetá","Aparecida","Cachoeira Paulista","Lorena","Pindamonhangaba","Taquaritinga","Catanduva","Bebedouro","Colina","Barretos","Jaboticabal","Gavião Peixoto","Ribeirão Preto","Passos","Poços de Caldas","Varginha","Alfenas","Passos","São Sebastião do Paraíso","Ituiutaba","Uberlândia","Uberaba","Araguari","Itumbiara","Rio Verde","Jataí"],"TO":["Palmas","Araguaína","Gurupi","Porto Nacional","Paraíso do Tocantins","Colinas do Tocantins","Guaraí","Tocantinópolis","Dianópolis","Miracema do Tocantins","Nova Rosalândia","Alvorada","São Félix do Tocantins","Lagoa da Confusão","Araguatins"]};
      return json(cidades)
    }

    // ─── 404 ─────────────────────────────────────────────────────────────
    return json({ ok: false, erro: 'Rota nao encontrada' }, 404)

  } catch (e) {
    console.error('API Error:', e.message, e.stack)
    return json({ ok: false, erro: 'Erro interno: ' + e.message }, 500)
  }
}
