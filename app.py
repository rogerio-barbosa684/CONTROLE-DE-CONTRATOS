import os, re, sqlite3, uuid, calendar, smtplib, ssl, json, traceback, html, base64, secrets, socket, ipaddress
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from flask import (Flask, request, session, g, send_from_directory, jsonify, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography import x509
from cryptography.x509.oid import NameOID

def _load_env():
    global BASE_DIR
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding='utf-8') as f:
        lines = f.readlines()
    changed = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            k, _, v = stripped.partition('=')
            k = k.strip()
            if k:
                os.environ.setdefault(k, v.strip())
                if k == 'SECRET_KEY' and not v.strip():
                    new_key = secrets.token_hex(32)
                    os.environ['SECRET_KEY'] = new_key
                    line = f'SECRET_KEY={new_key}\n'
                    changed = True
                elif k == 'ENCRYPTION_KEY' and not v.strip():
                    new_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
                    os.environ['ENCRYPTION_KEY'] = new_key
                    line = f'ENCRYPTION_KEY={new_key}\n'
                    changed = True
        new_lines.append(line)
    if changed:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print("[SEGURANCA] Chaves criptograficas geradas automaticamente em .env")

_load_env()

app = Flask(__name__, static_folder='.')
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get("HTTPS", "0") == "1",
)

DATABASE = os.path.join(BASE_DIR, "contratos.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
CONFIG_FILE = os.path.join(BASE_DIR, 'config_email.json')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─── BANCO DE DADOS ──────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        g.db = db
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def query_db(sql, params=(), one=False):
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(r) for r in rows]

def execute_db(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur.lastrowid

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if os.environ.get("HTTPS", "0") == "1":
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data:; font-src 'self' data: https://fonts.gstatic.com; connect-src 'self'"
    return response

@app.before_request
def session_timeout():
    if 'user_id' not in session:
        return
    max_hours = int(os.environ.get("SESSION_TIMEOUT_HOURS", "8"))
    max_seconds = max_hours * 3600
    now = datetime.utcnow().timestamp()
    last_active = session.get('_last_active')
    if last_active and (now - last_active) > max_seconds:
        session.clear()
        return jsonify({"ok": False, "erro": "Sessao expirada. Faca login novamente."}), 401
    session['_last_active'] = now

def uid():
    return uuid.uuid4().hex

def hash_password(text):
    return generate_password_hash(text)

def check_password(hash_val, text):
    return check_password_hash(hash_val, text)

def _get_cipher():
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        os.environ['ENCRYPTION_KEY'] = key
    key = key.encode() if isinstance(key, str) else key
    return Fernet(key)

def encrypt_text(text):
    if not text:
        return ""
    return _get_cipher().encrypt(text.encode()).decode()

def _try_decrypt_old(encrypted):
    old_secrets = [app.secret_key]
    old_key_file = os.path.join(BASE_DIR, 'script11', '.env')
    if os.path.exists(old_key_file):
        with open(old_key_file) as f:
            for line in f:
                if line.startswith('SECRET_KEY='):
                    val = line.strip().partition('=')[2]
                    if val:
                        old_secrets.append(val)
    for secret in old_secrets:
        try:
            old_salt = b'contratos_salt_fixo'
            old_kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=old_salt, iterations=100000)
            old_key = base64.urlsafe_b64encode(old_kdf.derive(secret.encode()))
            return Fernet(old_key).decrypt(encrypted.encode()).decode()
        except Exception:
            continue
    return None

def decrypt_text(encrypted):
    if not encrypted:
        return ""
    try:
        return _get_cipher().decrypt(encrypted.encode()).decode()
    except Exception:
        return _try_decrypt_old(encrypted) or encrypted

# ─── INICIALIZAÇÃO DO BANCO ─────────────────────────────────────────────────

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS contracts (
        id TEXT PRIMARY KEY,
        numero TEXT UNIQUE NOT NULL,
        fornecedor TEXT NOT NULL,
        cnpj TEXT,
        objeto TEXT NOT NULL,
        valor_total REAL NOT NULL DEFAULT 0,
        inicio TEXT NOT NULL,
        fim TEXT NOT NULL,
        tem_parcelas INTEGER NOT NULL DEFAULT 0,
        qtd_parcelas INTEGER,
        valor_parcela REAL,
        dia_vencimento INTEGER,
        responsavel TEXT,
        setor TEXT,
        obs TEXT,
        arquivo_contrato TEXT,
        created_by INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at TEXT,
        FOREIGN KEY (created_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY,
        contract_id TEXT NOT NULL,
        descricao TEXT NOT NULL,
        vencimento TEXT NOT NULL,
        valor REAL NOT NULL DEFAULT 0,
        contrato_num TEXT,
        data_pagamento TEXT,
        valor_pago REAL,
        forma_pagamento TEXT,
        status TEXT NOT NULL DEFAULT 'pendente',
        obs TEXT,
        comprovante TEXT,
        created_by INTEGER,
        paid_by INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
        FOREIGN KEY (created_by) REFERENCES users(id),
        FOREIGN KEY (paid_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS additives (
        id TEXT PRIMARY KEY,
        contract_id TEXT NOT NULL,
        numero TEXT,
        data_aditivo TEXT NOT NULL,
        tipo TEXT NOT NULL,
        nova_data_fim TEXT,
        acrescimo_valor REAL,
        descricao TEXT NOT NULL,
        arquivo_contrato TEXT,
        created_by INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
        FOREIGN KEY (created_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS companies (
        id TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        cnpj TEXT DEFAULT '',
        criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        entity TEXT NOT NULL,
        entity_id TEXT,
        details TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS destinatarios (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        nome TEXT DEFAULT '',
        empresa_ids TEXT DEFAULT '[]',
        criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """)
    for col, tbl in [
        ('arquivo_contrato', 'contracts'), ('tipo', 'contracts'), ('empresa_id', 'contracts'), ('forma_pagamento', 'contracts'),
        ('comprovante', 'payments'), ('contrato_num', 'payments'),
        ('arquivo_contrato', 'additives'),
    ]:
        try:
            cols = [r['name'] for r in db.execute(f"PRAGMA table_info({tbl})").fetchall()]
            if col not in cols:
                db.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} TEXT")
                db.commit()
        except Exception:
            pass
    admin_exists = query_db("SELECT id FROM users WHERE username=?", ("admin",), one=True)
    admin_pass_env = os.environ.get("ADMIN_PASSWORD")
    if not admin_exists:
        admin_pass = admin_pass_env or secrets.token_urlsafe(12)
        if not admin_pass_env:
            print("\n" + "=" * 60)
            print("  ATENCAO: Senha do admin nao definida em ADMIN_PASSWORD!")
            print(f"  Senha gerada automaticamente: {admin_pass}")
            print("  Defina ADMIN_PASSWORD no .env para usar uma senha personalizada.")
            print("=" * 60 + "\n")
        execute_db(
            "INSERT INTO users (username,full_name,password_hash,role) VALUES(?,?,?,?)",
            ("admin", "Administrador", hash_password(admin_pass), "admin")
        )
    elif admin_pass_env:
        execute_db(
            "UPDATE users SET password_hash=? WHERE username=?",
            (hash_password(admin_pass_env), "admin")
        )
        print("[SEGURANCA] Senha do admin atualizada via ADMIN_PASSWORD do .env")
    elif admin_exists:
        print("[INFO] Admin ja existe. Para alterar a senha, defina ADMIN_PASSWORD no .env e reinicie.")

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def audit(action, entity, entity_id="", details=""):
    execute_db(
        "INSERT INTO audit_log (user_id,action,entity,entity_id,details) VALUES(?,?,?,?,?)",
        (session.get("user_id"), action, entity, entity_id, details)
    )

def money(v):
    try:
        return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"

def datefmt(s):
    if not s:
        return "-"
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(s)

def today():
    return date.today()

def safe_float(value, default=0.0):
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except Exception:
        return default

def safe_int(value, default=None):
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(value)
    except Exception:
        return default

def validar_cpf_cnpj(valor):
    nums = re.sub(r'\D', '', str(valor))
    if len(nums) == 11:
        if nums == nums[0] * 11:
            return False
        s1 = sum(int(nums[i]) * (10 - i) for i in range(9))
        d1 = (s1 * 10 % 11) % 11
        s2 = sum(int(nums[i]) * (11 - i) for i in range(10))
        d2 = (s2 * 10 % 11) % 11
        return int(nums[9]) == d1 and int(nums[10]) == d2
    if len(nums) == 14:
        if nums == nums[0] * 14:
            return False
        p1 = [5,4,3,2,9,8,7,6,5,4,3,2]
        s1 = sum(int(nums[i]) * p1[i] for i in range(12))
        d1 = 11 - (s1 % 11)
        if d1 >= 10: d1 = 0
        p2 = [6,5,4,3,2,9,8,7,6,5,4,3,2]
        s2 = sum(int(nums[i]) * p2[i] for i in range(13))
        d2 = 11 - (s2 % 11)
        if d2 >= 10: d2 = 0
        return int(nums[12]) == d1 and int(nums[13]) == d2
    return True

def contract_status(fim):
    try:
        fim_d = datetime.strptime(str(fim)[:10], "%Y-%m-%d").date()
        return "Ativo" if fim_d >= today() else "Vencido"
    except Exception:
        return "Indefinido"

def payment_state(p):
    if p.get("data_pagamento"):
        return "Pago"
    try:
        venc = datetime.strptime(str(p["vencimento"])[:10], "%Y-%m-%d").date()
        return "Atrasado" if venc < today() else "Pendente"
    except Exception:
        return "Pendente"

def add_months(source_date, months, day=None):
    year = source_date.year + ((source_date.month - 1 + months) // 12)
    month = ((source_date.month - 1 + months) % 12) + 1
    last_day = calendar.monthrange(year, month)[1]
    chosen_day = min(day if day else source_date.day, last_day)
    return date(year, month, chosen_day)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xls', 'xlsx'}

MAX_FILE_MB = int(os.environ.get("MAX_UPLOAD_MB", "10"))
MAX_BASE64_LEN = MAX_FILE_MB * 15 * 1024 * 1024 // 10

def validate_file_data(obj):
    if not obj or not isinstance(obj, dict):
        return True
    data = obj.get('data', '')
    if len(data) > MAX_BASE64_LEN:
        return False
    return True

# ─── ROTAS ESTÁTICAS ────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/extrair')
def serve_extract():
    return send_from_directory(".", "extract.html")

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/<path:filename>')
def static_files(filename):
    if filename.startswith('api/') or filename.startswith('uploads/'):
        return jsonify({"ok": False, "erro": "Nao encontrado"}), 404
    return send_from_directory('.', filename)

# ─── API DE AUTENTICAÇÃO ────────────────────────────────────────────────────

@app.route('/api/csrf-token')
def api_csrf_token():
    return jsonify({"csrf_token": generate_csrf_token()})

@app.route('/api/me')
def api_me():
    if 'user_id' not in session:
        return jsonify({"ok": False, "user": None}), 401
    user = query_db("SELECT id, username, full_name, role FROM users WHERE id=?", (session['user_id']), one=True)
    return jsonify({"ok": True, "user": user, "csrf_token": generate_csrf_token()})

login_attempts = {}

# ─── CSRF ────────────────────────────────────────────────────────────────────
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf():
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return True
    token = request.headers.get('X-CSRF-Token') or (request.get_json(silent=True) or {}).get('csrf_token')
    if not token or token != session.get('csrf_token'):
        return False
    return True

# ─── CSRF ────────────────────────────────────────────────────────────────────

@app.route('/api/login', methods=['POST'])
def api_login():
    ip = request.remote_addr or 'unknown'
    now = datetime.now()
    if ip in login_attempts:
        attempts, block_until = login_attempts[ip]
        if block_until and now < block_until:
            return jsonify({"ok": False, "erro": "Muitas tentativas. Aguarde 30 segundos."}), 429
        if block_until and now - block_until > timedelta(seconds=30):
            login_attempts[ip] = (0, None)
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    user = query_db("SELECT * FROM users WHERE username=? AND active=1", (username,), one=True)
    if user and check_password(user['password_hash'], password):
        login_attempts.pop(ip, None)
        session.update({
            'user_id': user['id'], 'username': user['username'],
            'full_name': user['full_name'], 'role': user['role']
        })
        audit("LOGIN", "user", str(user['id']), f"Login: {user['username']}")
        return jsonify({
            "ok": True,
            "user": {"id": user['id'], "username": user['username'], "full_name": user['full_name'], "role": user['role']}
        })
    attempts, _ = login_attempts.get(ip, (0, None))
    attempts += 1
    block_until = now + timedelta(seconds=30) if attempts >= 5 else None
    login_attempts[ip] = (attempts, block_until)
    return jsonify({"ok": False, "erro": "Usuário ou senha incorretos!"}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    audit("LOGOUT", "user", str(session.get('user_id')), f"Logout: {session.get('username')}")
    session.clear()
    return jsonify({"ok": True})

# ─── API DE SINCRONIA ───────────────────────────────────────────────────────

# ─── API DE USUARIOS ──────────────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
def api_users_list():
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
    users = query_db("SELECT id, username, full_name, role, active, created_at FROM users ORDER BY id")
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
def api_users_create():
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
    admin_err = require_admin()
    if admin_err:
        return admin_err
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    full_name = data.get('full_name', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'user').strip()
    if not username or not full_name or not password:
        return jsonify({"ok": False, "erro": "Preencha todos os campos"}), 400
    if query_db("SELECT id FROM users WHERE username=?", (username,), one=True):
        return jsonify({"ok": False, "erro": "Usuario ja existe"}), 400
    user_id = execute_db(
        "INSERT INTO users (username,full_name,password_hash,role) VALUES (?,?,?,?)",
        (username, full_name, hash_password(password), role)
    )
    audit("CREATE", "user", "", f"Usuario {username} criado por {session.get('username')}")
    return jsonify({"ok": True, "user": {"id": user_id}})

@app.route('/api/users/<int:uid>', methods=['PUT', 'DELETE'])
def api_users_modify(uid):
    try:
        if not validate_csrf():
            return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
        if 'user_id' not in session:
            return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
        admin_err = require_admin()
        if admin_err:
            return admin_err
        if request.method == 'DELETE':
            if uid == 1:
                return jsonify({"ok": False, "erro": "Nao e possivel inativar o usuario admin principal."}), 400
            execute_db("UPDATE users SET active=0 WHERE id=?", (uid,))
            audit("INACTIVATE", "user", str(uid), f"Usuario {uid} inativado por {session.get('username')}")
            return jsonify({"ok": True})
        data = request.get_json(silent=True) or {}
        full_name = data.get('full_name', '').strip()
        role = data.get('role', 'user').strip()
        active = 1 if data.get('active', True) else 0
        execute_db("UPDATE users SET full_name=?, role=?, active=? WHERE id=?", (full_name, role, active, uid))
        audit("UPDATE", "user", str(uid), f"Usuario {uid} atualizado por {session.get('username')}")
        return jsonify({"ok": True})
    except Exception as e:
        app.logger.error("Erro ao modificar usuario: %s", traceback.format_exc())
        err_msg = "Usuario possui vinculos com contratos, pagamentos ou registros de auditoria. Remova os vinculos antes de excluir." if "FOREIGN KEY constraint failed" in str(e) else "Erro interno do servidor"
        return jsonify({"ok": False, "erro": err_msg}), 400

def require_admin():
    if session.get('role') != 'admin':
        return jsonify({"ok": False, "erro": "Acesso restrito ao administrador"}), 403
    return None

# ─── API DE EXCLUSAO ─────────────────────────────────────────────────────────

@app.route('/api/contracts/<contract_id>', methods=['DELETE'])
def api_delete_contract(contract_id):
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
    admin_err = require_admin()
    if admin_err:
        return admin_err
    execute_db("DELETE FROM payments WHERE contract_id=?", (contract_id,))
    execute_db("DELETE FROM additives WHERE contract_id=?", (contract_id,))
    execute_db("DELETE FROM contracts WHERE id=?", (contract_id,))
    audit("DELETE", "contract", contract_id, f"Contrato {contract_id} excluido por {session.get('username')}")
    return jsonify({"ok": True})

@app.route('/api/payments/<payment_id>', methods=['DELETE'])
def api_delete_payment(payment_id):
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
    admin_err = require_admin()
    if admin_err:
        return admin_err
    execute_db("DELETE FROM payments WHERE id=?", (payment_id,))
    audit("DELETE", "payment", payment_id, f"Pagamento {payment_id} excluido por {session.get('username')}")
    return jsonify({"ok": True})

# ─── API DE SINCRONIA ───────────────────────────────────────────────────────

@app.route('/api/sync', methods=['GET'])
def api_sync_get():
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
    contratos = query_db("SELECT * FROM contracts ORDER BY created_at DESC")
    pagamentos = query_db("SELECT * FROM payments ORDER BY vencimento ASC")
    usuarios = query_db("SELECT id, username, full_name, role, created_at FROM users ORDER BY id")
    aditivos = query_db("SELECT * FROM additives ORDER BY created_at ASC")
    empresas = query_db("SELECT * FROM companies ORDER BY nome ASC")
    destinatarios = query_db("SELECT * FROM destinatarios ORDER BY criado_em ASC")
    return jsonify({"contratos": contratos, "pagamentos": pagamentos, "usuarios": usuarios, "aditivos": aditivos, "empresas": empresas, "destinatarios": destinatarios})

@app.route('/api/sync', methods=['POST'])
def api_sync_post():
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({"ok": False, "erro": "JSON invalido ou vazio."}), 400
    importados = {"contratos": 0, "pagamentos": 0, "aditivos": 0, "ignorados": 0}

    for c in dados.get("contratos", []):
        cid = (c.get("id") or "").strip()
        numero = (c.get("numero") or "").strip()
        if not cid or not numero:
            importados["ignorados"] += 1
            continue
        existing = query_db("SELECT id FROM contracts WHERE id=?", (cid,), one=True)
        tem_parcelas = 1 if c.get("temParcelas") else 0
        pgto = c.get("pgtoConfig") or {}
        if c.get("arquivo") and not validate_file_data(c["arquivo"]):
            return jsonify({"ok": False, "erro": f"Arquivo do contrato {numero} excede {MAX_FILE_MB}MB."}), 400
        arquivo_json = json.dumps(c["arquivo"], ensure_ascii=False) if c.get("arquivo") else None
        vals = (
            numero, (c.get("parte") or "").strip(), (c.get("doc") or "").strip(),
            (c.get("objeto") or "").strip(), float(c.get("valor") or 0),
            (c.get("inicio") or "").strip(), (c.get("fim") or "").strip(),
            tem_parcelas, pgto.get("qtdParcelas"), safe_float(pgto.get("valorParcela")),
            pgto.get("diaVenc"), (c.get("responsavel") or "").strip(),
            (c.get("setor") or "").strip(), (c.get("obs") or "").strip(),
            c.get("tipo"), c.get("empresaId"), pgto.get("forma"),
            arquivo_json
        )
        if existing:
            execute_db("""
                UPDATE contracts SET numero=?,fornecedor=?,cnpj=?,objeto=?,
                    valor_total=?,inicio=?,fim=?,tem_parcelas=?,qtd_parcelas=?,
                    valor_parcela=?,dia_vencimento=?,responsavel=?,setor=?,obs=?,
                    tipo=?,empresa_id=?,forma_pagamento=?,arquivo_contrato=?,
                    updated_at=datetime('now','localtime')
                WHERE id=?
            """, vals + (cid,))
        else:
            execute_db("""
                INSERT INTO contracts
                (id,numero,fornecedor,cnpj,objeto,valor_total,inicio,fim,
                 tem_parcelas,qtd_parcelas,valor_parcela,dia_vencimento,
                 responsavel,setor,obs,tipo,empresa_id,forma_pagamento,
                 arquivo_contrato,created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cid,) + vals + (1,))
        importados["contratos"] += 1

        if c.get("aditivos"):
            execute_db("DELETE FROM additives WHERE contract_id=?", (cid,))
            for a in c["aditivos"]:
                if a.get("arquivo") and not validate_file_data(a["arquivo"]):
                    return jsonify({"ok": False, "erro": f"Arquivo de aditivo excede {MAX_FILE_MB}MB."}), 400
                arquivo_json = json.dumps(a["arquivo"], ensure_ascii=False) if a.get("arquivo") else None
                execute_db("""
                    INSERT INTO additives
                    (id,contract_id,numero,data_aditivo,tipo,
                     nova_data_fim,acrescimo_valor,descricao,arquivo_contrato,created_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (
                    a.get("id") or uid(), cid, a.get("numero"),
                    a.get("data") or "", a.get("tipo"),
                    a.get("novaData"), a.get("novoValor"),
                    a.get("objeto"), arquivo_json, 1
                ))
                importados["aditivos"] += 1

    pagamentos_dados = dados.get("pagamentos", [])
    contratos_pag = set()
    for p in pagamentos_dados:
        cid = (p.get("contratoId") or "").strip()
        if cid:
            contratos_pag.add(cid)

    for cid in contratos_pag:
        execute_db("DELETE FROM payments WHERE contract_id=?", (cid,))

    for p in pagamentos_dados:
        pid = (p.get("id") or "").strip() or uid()
        cid = (p.get("contratoId") or "").strip()
        descricao = (p.get("descricao") or "").strip()
        vencimento = (p.get("vencimento") or "").strip()
        if not cid or not vencimento:
            importados["ignorados"] += 1
            continue
        valor = float(p.get("valor") or 0)
        data_pagamento = (p.get("dataPagamento") or "").strip() or None
        valor_pago = safe_float(p.get("valorPago")) or (valor if data_pagamento else None)
        forma_pgto = (p.get("formaPgto") or "").strip() or None
        obs = (p.get("obs") or "").strip()
        status = "pago" if data_pagamento else "pendente"
        if p.get("comprovante") and not validate_file_data(p["comprovante"]):
            return jsonify({"ok": False, "erro": f"Comprovante de pagamento excede {MAX_FILE_MB}MB."}), 400
        comprovante_json = json.dumps(p["comprovante"], ensure_ascii=False) if p.get("comprovante") else None
        contrato_num = (p.get("contratoNum") or "").strip() or None
        execute_db("""
            INSERT INTO payments
            (id,contract_id,descricao,vencimento,valor,contrato_num,data_pagamento,valor_pago,
             forma_pagamento,status,obs,comprovante,created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (pid, cid, descricao, vencimento, valor, contrato_num,
              data_pagamento, valor_pago, forma_pgto, status, obs,
              comprovante_json, 1))
        importados["pagamentos"] += 1

    for d in dados.get("destinatarios", []):
        did = (d.get("id") or "").strip()
        email = (d.get("email") or "").strip()
        if not did or not email:
            importados["ignorados"] += 1
            continue
        nome = (d.get("nome") or "").strip()
        empresa_ids = d.get("empresaIds", [])
        existing = query_db("SELECT id FROM destinatarios WHERE id=?", (did,), one=True)
        if existing:
            execute_db("UPDATE destinatarios SET email=?, nome=?, empresa_ids=? WHERE id=?",
                       (email, nome, json.dumps(empresa_ids, ensure_ascii=False), did))
        else:
            execute_db("INSERT INTO destinatarios (id, email, nome, empresa_ids) VALUES (?,?,?,?)",
                       (did, email, nome, json.dumps(empresa_ids, ensure_ascii=False)))
        importados["destinatarios"] = importados.get("destinatarios", 0) + 1

    audit("SYNC", "system", "", f"Sincronizacao concluida: {importados}")
    return jsonify({"ok": True, "importados": importados})

# ─── API DE EMPRESAS ─────────────────────────────────────────────────────────

@app.route('/api/companies', methods=['GET', 'POST'])
def api_companies():
    if request.method == 'GET':
        return jsonify(query_db("SELECT * FROM companies ORDER BY nome ASC"))
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
    admin_err = require_admin()
    if admin_err:
        return admin_err
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({"ok": False, "erro": "JSON invalido."}), 400
    cid = dados.get('id') or uid()
    nome = (dados.get('nome') or '').strip()
    if not nome:
        return jsonify({"ok": False, "erro": "Nome da empresa e obrigatorio."}), 400
    cnpj = (dados.get('cnpj') or '').strip()
    existing = query_db("SELECT id FROM companies WHERE id=?", (cid,), one=True)
    if existing:
        execute_db("UPDATE companies SET nome=?, cnpj=? WHERE id=?", (nome, cnpj, cid))
    else:
        execute_db("INSERT INTO companies (id, nome, cnpj) VALUES (?,?,?)", (cid, nome, cnpj))
    return jsonify({"ok": True, "id": cid})

@app.route('/api/companies/<cid>', methods=['DELETE'])
def api_delete_company(cid):
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
    admin_err = require_admin()
    if admin_err:
        return admin_err
    execute_db("DELETE FROM companies WHERE id=?", (cid,))
    return jsonify({"ok": True})

# ─── API DE E-MAIL / LEMBRETE ───────────────────────────────────────────────

def ler_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    if cfg.get('email_senha') and not cfg.get('email_senha_enc'):
        cfg['email_senha_enc'] = encrypt_text(cfg['email_senha'])
        cfg['email_senha'] = decrypt_text(cfg['email_senha_enc'])
    elif cfg.get('email_senha_enc'):
        decrypted = decrypt_text(cfg['email_senha_enc'])
        if decrypted and decrypted != cfg['email_senha_enc']:
            cfg['email_senha'] = decrypted
            new_enc = encrypt_text(decrypted)
            if new_enc != cfg['email_senha_enc']:
                cfg['email_senha_enc'] = new_enc
                salvar_config(cfg)
                cfg['email_senha'] = decrypted
        else:
            cfg['email_senha'] = ''
            app.logger.warning("Falha ao descriptografar senha de email. Reconfigure o email no sistema.")
    else:
        cfg['email_senha'] = os.environ.get("EMAIL_PASSWORD", "")
    return cfg

def salvar_config(cfg):
    if cfg and 'email_senha' in cfg:
        if cfg['email_senha'] and cfg['email_senha'] != '********':
            cfg['email_senha_enc'] = encrypt_text(cfg['email_senha'])
        cfg['email_senha'] = '********'
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

@app.route('/api/config-email', methods=['GET', 'POST'])
def api_config_email():
    if request.method == 'POST':
        if not validate_csrf():
            return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
        if 'user_id' not in session:
            return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
        cfg = request.json
        old_cfg_raw = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                old_cfg_raw = json.load(f)
        if cfg and 'email_senha' in cfg:
            pwd = cfg['email_senha']
            if pwd == '********' or not pwd.strip():
                cfg['email_senha'] = old_cfg_raw.get('email_senha', '')
                cfg['email_senha_enc'] = old_cfg_raw.get('email_senha_enc', '')
        salvar_config(cfg)
        return jsonify({"ok": True})
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    if cfg.get('email_senha_enc'):
        cfg['email_senha'] = '********'
    return jsonify(cfg)

def processar_pagamentos(contratos, pagamentos, hoje, empresa_nomes=None):
    if empresa_nomes is None:
        empresa_nomes = {}
    vencidos, vence_hoje, vence_amanha = [], [], []
    for p in pagamentos:
        if p.get("data_pagamento"):
            continue
        venc = (p.get("vencimento") or "")[:10]
        try:
            dv = datetime.strptime(venc, '%Y-%m-%d').date()
        except Exception:
            continue
        c = next((c2 for c2 in contratos if c2.get("id") == p.get("contract_id")), None)
        contrato_num = p.get('contract_num') or (c.get('numero', '?') if c else '?')
        empresa_id = c.get('empresa_id', '') if c else ''
        empresa_nome = empresa_nomes.get(empresa_id, '') if empresa_id else ''
        info = {
            'numero_contrato': contrato_num,
            'empresa': empresa_nome or '—',
            'parte': c.get('fornecedor', '?') if c else '?',
            'descricao': p.get('descricao', '?'),
            'vencimento': datefmt(venc),
            'valor': money(p.get('valor', 0))
        }
        if dv < hoje:
            info['dias'] = (hoje - dv).days
            vencidos.append(info)
        elif dv == hoje:
            vence_hoje.append(info)
        elif (dv - hoje).days == 1:
            vence_amanha.append(info)
    return vencidos, vence_hoje, vence_amanha


def processar_contratos_vencidos(contratos, hoje):
    vencidos = []
    for c in contratos:
        fim = (c.get("fim") or "")[:10]
        try:
            df = datetime.strptime(fim, '%Y-%m-%d').date()
        except Exception:
            continue
        dias = (df - hoje).days
        if dias >= 0:
            continue
        vencidos.append({
            'numero': c.get('numero', '?'),
            'fornecedor': c.get('fornecedor', '?'),
            'objeto': c.get('objeto', '?'),
            'fim': datefmt(fim),
            'dias_passados': abs(dias)
        })
    return vencidos


def processar_contratos_a_vencer(contratos, hoje):
    grupos = {"d35": [], "d30": [], "d15": [], "d0_14": []}
    for c in contratos:
        fim = (c.get("fim") or "")[:10]
        try:
            df = datetime.strptime(fim, '%Y-%m-%d').date()
        except Exception:
            continue
        dias = (df - hoje).days
        if dias < 0:
            continue
        info = {
            'numero': c.get('numero', '?'),
            'fornecedor': c.get('fornecedor', '?'),
            'objeto': c.get('objeto', '?'),
            'fim': datefmt(fim),
            'dias': dias
        }
        if 31 <= dias <= 35:
            grupos["d35"].append(info)
        elif 16 <= dias <= 30:
            grupos["d30"].append(info)
        elif dias == 15:
            grupos["d15"].append(info)
        elif 0 <= dias <= 14:
            grupos["d0_14"].append(info)
    return grupos


def montar_html_pagamentos(vencidos, vence_hoje, vence_amanha, titulo_adicional=""):
    partes = []
    if vencidos or vence_hoje or vence_amanha:
        html_content = f'<h2 style="color:#1a3c5e">Lembrete de Vencimentos{titulo_adicional}</h2>'
        if vencidos:
            html_content += """<h3 style="color:#c0392b">VENCIDOS</h3><table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px">
            <tr style="background:#ffe1e1"><th>Contrato</th><th>Empresa</th><th>Fornecedor</th><th>Parcela</th><th>Vencimento</th><th>Valor</th><th>Dias</th></tr>"""
            for v in vencidos:
                html_content += f'<tr><td>{html.escape(v["numero_contrato"])}</td><td>{html.escape(v["empresa"])}</td><td>{html.escape(v["parte"])}</td><td>{html.escape(v["descricao"])}</td><td>{html.escape(v["vencimento"])}</td><td>R$ {html.escape(v["valor"])}</td><td>{v["dias"]} dia(s)</td></tr>'
            html_content += '</table>'
        if vence_hoje:
            html_content += """<h3 style="color:#d4820a">VENCEM HOJE</h3><table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px">
            <tr style="background:#fff3cd"><th>Contrato</th><th>Empresa</th><th>Fornecedor</th><th>Parcela</th><th>Vencimento</th><th>Valor</th></tr>"""
            for v in vence_hoje:
                html_content += f'<tr><td>{html.escape(v["numero_contrato"])}</td><td>{html.escape(v["empresa"])}</td><td>{html.escape(v["parte"])}</td><td>{html.escape(v["descricao"])}</td><td>{html.escape(v["vencimento"])}</td><td>R$ {html.escape(v["valor"])}</td></tr>'
            html_content += '</table>'
        if vence_amanha:
            html_content += """<h3 style="color:#24527a">VENCEM AMANHA</h3><table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px">
            <tr style="background:#eef6ff"><th>Contrato</th><th>Empresa</th><th>Fornecedor</th><th>Parcela</th><th>Vencimento</th><th>Valor</th></tr>"""
            for v in vence_amanha:
                html_content += f'<tr><td>{html.escape(v["numero_contrato"])}</td><td>{html.escape(v["empresa"])}</td><td>{html.escape(v["parte"])}</td><td>{html.escape(v["descricao"])}</td><td>{html.escape(v["vencimento"])}</td><td>R$ {html.escape(v["valor"])}</td></tr>'
            html_content += '</table>'
        partes.append(html_content)
    return partes


def montar_html_contratos_vencidos(vencidos, titulo_adicional=""):
    if not vencidos:
        return []
    html_content = f'<h2 style="color:#c0392b">Contratos Vencidos{titulo_adicional}</h2>'
    html_content += """<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px">
    <tr style="background:#ffe1e1"><th>Contrato</th><th>Fornecedor</th><th>Objeto</th><th>Termino</th><th>Dias Vencido</th></tr>"""
    for c in vencidos:
        html_content += f'<tr><td>{html.escape(c["numero"])}</td><td>{html.escape(c["fornecedor"])}</td><td>{html.escape(c["objeto"])}</td><td>{html.escape(c["fim"])}</td><td>{c["dias_passados"]} dia(s)</td></tr>'
    html_content += '</table>'
    return [html_content]


def montar_html_contratos_a_vencer(grupos, titulo_adicional=""):
    if not any(grupos.values()):
        return []
    html_content = f'<h2 style="color:#1a3c5e">Aviso de Vencimento de Contratos{titulo_adicional}</h2>'
    secoes = [
        ('d35', 'ENTRE 31 E 35 DIAS PARA O TERMINO', '#24527a', '#eef6ff'),
        ('d30', 'ENTRE 16 E 30 DIAS PARA O TERMINO', '#d4820a', '#fff3cd'),
        ('d15', 'FALTAM 15 DIAS PARA O TERMINO', '#c0392b', '#ffe1e1'),
        ('d0_14', 'MENOS DE 15 DIAS PARA O TERMINO — ATENCAO DIARIA', '#b71c1c', '#ffd7d7'),
    ]
    for chave, titulo, cor_borda, cor_fundo in secoes:
        grupo = grupos[chave]
        if not grupo:
            continue
        html_content += f"""<h3 style="color:{cor_borda}">{titulo}</h3>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px">
        <tr style="background:{cor_fundo}"><th>Contrato</th><th>Fornecedor</th><th>Objeto</th><th>Termino</th><th>Dias</th></tr>"""
        for c in grupo:
            html_content += f'<tr><td>{html.escape(c["numero"])}</td><td>{html.escape(c["fornecedor"])}</td><td>{html.escape(c["objeto"])}</td><td>{html.escape(c["fim"])}</td><td>{c["dias"]} dia(s)</td></tr>'
        html_content += '</table>'
    return [html_content]


def enviar_email(cfg, html, assunto, destinatario):
    msg = MIMEText(html, 'html', 'utf-8')
    msg['Subject'] = assunto
    msg['From'] = cfg['email_remetente']
    msg['To'] = destinatario
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP(cfg.get('smtp_server', 'smtp.gmail.com'), int(cfg.get('smtp_port', 587))) as server:
            server.starttls(context=ctx)
            server.login(cfg['email_remetente'], cfg['email_senha'])
            server.sendmail(msg['From'], [d.strip() for d in destinatario.split(',') if d.strip()], msg.as_string().encode('utf-8'))
    except Exception as e:
        app.logger.error("ERRO EMAIL: %s", traceback.format_exc())
        raise


@app.route('/api/enviar-lembrete', methods=['POST'])
@app.route('/api/enviar-lembrete-pagamentos', methods=['POST'])
def api_enviar_lembrete_pagamentos():
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    cfg = ler_config()
    if not cfg.get('email_remetente') or not cfg.get('email_senha'):
        return jsonify({"ok": False, "erro": "Configure o e-mail primeiro."})

    body = request.get_json(silent=True) or {}
    empresas_lista = body.get('empresas', [])
    empresa_nomes = {e['id']: e['nome'] for e in empresas_lista if e.get('id') and e.get('nome')}
    destinatarios_data = body.get('destinatarios', [])

    contratos = query_db("SELECT * FROM contracts")
    pagamentos = query_db("SELECT * FROM payments")
    hoje = date.today()

    if not destinatarios_data:
        return jsonify({"ok": True, "msg": "Nenhum destinatario cadastrado para enviar lembretes."})

    enviados = 0
    erros = []

    for dest in destinatarios_data:
        email = dest.get('email', '').strip()
        if not email:
            continue
        empresa_ids = dest.get('empresaIds', [])
        dest_nome = dest.get('nome', '')
        emp_ids_set = set(empresa_ids) if empresa_ids else None
        contrato_ids_emp = {c['id'] for c in contratos if emp_ids_set is None or c.get('empresa_id') in emp_ids_set}
        emp_pagamentos = [p for p in pagamentos if p.get('contract_id') in contrato_ids_emp]
        vencidos, vence_hoje, vence_amanha = processar_pagamentos(contratos, emp_pagamentos, hoje, empresa_nomes)
        if not (vencidos or vence_hoje or vence_amanha):
            continue
        rotulo = f" - {dest_nome}" if dest_nome else ""
        partes = montar_html_pagamentos(vencidos, vence_hoje, vence_amanha, rotulo)
        html = f"""<html><body style="font-family:Arial,sans-serif;padding:20px">
        {''.join(partes)}
        <p style="color:#666;font-size:12px">Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}</p></body></html>"""
        try:
            enviar_email(cfg, html,
                         f'Lembrete de Pagamentos{rotulo} - {hoje.strftime("%d/%m/%Y")}',
                         email)
            enviados += 1
        except Exception as e:
            erros.append(f"{email}: {e}")

    if enviados == 0 and not erros:
        return jsonify({"ok": True, "msg": "Nenhum pagamento pendente para os destinatarios cadastrados."})

    partes = [f'{enviados} e-mail(s) enviado(s)']
    if erros:
        partes.append(f'Erros: {"; ".join(erros)}')
    return jsonify({"ok": True, "msg": '. '.join(partes)})


@app.route('/api/enviar-alertas-contratos', methods=['POST'])
def api_enviar_alertas_contratos():
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    cfg = ler_config()
    if not cfg.get('email_remetente') or not cfg.get('email_senha'):
        return jsonify({"ok": False, "erro": "Configure o e-mail primeiro."})

    body = request.get_json(silent=True) or {}
    destinatarios_data = body.get('destinatarios', [])

    contratos = query_db("SELECT * FROM contracts")
    hoje = date.today()

    if not destinatarios_data:
        return jsonify({"ok": True, "msg": "Nenhum destinatario cadastrado para enviar alertas."})

    enviados = 0
    erros = []

    for dest in destinatarios_data:
        email = dest.get('email', '').strip()
        if not email:
            continue
        empresa_ids = dest.get('empresaIds', [])
        dest_nome = dest.get('nome', '')
        emp_ids_set = set(empresa_ids) if empresa_ids else None
        emp_contratos = [c for c in contratos if emp_ids_set is None or c.get('empresa_id') in emp_ids_set]
        emp_vencidos = processar_contratos_vencidos(emp_contratos, hoje)
        emp_a_vencer = processar_contratos_a_vencer(emp_contratos, hoje)
        if not emp_vencidos and not any(emp_a_vencer.values()):
            continue
        rotulo = f" - {dest_nome}" if dest_nome else ""
        regioes = []
        regioes += montar_html_contratos_vencidos(emp_vencidos, rotulo)
        regioes += montar_html_contratos_a_vencer(emp_a_vencer, rotulo)
        emp_html = f"""<html><body style="font-family:Arial,sans-serif;padding:20px">
        {'<hr style="margin:24px 0">'.join(regioes)}
        <p style="color:#666;font-size:12px">Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}</p></body></html>"""
        try:
            enviar_email(cfg, emp_html,
                         f'Alertas de Contratos{rotulo} - {hoje.strftime("%d/%m/%Y")}',
                         email)
            enviados += 1
        except Exception as e:
            erros.append(f"{email}: {e}")

    if enviados == 0 and not erros:
        return jsonify({"ok": True, "msg": "Nenhum contrato pendente para os destinatarios cadastrados."})

    partes = [f'{enviados} e-mail(s) enviado(s)']
    if erros:
        partes.append(f'Erros: {"; ".join(erros)}')
    return jsonify({"ok": True, "msg": '. '.join(partes)})

# ─── SSL / HTTPS ─────────────────────────────────────────────────────────────

def _ensure_ssl_cert():
    cert_path = os.path.join(BASE_DIR, 'cert.pem')
    key_path = os.path.join(BASE_DIR, 'key.pem')
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path
    print("[SSL] Gerando certificado auto-assinado...")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u'Controle Contratos'),
    ])
    alt_names = [x509.DNSName(u'localhost'), x509.IPAddress(ipaddress.IPv4Address(u'127.0.0.1'))]
    try:
        hostname = socket.gethostname()
        alt_names.append(x509.DNSName(hostname))
        ip = socket.gethostbyname(hostname)
        if ip:
            alt_names.append(x509.IPAddress(ipaddress.IPv4Address(ip)))
    except Exception:
        pass
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(key, hashes.SHA256())
    )
    with open(key_path, 'wb') as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    with open(cert_path, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    print(f"[SSL] Certificado gerado: {cert_path}")
    return cert_path, key_path

# ─── INICIALIZAÇÃO ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    https_enabled = os.environ.get("HTTPS", "0") == "1"
    port = int(os.environ.get('PORT', 5000))
    try:
        with app.app_context():
            init_db()
        print("=" * 50)
        print("Sistema iniciado com sucesso!")
        if https_enabled:
            cert_path, key_path = _ensure_ssl_cert()
            protocol = "https"
            ssl_ctx = (cert_path, key_path)
        else:
            protocol = "http"
            ssl_ctx = None
        print(f"Acesse: {protocol}://127.0.0.1:{port}")
        print(f"       {protocol}://localhost:{port}")
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            print(f"       {protocol}://{ip}:{port}")
        except Exception:
            pass
        print("=" * 50)
        app.run(host='0.0.0.0', port=port, debug=debug_mode, ssl_context=ssl_ctx)
    except Exception as e:
        app.logger.error("Erro ao iniciar: %s", traceback.format_exc())
        print("\n" + "=" * 50)
        print("ERRO AO INICIAR:")
        print(str(e))
        print("=" * 50)
        input("\nAperte ENTER para fechar...")
