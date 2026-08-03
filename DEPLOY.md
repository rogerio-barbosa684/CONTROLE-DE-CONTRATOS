# Guia de Deploy - Controle de Contratos

## Pré-requisitos

- Conta no [Supabase](https://supabase.com) (plano gratuito funciona)
- Conta no [Netlify](https://netlify.com) (plano gratuito funciona)
- Git instalado (opcional, mas recomendado)

---

## PASSO 1: Criar Projeto no Supabase

1. Acesse [supabase.com](https://supabase.com) e faça login
2. Clique em **"New Project"**
3. Preencha:
   - **Organization**: selecione ou crie uma
   - **Project Name**: `controle-contratos`
   - **Database Password**: gere uma senha forte (guarde!)
   - **Region**: selecione a mais próxima (Brasil: `South America (São Paulo)`)
4. Aguarde o projeto ser criado (~2 minutos)

---

## PASSO 2: Criar Tabelas no Supabase

1. No painel do projeto, vá em **SQL Editor** (menu lateral esquerdo)
2. Clique em **"New Query"**
3. Cole TODO o conteúdo do arquivo `supabase/schema.sql`
4. Clique em **"Run"** (botão verde)
5. Verifique se as tabelas foram criadas em **Table Editor**

Tabelas esperadas:
- `users`
- `password_resets`
- `sectors`
- `user_setores`
- `companies`
- `contracts`
- `payments`
- `additives`
- `audit_log`
- `destinatarios`
- `email_config`

---

## PASSO 3: Configurar Autenticação (RLS)

> **IMPORTANTE**: O sistema usa JWT via cookies. Você precisa desabilitar o RLS (Row Level Security) ou configurar políticas adequadas.

### Opção A: Desabilitar RLS (mais simples)

No SQL Editor, execute:

```sql
-- Desabilitar RLS em todas as tabelas
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE password_resets DISABLE ROW LEVEL SECURITY;
ALTER TABLE sectors DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_setores DISABLE ROW LEVEL SECURITY;
ALTER TABLE companies DISABLE ROW LEVEL SECURITY;
ALTER TABLE contracts DISABLE ROW LEVEL SECURITY;
ALTER TABLE payments DISABLE ROW LEVEL SECURITY;
ALTER TABLE additives DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log DISABLE ROW LEVEL SECURITY;
ALTER TABLE destinatarios DISABLE ROW LEVEL SECURITY;
ALTER TABLE email_config DISABLE ROW LEVEL SECURITY;
```

### Opção B: Habilitar RLS com políticas (mais seguro)

Se preferir manter RLS ativo, crie políticas para permitir acesso via service_role key.

---

## PASSO 4: Criar Usuário Admin Inicial

1. No SQL Editor, execute (substitua `SUA_SENHA_AQUI`):

```sql
-- Gerar hash da senha (você pode usar o endpoint de registro)
-- OU insira diretamente com hash pré-gerado

-- Para gerar o hash, use o endpoint POST /api/register
-- ou use o script migrate.js
```

2. **Método alternativo**: Use o script `supabase/migrate.js`:

```bash
cd script16
npm install
node supabase/migrate.js
```

Isso irá:
- Criar o usuário admin com senha padrão
- Migrar dados do SQLite local (se existir)

---

## PASSO 5: Obter Credenciais do Supabase

1. No painel do projeto, vá em **Settings** → **API**
2. Copie:
   - **Project URL** (ex: `https://xxxxxxxxxxxx.supabase.co`)
   - **anon public** key
   - **service_role** key (⚠️ mantenha segura!)

---

## PASSO 6: Criar Projeto no Netlify

1. Acesse [app.netlify.com](https://app.netlify.com) e faça login
2. Clique em **"Add new site"** → **"Deploy manually"**
3. Arraste a pasta `script16` inteira OU conecte seu repositório Git

### Opção A: Upload Manual
1. Acesse [app.netlify.com/drop](https://app.netlify.com/drop)
2. Arraste a pasta `script16`
3. Aguarde o deploy (~1 minuto)

### Opção B: Conectar ao GitHub
1. No Netlify, clique em **"Add new site"** → **"Import an existing project"**
2. Selecione **GitHub**
3. Escolha o repositório
4. Configurações de build:
   - **Base directory**: (deixe vazio ou `script16`)
   - **Build command**: `npm install`
   - **Publish directory**: `.`
5. Clique **"Deploy site"**

---

## PASSO 7: Configurar Variáveis de Ambiente no Netlify

1. No painel do site, vá em **Site settings** → **Environment variables**
2. Adicione as seguintes variáveis:

| Variável | Valor | Descrição |
|----------|-------|-----------|
| `SUPABASE_URL` | `https://xxxxx.supabase.co` | URL do projeto Supabase |
| `SUPABASE_KEY` | `eyJhbGc...` | Chave `anon` do Supabase |
| `SUPABASE_SERVICE_KEY` | `eyJhbGc...` | Chave `service_role` do Supabase |
| `JWT_SECRET` | `sua_senha_forte_aleatoria` | Senha para assinar JWTs |
| `NODE_VERSION` | `20` | Versão do Node.js |

### Gerar JWT_SECRET seguro:

```bash
# No terminal, execute:
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

---

## PASSO 8: Configurar URL de Redirecionamento

1. No Netlify, vá em **Domain settings**
2. Clique **"Add custom domain"** (se tiver domínio próprio)
3. OU anote a URL gerada (ex: `https://seu-site.netlify.app`)
4. Atualize o `index.html` se necessário (a URL da API é relativa: `/api/*`)

---

## PASSO 9: Testar o Deploy

1. Acesse a URL do Netlify
2. Faça login com:
   - **Usuário**: `admin`
   - **Senha**: a definida no Passo 4

3. Verifique:
   - [ ] Login funciona
   - [ ] Dashboard carrega
   - [ ] Contratos podem ser criados
   - [ ] Pagamentos funcionam
   - [ ] Configurações estão acessíveis

---

## PASSO 10: Configurar SSL (automático no Netlify)

O Netlify configura SSL automaticamente para todos os sites. Não precisa fazer nada!

---

## Solução de Problemas

### Erro "Cannot connect to Supabase"
- Verifique se `SUPABASE_URL` e `SUPABASE_KEY` estão corretos
- Verifique se o RLS está desabilitado ou com políticas adequadas

### Erro "JWT invalid"
- Verifique se `JWT_SECRET` está configurado no Netlify
- Limpe os cookies do navegador e faça login novamente

### Erro 404 na API
- Verifique se o redirect está configurado no `netlify.toml`
- Acesse `/.netlify/functions/api/health` para testar

### Erro de permissão
- Verifique o role do usuário na tabela `users`
- `admin`: acesso total
- `setor_admin`: acesso restrito a setores
- `user`: acesso mínimo

---

## Comandos Úteis

```bash
# Verificar status do deploy
netlify deploy --prod

# Limpar cache
netlify deploy --prod --build

# Ver logs
netlify logs --function api

# Backup do banco
node backup_supabase.js
```

---

## Manutenção

### Backup Automático
O arquivo `backup_supabase.js` pode ser configurado para rodar diariamente:

```bash
# Adicione ao crontab (Linux/Mac)
0 2 * * * cd /caminho/do/projeto && node backup_supabase.js
```

### Atualizar o Sistema
1. Baixe a nova versão do `script16`
2. Substitua os arquivos no Netlify (via drag-and-drop ou Git)
3. Execute migrações se houver alterações no schema

---

## Contatos

Em caso de problemas, verifique:
- Logs do Netlify: Site settings → Logs
- Logs do Supabase: Dashboard → Logs
- Console do navegador (F12)
