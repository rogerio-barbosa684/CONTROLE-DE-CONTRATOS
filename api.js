import { createClient } from '@supabase/supabase-js'
import jwt from 'jsonwebtoken'
import nodemailer from 'nodemailer'
import crypto from 'crypto'

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const JWT_SECRET = process.env.JWT_SECRET || crypto.randomBytes(32).toString('hex')

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)

// ─── HELPERS ───────────────────────────────────────────────────────────────

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' }
  })
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
    if (!hash || !hash.includes('$')) return resolve(false)
    const parts = hash.split('$')
    if (parts.length < 3) return resolve(false)
    const salt = parts[1]
    const storedHash = parts[2]
    crypto.pbkdf2(password, salt, 310000, 32, 'sha256', (err, key) => {
      if (err) reject(err)
      else resolve(key.toString('hex') === storedHash)
    })
  })
}

function generateCsrf() {
  return crypto.randomBytes(32).toString('hex')
}

function validateCsrf(cookieHeader, bodyCsrf) {
  if (!bodyCsrf) return false
  const cookies = parseCookies(cookieHeader)
  return cookies['csrf'] === bodyCsrf
}

function requireAdmin(user) {
  if (!user || user.role !== 'admin') {
    return json({ ok: false, erro: 'Acesso restrito ao administrador' }, 403)
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
  await supabase.from('audit_log').insert({
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

// ─── EMAIL ─────────────────────────────────────────────────────────────────

async function getEmailConfig() {
  const { data } = await supabase.from('email_config').select('*').eq('id', 1).single()
  if (!data) return {}
  const cfg = { ...data }
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
  await supabase.from('email_config').upsert({ id: 1, ...data })
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
  const transporter = nodemailer.createTransport({
    host: cfg.smtp_server || 'smtp.gmail.com',
    port: parseInt(cfg.smtp_port) || 587,
    secure: false,
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
  const cookieHeader = headers.cookie || ''
  const host = headers.host || ''
  const isSecure = process.env.HTTPS === '1' || host.includes('netlify.app')

  const csrfToken = generateCsrf()
  const user = getAuthUser(cookieHeader)

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
      return json({ csrf_token: csrfToken }, 200, {
        'Set-Cookie': setCookie('csrf', csrfToken, { secure: isSecure, maxAge: 86400 })
      })
    }

    // ─── ME ──────────────────────────────────────────────────────────────
    if (route === 'me' && httpMethod === 'GET') {
      if (!user) return json({ ok: false, user: null }, 401)
      const { data: dbUser } = await supabase.from('users').select('id, username, full_name, role').eq('id', user.id).single()
      return json({ ok: true, user: dbUser, csrf_token: csrfToken }, 200, {
        'Set-Cookie': setCookie('csrf', csrfToken, { secure: isSecure, maxAge: 86400 })
      })
    }

    // ─── LOGIN ───────────────────────────────────────────────────────────
    if (route === 'login' && httpMethod === 'POST') {
      const { username, password } = body
      const { data: dbUser } = await supabase.from('users').select('*').eq('username', username).eq('active', 1).single()
      if (!dbUser || !(await checkPassword(password, dbUser.password_hash))) {
        return json({ ok: false, erro: 'Usuario ou senha incorretos!' }, 401)
      }
      const now = Math.floor(Date.now() / 1000)
      const token = jwt.sign(
        { id: dbUser.id, username: dbUser.username, full_name: dbUser.full_name, role: dbUser.role, _lastActive: now },
        JWT_SECRET,
        { expiresIn: '8h' }
      )
      await audit(dbUser.id, 'LOGIN', 'user', String(dbUser.id), `Login: ${dbUser.username}`)
      return json({
        ok: true,
        user: { id: dbUser.id, username: dbUser.username, full_name: dbUser.full_name, role: dbUser.role }
      }, 200, {
        'Set-Cookie': [
          setCookie('token', token, { secure: isSecure, maxAge: 28800 }),
          setCookie('csrf', csrfToken, { secure: isSecure, maxAge: 86400 })
        ].join(', ')
      })
    }

    // ─── LOGOUT ──────────────────────────────────────────────────────────
    if (route === 'logout' && httpMethod === 'POST') {
      if (user) await audit(user.id, 'LOGOUT', 'user', String(user.id), `Logout: ${user.username}`)
      return json({ ok: true }, 200, {
        'Set-Cookie': [
          'token=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0',
          'csrf=; Path=/; SameSite=Lax; Max-Age=0'
        ].join(', ')
      })
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
        if (!validateCsrf(cookieHeader, body.csrf_token)) {
          return json({ ok: false, erro: 'CSRF invalido' }, 403)
        }
        const { data: oldCfg } = await supabase.from('email_config').select('*').eq('id', 1).single()
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
      if (!validateCsrf(cookieHeader, body.csrf_token)) {
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
      const { data: contratos } = await supabase.from('contracts').select('*')
      const { data: pagamentos } = await supabase.from('payments').select('*')
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
      if (!validateCsrf(cookieHeader, body.csrf_token)) {
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
      const { data: contratos } = await supabase.from('contracts').select('*')
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
      const { data: users } = await supabase.from('users').select('id, username, full_name, role, active, created_at').order('id')
      return json(users)
    }

    if (route === 'users' && httpMethod === 'POST') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(cookieHeader, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const username = (body.username || '').trim()
      const fullName = (body.full_name || '').trim()
      const password = (body.password || '').trim()
      const role = (body.role || 'user').trim()
      if (!username || !fullName || !password) {
        return json({ ok: false, erro: 'Preencha todos os campos' }, 400)
      }
      const { data: existing } = await supabase.from('users').select('id').eq('username', username).single()
      if (existing) return json({ ok: false, erro: 'Usuario ja existe' }, 400)
      const hash = await hashPassword(password)
      const { data: newUser } = await supabase.from('users').insert({
        username, full_name: fullName, password_hash: hash, role
      }).select().single()
      await audit(user.id, 'CREATE', 'user', '', `Usuario ${username} criado por ${user.username}`)
      return json({ ok: true, user: { id: newUser.id } })
    }

    if (parts[0] === 'users' && parts[1] && httpMethod === 'PUT') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(cookieHeader, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const uid = parseInt(parts[1])
      const fullName = (body.full_name || '').trim()
      const role = (body.role || 'user').trim()
      const active = body.active !== false ? 1 : 0
      await supabase.from('users').update({ full_name: fullName, role, active }).eq('id', uid)
      await audit(user.id, 'UPDATE', 'user', String(uid), `Usuario ${uid} atualizado por ${user.username}`)
      return json({ ok: true })
    }

    if (parts[0] === 'users' && parts[1] && httpMethod === 'DELETE') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(cookieHeader, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const uid = parseInt(parts[1])
      if (uid === 1) return json({ ok: false, erro: 'Nao e possivel inativar o usuario admin principal.' }, 400)
      await supabase.from('users').update({ active: 0 }).eq('id', uid)
      await audit(user.id, 'INACTIVATE', 'user', String(uid), `Usuario ${uid} inativado por ${user.username}`)
      return json({ ok: true })
    }

    // ─── COMPANIES ───────────────────────────────────────────────────────
    if (route === 'companies' && httpMethod === 'GET') {
      const { data } = await supabase.from('companies').select('*').order('nome')
      return json(data)
    }

    if (route === 'companies' && httpMethod === 'POST') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      if (!validateCsrf(cookieHeader, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      const cid = body.id || crypto.randomUUID()
      const nome = (body.nome || '').trim()
      if (!nome) return json({ ok: false, erro: 'Nome da empresa e obrigatorio.' }, 400)
      const cnpj = (body.cnpj || '').trim()
      const { data: existing } = await supabase.from('companies').select('id').eq('id', cid).single()
      if (existing) {
        await supabase.from('companies').update({ nome, cnpj }).eq('id', cid)
      } else {
        await supabase.from('companies').insert({ id: cid, nome, cnpj })
      }
      return json({ ok: true, id: cid })
    }

    if (parts[0] === 'companies' && parts[1] && httpMethod === 'DELETE') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(cookieHeader, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      await supabase.from('companies').delete().eq('id', parts[1])
      return json({ ok: true })
    }

    // ─── CONTRACTS DELETE ────────────────────────────────────────────────
    if (parts[0] === 'contracts' && parts[1] && httpMethod === 'DELETE') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(cookieHeader, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      await supabase.from('payments').delete().eq('contract_id', parts[1])
      await supabase.from('additives').delete().eq('contract_id', parts[1])
      await supabase.from('contracts').delete().eq('id', parts[1])
      await audit(user.id, 'DELETE', 'contract', parts[1], `Contrato ${parts[1]} excluido por ${user.username}`)
      return json({ ok: true })
    }

    // ─── PAYMENTS DELETE ─────────────────────────────────────────────────
    if (parts[0] === 'payments' && parts[1] && httpMethod === 'DELETE') {
      const authErr = requireAuth(user)
      if (authErr) return authErr
      const adminErr = requireAdmin(user)
      if (adminErr) return adminErr
      if (!validateCsrf(cookieHeader, body.csrf_token)) {
        return json({ ok: false, erro: 'CSRF invalido' }, 403)
      }
      await supabase.from('payments').delete().eq('id', parts[1])
      await audit(user.id, 'DELETE', 'payment', parts[1], `Pagamento ${parts[1]} excluido por ${user.username}`)
      return json({ ok: true })
    }

    // ─── SYNC ────────────────────────────────────────────────────────────
    if (route === 'sync') {
      if (httpMethod === 'GET') {
        const authErr = requireAuth(user)
        if (authErr) return authErr
        const [contratos, pagamentos, usuarios, aditivos, empresas, destinatarios] = await Promise.all([
          supabase.from('contracts').select('*').order('created_at', { ascending: false }),
          supabase.from('payments').select('*').order('vencimento'),
          supabase.from('users').select('id, username, full_name, role, created_at').order('id'),
          supabase.from('additives').select('*').order('created_at'),
          supabase.from('companies').select('*').order('nome'),
          supabase.from('destinatarios').select('*').order('criado_em'),
        ])
        return json({
          contratos: contratos.data || [],
          pagamentos: pagamentos.data || [],
          usuarios: usuarios.data || [],
          aditivos: aditivos.data || [],
          empresas: empresas.data || [],
          destinatarios: destinatarios.data || []
        })
      }

      if (httpMethod === 'POST') {
        const authErr = requireAuth(user)
        if (authErr) return authErr
        if (!validateCsrf(cookieHeader, body.csrf_token)) {
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
            return json({ ok: false, erro: `Arquivo do contrato ${numero} excede 10MB.` }, 400)
          }
          const pgto = c.pgtoConfig || {}
          const arquivoJson = c.arquivo ? JSON.stringify(c.arquivo) : null
          const { data: existing } = await supabase.from('contracts').select('id').eq('id', cid).single()
          const vals = {
            numero, fornecedor: (c.parte || '').trim(), cnpj: (c.doc || '').trim(),
            objeto: (c.objeto || '').trim(), valor_total: parseFloat(c.valor || 0),
            inicio: (c.inicio || '').trim(), fim: (c.fim || '').trim(),
            tem_parcelas: c.temParcelas ? 1 : 0, qtd_parcelas: pgto.qtdParcelas,
            valor_parcela: safeFloat(pgto.valorParcela), dia_vencimento: pgto.diaVenc,
            responsavel: (c.responsavel || '').trim(), setor: (c.setor || '').trim(),
            obs: (c.obs || '').trim(), tipo: c.tipo, empresa_id: c.empresaId,
            forma_pagamento: pgto.forma, arquivo_contrato: arquivoJson
          }
          if (existing) {
            await supabase.from('contracts').update({ ...vals, updated_at: new Date().toISOString() }).eq('id', cid)
          } else {
            await supabase.from('contracts').insert({ id: cid, ...vals, created_by: 1 })
          }
          importados.contratos++

          if (c.aditivos?.length) {
            await supabase.from('additives').delete().eq('contract_id', cid)
            for (const a of c.aditivos) {
              if (a.arquivo?.data?.length > MAX_BASE64) {
                return json({ ok: false, erro: 'Arquivo de aditivo excede 10MB.' }, 400)
              }
              const arqJson = a.arquivo ? JSON.stringify(a.arquivo) : null
              await supabase.from('additives').insert({
                id: a.id || crypto.randomUUID(), contract_id: cid, numero: a.numero,
                data_aditivo: a.data || '', tipo: a.tipo, nova_data_fim: a.novaData,
                acrescimo_valor: a.novoValor, descricao: a.objeto || '',
                arquivo_contrato: arqJson, created_by: 1
              })
              importados.aditivos++
            }
          }
        }

        const pagDados = body.pagamentos || []
        const contratosPag = new Set(pagDados.filter(p => p.contratoId).map(p => p.contratoId))
        for (const cid of contratosPag) {
          await supabase.from('payments').delete().eq('contract_id', cid)
        }
        for (const p of pagDados) {
          const pid = (p.id || '').trim() || crypto.randomUUID()
          const cid = (p.contratoId || '').trim()
          const descricao = (p.descricao || '').trim()
          const vencimento = (p.vencimento || '').trim()
          if (!cid || !vencimento) { importados.ignorados++; continue }
          if (p.comprovante?.data?.length > MAX_BASE64) {
            return json({ ok: false, erro: 'Comprovante de pagamento excede 10MB.' }, 400)
          }
          const valor = parseFloat(p.valor || 0)
          const dataPag = (p.dataPagamento || '').trim() || null
          const comprovanteJson = p.comprovante ? JSON.stringify(p.comprovante) : null
          await supabase.from('payments').insert({
            id: pid, contract_id: cid, descricao, vencimento, valor,
            contrato_num: (p.contratoNum || '').trim() || null,
            data_pagamento: dataPag, valor_pago: safeFloat(p.valorPago) || (dataPag ? valor : null),
            forma_pagamento: (p.formaPgto || '').trim() || null,
            status: dataPag ? 'pago' : 'pendente', obs: (p.obs || '').trim(),
            comprovante: comprovanteJson, created_by: 1
          })
          importados.pagamentos++
        }

        for (const d of (body.destinatarios || [])) {
          const did = (d.id || '').trim()
          const email = (d.email || '').trim()
          if (!did || !email) { importados.ignorados++; continue }
          const { data: existing } = await supabase.from('destinatarios').select('id').eq('id', did).single()
          if (existing) {
            await supabase.from('destinatarios').update({
              email, nome: (d.nome || '').trim(),
              empresa_ids: JSON.stringify(d.empresaIds || [])
            }).eq('id', did)
          } else {
            await supabase.from('destinatarios').insert({
              id: did, email, nome: (d.nome || '').trim(),
              empresa_ids: JSON.stringify(d.empresaIds || [])
            })
          }
          importados.destinatarios = (importados.destinatarios || 0) + 1
        }

        await audit(user.id, 'SYNC', 'system', '', `Sincronizacao concluida: ${JSON.stringify(importados)}`)
        return json({ ok: true, importados })
      }
    }

    // ─── 404 ─────────────────────────────────────────────────────────────
    return json({ ok: false, erro: 'Rota nao encontrada' }, 404)

  } catch (e) {
    console.error('API Error:', e)
    return json({ ok: false, erro: 'Erro interno do servidor' }, 500)
  }
}
