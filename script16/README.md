# Controle de Contratos e Pagamentos

Sistema para gestão de contratos e pagamentos com alertas por email.

## Arquitetura

- **Frontend**: HTML/CSS/JS (`index.html`) - Single Page Application
- **Backend (novo)**: Netlify Functions + Supabase (PostgreSQL)
- **Backend (legado)**: Flask + SQLite (mantido para compatibilidade)

## Deploy no Supabase + Netlify

### 1. Criar projeto no Supabase

1. Acesse https://supabase.com e crie uma conta
2. Crie um novo projeto
3. No SQL Editor, cole e execute o conteúdo de `supabase/schema.sql`
4. Vá em **Project Settings → API** e anote:
   - `Project URL` (será o `SUPABASE_URL`)
   - `service_role key` (será o `SUPABASE_SERVICE_ROLE_KEY`)

### 2. Migrar os dados

Edite o arquivo `.env` com as credenciais do Supabase:

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=chave_service_role_aqui
```

Depois execute:

```bash
npm run migrate
```

### 3. Criar site no Netlify

1. Acesse https://netlify.com e faça login
2. Clique em **Add new site → Import an existing project**
3. Conecte com GitHub/GitLab (ou faça upload manual)
4. Em **Site settings → Environment variables**, adicione:

| Variável | Valor |
|----------|-------|
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role key do Supabase |
| `JWT_SECRET` | (deixe vazio para auto-gerar) |
| `SESSION_TIMEOUT_HOURS` | `8` |
| `ADMIN_PASSWORD` | Sua senha de admin |

5. Deploy será feito automaticamente ao conectar o repositório

### 4. Acessar

Seu sistema estará disponível em `https://seu-site.netlify.app`

## Desenvolvimento local

```bash
# Instalar dependências
npm install

# Rodar servidor Flask (legado, com SQLite)
python app.py

# Rodar Netlify local (novo backend)
npx netlify dev
```

## Estrutura do projeto

```
├── app.py                    # Backend Flask (legado)
├── index.html                # Frontend (funciona com ambos backends)
├── netlify/
│   └── functions/api.js      # Backend Netlify Functions (novo)
├── supabase/
│   ├── schema.sql            # Schema PostgreSQL
│   └── migrate.js            # Script de migração SQLite → Supabase
├── .env                      # Config local
├── .env.example              # Modelo de variáveis
├── netlify.toml              # Config Netlify
├── package.json              # Dependências Node.js
└── contratos.db              # Banco SQLite (dados existentes)
```
