#!/usr/bin/env node

/**
 * Script de Setup - Controle de Contratos
 * Execute após criar o projeto no Supabase e configurar as variáveis de ambiente
 */

const { createClient } = require('@supabase/supabase-js');
const bcrypt = require('bcryptjs');
const crypto = require('crypto');

// ============================================================
// CONFIGURAÇÃO - Preencha com seus dados
// ============================================================
const CONFIG = {
  // URL do projeto Supabase (ex: https://xxxxx.supabase.co)
  SUPABASE_URL: process.env.SUPABASE_URL || 'SUA_URL_SUPABASE',
  
  // Chave service_role do Supabase
  SUPABASE_KEY: process.env.SUPABASE_SERVICE_KEY || 'SUA_SERVICE_KEY',
  
  // Senha do usuário admin
  ADMIN_PASSWORD: 'Admin@123456',
  
  // Nome do primeiro setor
  DEFAULT_SECTOR: 'Geral',
};

// ============================================================
// FUNÇÕES AUXILIARES
// ============================================================

function generateId() {
  return crypto.randomBytes(16).toString('hex');
}

function log(msg, type = 'info') {
  const icons = { info: '✓', warn: '⚠', error: '✗', success: '✓' };
  console.log(`${icons[type] || '•'} ${msg}`);
}

// ============================================================
// MAIN
// ============================================================

async function main() {
  console.log('\n🚀 Setup do Sistema - Controle de Contratos\n');
  console.log('='.repeat(50));

  // Verificar configuração
  if (CONFIG.SUPABASE_URL.includes('SUA_URL')) {
    console.error('\n❌ Erro: Configure SUPABASE_URL e SUPABASE_KEY');
    console.log('\nOpções:');
    console.log('1. Defina as variáveis de ambiente:');
    console.log('   export SUPABASE_URL=https://xxxxx.supabase.co');
    console.log('   export SUPABASE_SERVICE_KEY=eyJhbGc...');
    console.log('\n2. Edite este arquivo e preencha CONFIG.SUPABASE_URL e CONFIG.SUPABASE_KEY');
    process.exit(1);
  }

  // Conectar ao Supabase
  log('Conectando ao Supabase...');
  const supabase = createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_KEY);

  // Testar conexão
  const { data: testData, error: testError } = await supabase
    .from('users')
    .select('id')
    .limit(1);

  if (testError) {
    if (testError.message.includes('relation "users" does not exist')) {
      log('Tabela "users" não encontrada!', 'error');
      console.log('\nExecute o schema.sql no SQL Editor do Supabase primeiro.');
      console.log('Arquivo: supabase/schema.sql\n');
      process.exit(1);
    }
    log(`Erro de conexão: ${testError.message}`, 'error');
    process.exit(1);
  }

  log('Conexão com Supabase OK', 'success');

  // Criar setor padrão
  log('Criando setor padrão...');
  const { error: sectorError } = await supabase
    .from('sectors')
    .upsert({
      id: CONFIG.DEFAULT_SECTOR.toLowerCase(),
      nome: CONFIG.DEFAULT_SECTOR,
      active: 1,
      criado_em: new Date().toISOString()
    }, { onConflict: 'id' });

  if (sectorError) {
    log(`Aviso: ${sectorError.message}`, 'warn');
  } else {
    log(`Setor "${CONFIG.DEFAULT_SECTOR}" criado`, 'success');
  }

  // Criar usuário admin
  log('Criando usuário admin...');
  const passwordHash = await bcrypt.hash(CONFIG.ADMIN_PASSWORD, 12);

  const { data: existingUser } = await supabase
    .from('users')
    .select('id')
    .eq('username', 'admin')
    .single();

  if (existingUser) {
    // Atualizar senha
    const { error: updateError } = await supabase
      .from('users')
      .update({ password_hash: passwordHash })
      .eq('username', 'admin');

    if (updateError) {
      log(`Erro ao atualizar admin: ${updateError.message}`, 'error');
    } else {
      log('Senha do admin atualizada', 'success');
    }
  } else {
    // Criar novo
    const { error: insertError } = await supabase
      .from('users')
      .insert({
        username: 'admin',
        full_name: 'Administrador',
        password_hash: passwordHash,
        role: 'admin',
        active: 1,
        created_at: new Date().toISOString()
      });

    if (insertError) {
      log(`Erro ao criar admin: ${insertError.message}`, 'error');
    } else {
      log('Usuário admin criado', 'success');
    }
  }

  // Vincular admin ao setor
  log('Vinculando admin ao setor...');
  const { error: linkError } = await supabase
    .from('user_setores')
    .upsert({
      user_id: existingUser?.id || 1,
      setor_id: CONFIG.DEFAULT_SECTOR.toLowerCase()
    }, { onConflict: 'user_id,setor_id' });

  if (linkError && !linkError.message.includes('duplicate')) {
    log(`Aviso: ${linkError.message}`, 'warn');
  } else {
    log('Admin vinculado ao setor', 'success');
  }

  // Configuração de email padrão
  log('Criando configuração de email...');
  const { error: emailError } = await supabase
    .from('email_config')
    .upsert({
      id: 1,
      smtp_server: 'smtp.gmail.com',
      smtp_port: 587
    }, { onConflict: 'id' });

  if (emailError) {
    log(`Aviso: ${emailError.message}`, 'warn');
  } else {
    log('Configuração de email criada', 'success');
  }

  // Resumo
  console.log('\n' + '='.repeat(50));
  console.log('✅ Setup concluído com sucesso!\n');
  console.log('Credenciais de acesso:');
  console.log(`  Usuário: admin`);
  console.log(`  Senha:   ${CONFIG.ADMIN_PASSWORD}`);
  console.log('\nPróximos passos:');
  console.log('1. Acesse o site no Netlify');
  console.log('2. Faça login com as credenciais acima');
  console.log('3. Altere a senha em "Minha Conta"');
  console.log('4. Configure empresas, setores e usuários');
  console.log('\n⚠️  Importante:');
  console.log('- Altere a senha padrão após primeiro login');
  console.log('- Mantenha a service_key segura');
  console.log('- Faça backups regulares com backup_supabase.js\n');
}

// Executar
main().catch(err => {
  console.error('\n❌ Erro fatal:', err.message);
  process.exit(1);
});
