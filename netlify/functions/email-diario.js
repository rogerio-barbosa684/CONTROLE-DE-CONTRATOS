import { createClient } from '@supabase/supabase-js'
import nodemailer from 'nodemailer'
import crypto from 'crypto'

export const schedule = '0 13 * * *' // Todos os dias as 13h UTC = 10h BRL

let _supabase = null
function getSupabase() {
  if (_supabase) return _supabase
  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) {
    throw new Error('SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem estar configurados nas variaveis de ambiente do Netlify.')
  }
  _supabase = createClient(url, key)
  return _supabase
}

async function getConfigEmail() {
  const { data } = await getSupabase().from('email_config').select('*').eq('id', 1).single()
  if (!data) return {}
  const cfg = { ...data }
  if (cfg.email_senha_enc) {
    try {
      const key = crypto.createHash('sha256').update(process.env.JWT_SECRET || '').digest()
      const decipher = crypto.createDecipheriv(
        'aes-256-cbc',
        key,
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

async function getDestinatarios() {
  const { data } = await getSupabase().from('destinatarios').select('*')
  return data || []
}

async function getEmpresas() {
  const { data } = await getSupabase().from('companies').select('*')
  return data || []
}

async function getContratos() {
  const { data } = await getSupabase().from('contracts').select('*')
  return data || []
}

async function getPayments() {
  const { data } = await getSupabase().from('payments').select('*')
  return data || []
}

function datefmt(d) {
  if (!d) return '—'
  const [y, m, day] = d.split('-')
  return `${day}/${m}/${y}`
}

function money(v) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0)
}

function getAlertas(dest) {
  let alertas = dest.alertas || []
  if (typeof alertas === 'string') {
    try { alertas = JSON.parse(alertas) } catch { alertas = [] }
  }
  return alertas
}

function processarPagamentos(contratos, pagamentos, hoje, empresaNomes = {}) {
  const vencidos = [], venceHoje = [], venceAmanha = []
  for (const p of pagamentos) {
    if (p.data_pagamento) continue
    const venc = (p.vencimento || '').slice(0, 10)
    let dv
    try { dv = new Date(venc + 'T00:00:00') } catch { continue }
    const c = contratos.find(c2 => c2.id === p.contract_id)
    const contratoNum = p.contrato_num || c?.numero || '?'
    const empresaId = c?.empresa_id || ''
    const empresaNome = empresaNomes[empresaId] || ''
    const info = {
      numero_contrato: contratoNum, empresa: empresaNome || '—',
      parte: c?.fornecedor || '?', descricao: p.descricao || '?',
      vencimento: datefmt(venc), valor: money(p.valor || 0)
    }
    const hojeMs = hoje.getTime()
    const dvMs = dv.getTime()
    if (dvMs < hojeMs) { info.dias = Math.floor((hojeMs - dvMs) / 86400000); vencidos.push(info) }
    else if (dvMs === hojeMs) { venceHoje.push(info) }
    else if (dvMs - hojeMs <= 86400000) { venceAmanha.push(info) }
  }
  return { vencidos, venceHoje, venceAmanha }
}

function processarContratosVencidos(contratos, hoje, empresaNomes = {}) {
  return contratos.filter(c => {
    if (!c.fim) return false
    try { return new Date(c.fim + 'T00:00:00') < hoje } catch { return false }
  }).map(c => ({
    numero: c.numero, empresa: empresaNomes[c.empresa_id] || '—', fornecedor: c.fornecedor || '?',
    objeto: c.objeto || '?', fim: datefmt(c.fim),
    dias: Math.floor((hoje - new Date(c.fim + 'T00:00:00')) / 86400000)
  }))
}

function processarContratosAVencer(contratos, hoje, empresaNomes = {}) {
  const grupos = { 30: [], 15: [], 7: [] }
  for (const c of contratos) {
    if (!c.fim) continue
    try {
      const df = new Date(c.fim + 'T00:00:00')
      const dias = Math.floor((df - hoje) / 86400000)
      if (dias > 0 && dias <= 30) {
        const info = {
          numero: c.numero, empresa: empresaNomes[c.empresa_id] || '—', fornecedor: c.fornecedor || '?',
          objeto: c.objeto || '?', fim: datefmt(c.fim), dias
        }
        if (dias <= 7) grupos[7].push(info)
        else if (dias <= 15) grupos[15].push(info)
        else grupos[30].push(info)
      }
    } catch {}
  }
  return grupos
}

function montarHtmlPagamentos(vencidos, venceHoje, venceAmanha, titulo = '') {
  const partes = []
  if (vencidos.length) {
    partes.push(`<div style="background:#fff3cd;border-left:4px solid #d4820a;padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:16px">
      <h3 style="color:#856404;margin:0 0 8px">Pagamentos Vencidos${titulo}</h3>
      <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
        <tr style="background:#f5f5f5"><th style="padding:6px;text-align:left">Contrato</th><th>Empresa</th><th>Fornecedor</th><th>Descrição</th><th>Vencimento</th><th>Valor</th><th>Dias</th></tr>
        ${vencidos.map(v => `<tr><td style="padding:6px">${v.numero_contrato}</td><td>${v.empresa}</td><td>${v.parte}</td><td>${v.descricao}</td><td>${v.vencimento}</td><td>${v.valor}</td><td style="color:red;font-weight:bold">${v.dias}d</td></tr>`).join('')}
      </table>
    </div>`)
  }
  if (venceHoje.length) {
    partes.push(`<div style="background:#f8d7da;border-left:4px solid #c0392b;padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:16px">
      <h3 style="color:#721c24;margin:0 0 8px">Vence Hoje${titulo}</h3>
      ${venceHoje.map(v => `<p style="margin:4px 0;font-size:0.85rem"><b>${v.numero_contrato}</b> - ${v.empresa} - ${v.parte} - ${v.vencimento} - ${v.valor}</p>`).join('')}
    </div>`)
  }
  if (venceAmanha.length) {
    partes.push(`<div style="background:#fff3cd;border-left:4px solid #d4820a;padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:16px">
      <h3 style="color:#856404;margin:0 0 8px">Vence Amanha${titulo}</h3>
      ${venceAmanha.map(v => `<p style="margin:4px 0;font-size:0.85rem"><b>${v.numero_contrato}</b> - ${v.empresa} - ${v.parte} - ${v.vencimento} - ${v.valor}</p>`).join('')}
    </div>`)
  }
  return partes
}

function montarHtmlContratosVencidos(vencidos, titulo = '') {
  if (!vencidos.length) return []
  return [`<div style="background:#f8d7da;border-left:4px solid #c0392b;padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:16px">
    <h3 style="color:#721c24;margin:0 0 8px">Contratos Vencidos${titulo}</h3>
    ${vencidos.map(v => `<p style="margin:4px 0;font-size:0.85rem"><b>${v.numero}</b> - ${v.empresa} - ${v.fornecedor} - ${v.objeto} - Venceu: ${v.fim} (${v.dias} dias)</p>`).join('')}
  </div>`]
}

function montarHtmlContratosAVencer(grupos, titulo = '') {
  const partes = []
  for (const [dias, lista] of Object.entries(grupos)) {
    if (!lista.length) continue
    const cor = parseInt(dias) <= 7 ? '#c0392b' : parseInt(dias) <= 15 ? '#d4820a' : '#24527a'
    partes.push(`<div style="background:#f0f4f8;border-left:4px solid ${cor};padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:16px">
      <h3 style="color:${cor};margin:0 0 8px">Vence em ${dias} dias${titulo}</h3>
      ${lista.map(v => `<p style="margin:4px 0;font-size:0.85rem"><b>${v.numero}</b> - ${v.empresa} - ${v.fornecedor} - ${v.objeto} - ${v.fim} (${v.dias}d)</p>`).join('')}
    </div>`)
  }
  return partes
}

async function enviarEmail(cfg, html, assunto, destinatario) {
  const transporter = nodemailer.createTransport({
    host: cfg.smtp_server || 'smtp.gmail.com',
    port: parseInt(cfg.smtp_port) || 587,
    secure: parseInt(cfg.smtp_port) === 465,
    auth: { user: cfg.email_remetente, pass: cfg.email_senha }
  })
  await transporter.sendMail({
    from: cfg.email_remetente, to: destinatario, subject: assunto, html
  })
}

export async function handler(event) {
  try {
    const cfg = await getConfigEmail()
    if (!cfg.email_remetente || !cfg.email_senha) {
      console.log('[EMAIL AUTO] Config de email nao encontrada. Pulando.')
      return { statusCode: 200, body: 'Email not configured' }
    }

    const destinatarios = await getDestinatarios()
    if (!destinatarios.length) {
      console.log('[EMAIL AUTO] Nenhum destinatario cadastrado. Pulando.')
      return { statusCode: 200, body: 'No recipients' }
    }

    const contratos = await getContratos()
    const pagamentos = await getPayments()
    const empresas = await getEmpresas()
    const empresaNomes = {}
    empresas.forEach(e => { if (e.id && e.nome) empresaNomes[e.id] = e.nome })
    const hoje = new Date()
    hoje.setHours(0, 0, 0, 0)

    let enviados = 0
    const erros = []

    for (const dest of destinatarios) {
      const email = (dest.email || '').trim()
      if (!email) continue

      const alertas = getAlertas(dest)

      let empresaIds = dest.empresa_ids || []
      if (typeof empresaIds === 'string') {
        try { empresaIds = JSON.parse(empresaIds) } catch { empresaIds = [] }
      }
      const empIdsSet = empresaIds.length ? new Set(empresaIds) : null

      // Lembretes de pagamentos
      if (!alertas.length || alertas.includes('pagamentos')) {
        const contratoIdsEmp = new Set(contratos.filter(c => empIdsSet === null || empIdsSet.has(c.empresa_id)).map(c => c.id))
        const empPagamentos = pagamentos.filter(p => contratoIdsEmp.has(p.contract_id))
        const { vencidos, venceHoje, venceAmanha } = processarPagamentos(contratos, empPagamentos, hoje, empresaNomes)

        if (vencidos.length || venceHoje.length || venceAmanha.length) {
          const rotulo = dest.nome ? ` - ${dest.nome}` : ''
          const partes = montarHtmlPagamentos(vencidos, venceHoje, venceAmanha, rotulo)
          const html = `<html><body style="font-family:Arial,sans-serif;padding:20px">
            ${partes.join('')}
            <p style="color:#666;font-size:12px">Gerado automaticamente em ${new Date().toLocaleString('pt-BR')}</p></body></html>`
          try {
            await enviarEmail(cfg, html, `Lembrete de Pagamentos${rotulo} - ${hoje.toLocaleDateString('pt-BR')}`, email)
            enviados++
          } catch (e) { erros.push(`Pagamentos ${email}: ${e.message}`) }
        }
      }

      // Alertas de contratos
      if (!alertas.length || alertas.includes('contratos')) {
        const empContratos = contratos.filter(c => empIdsSet === null || empIdsSet.has(c.empresa_id))
        const empVencidos = processarContratosVencidos(empContratos, hoje, empresaNomes)
        const empAVencer = processarContratosAVencer(empContratos, hoje, empresaNomes)

        if (empVencidos.length || Object.values(empAVencer).some(v => v.length)) {
          const rotulo = dest.nome ? ` - ${dest.nome}` : ''
          const regioes = [
            ...montarHtmlContratosVencidos(empVencidos, rotulo),
            ...montarHtmlContratosAVencer(empAVencer, rotulo)
          ]
          const html = `<html><body style="font-family:Arial,sans-serif;padding:20px">
            ${regioes.join('<hr style="margin:24px 0">')}
            <p style="color:#666;font-size:12px">Gerado automaticamente em ${new Date().toLocaleString('pt-BR')}</p></body></html>`
          try {
            await enviarEmail(cfg, html, `Alerta de Contratos${rotulo} - ${hoje.toLocaleDateString('pt-BR')}`, email)
            enviados++
          } catch (e) { erros.push(`Contratos ${email}: ${e.message}`) }
        }
      }
    }

    console.log(`[EMAIL AUTO] ${enviados} e-mail(s) enviado(s)`)
    if (erros.length) console.log(`[EMAIL AUTO] Erros: ${erros.join('; ')}`)
    return { statusCode: 200, body: JSON.stringify({ ok: true, enviados, erros }) }

  } catch (e) {
    console.error('[EMAIL AUTO] Erro geral:', e)
    return { statusCode: 500, body: JSON.stringify({ ok: false, erro: e.message }) }
  }
}