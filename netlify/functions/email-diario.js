import { createClient } from '@supabase/supabase-js'
import nodemailer from 'nodemailer'

export const schedule = '0 13 * * *' // Todos os dias as 13h UTC = 10h BRL

let _supabase = null
function getSupabase() {
  if (_supabase) return _supabase
  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY
  _supabase = createClient(url, key)
  return _supabase
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

async function getConfigEmail() {
  const { data } = await getSupabase().from('config_email').select('*').limit(1).single()
  return data || {}
}

async function getDestinatarios() {
  const { data } = await getSupabase().from('destinatarios').select('*')
  return data || []
}

async function getEmpresas() {
  const { data } = await getSupabase().from('empresas').select('*')
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

function processarPagamentos(contratos, pagamentos, hoje, empresaNomes = {}) {
  const vencidos = [], venceHoje = [], venceAmanha = []
  for (const p of pagamentos) {
    if (p.data_pagamento) continue
    const venc = (p.vencimento || '').slice(0, 10)
    let dv
    try { dv = new Date(venc + 'T00:00:00') } catch { continue }
    const c = contratos.find(c2 => c2.id === p.contract_id)
    const contratoNum = p.contract_num || c?.numero || '?'
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

function processarContratosVencidos(contratos, hoje) {
  return contratos.filter(c => {
    if (!c.data_fim) return false
    try { return new Date(c.data_fim + 'T00:00:00') < hoje } catch { return false }
  }).map(c => ({
    numero: c.numero, empresa: c.empresa_nome || '—', fornecedor: c.fornecedor || '?',
    objeto: c.objeto || '?', data_fim: datefmt(c.data_fim),
    dias: Math.floor((hoje - new Date(c.data_fim + 'T00:00:00')) / 86400000)
  }))
}

function processarContratosAVencer(contratos, hoje) {
  const grupos = { 30: [], 15: [], 7: [] }
  for (const c of contratos) {
    if (!c.data_fim) continue
    try {
      const df = new Date(c.data_fim + 'T00:00:00')
      const dias = Math.floor((df - hoje) / 86400000)
      if (dias > 0 && dias <= 30) {
        const info = {
          numero: c.numero, empresa: c.empresa_nome || '—', fornecedor: c.fornecedor || '?',
          objeto: c.objeto || '?', data_fim: datefmt(c.data_fim), dias
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
    ${vencidos.map(v => `<p style="margin:4px 0;font-size:0.85rem"><b>${v.numero}</b> - ${v.empresa} - ${v.fornecedor} - ${v.objeto} - Venceu: ${v.data_fim} (${v.dias} dias)</p>`).join('')}
  </div>`]
}

function montarHtmlContratosAVencer(grupos, titulo = '') {
  const partes = []
  for (const [dias, lista] of Object.entries(grupos)) {
    if (!lista.length) continue
    const cor = parseInt(dias) <= 7 ? '#c0392b' : parseInt(dias) <= 15 ? '#d4820a' : '#24527a'
    partes.push(`<div style="background:#f0f4f8;border-left:4px solid ${cor};padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:16px">
      <h3 style="color:${cor};margin:0 0 8px">Vence em ${dias} dias${titulo}</h3>
      ${lista.map(v => `<p style="margin:4px 0;font-size:0.85rem"><b>${v.numero}</b> - ${v.empresa} - ${v.fornecedor} - ${v.objeto} - ${v.data_fim} (${v.dias}d)</p>`).join('')}
    </div>`)
  }
  return partes
}

async function enviarEmail(cfg, html, assunto, destinatario) {
  const transporter = nodemailer.createTransport({
    host: cfg.smtp_server, port: cfg.smtp_port, secure: cfg.smtp_port === 465,
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

      let empresaIds = dest.empresa_ids || []
      if (typeof empresaIds === 'string') {
        try { empresaIds = JSON.parse(empresaIds) } catch { empresaIds = [] }
      }
      const empIdsSet = empresaIds.length ? new Set(empresaIds) : null

      // Lembretes de pagamentos
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

      // Alertas de contratos
      const empContratos = contratos.filter(c => empIdsSet === null || empIdsSet.has(c.empresa_id))
      const empVencidos = processarContratosVencidos(empContratos, hoje)
      const empAVencer = processarContratosAVencer(empContratos, hoje)

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

    console.log(`[EMAIL AUTO] ${enviados} e-mail(s) enviado(s)`)
    if (erros.length) console.log(`[EMAIL AUTO] Erros: ${erros.join('; ')}`)
    return { statusCode: 200, body: JSON.stringify({ ok: true, enviados, erros }) }

  } catch (e) {
    console.error('[EMAIL AUTO] Erro geral:', e)
    return { statusCode: 500, body: JSON.stringify({ ok: false, erro: e.message }) }
  }
}
