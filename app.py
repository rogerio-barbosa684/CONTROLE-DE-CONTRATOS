import os, re, sqlite3, uuid, calendar, smtplib, ssl, json, traceback, html, base64, secrets, socket, ipaddress, logging, io, requests, time
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
import fitz
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
import google.generativeai as genai
from extrator_contrato import extrair_resumo_contrato, formatar_resumo

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
LOG_FILE = os.path.join(BASE_DIR, 'erros.log')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    encoding='utf-8'
)
logging.getLogger().addHandler(logging.StreamHandler())

# ─── LIMPEZA AUTOMATICA DE LOGS (1 ano) ─────────────────────────────────
try:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding='utf-8') as f:
            linhas = f.readlines()
        if len(linhas) > 1000:
            um_ano_atras = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            novas = [l for l in linhas if l[:10] >= um_ano_atras]
            if len(novas) < len(linhas):
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    f.writelines(novas)
                print(f"[LOG] erros.log limpo: {(len(linhas)-len(novas))} linhas removidas")
except Exception:
    pass
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
    allowed_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    origin = request.headers.get('Origin')
    if origin and origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRF-Token'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
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
    session_pwd_changed = session.get('_password_changed_at')
    if session_pwd_changed is not None:
        user = query_db("SELECT password_changed_at FROM users WHERE id=?", (session['user_id'],), one=True)
        if user and user.get('password_changed_at'):
            if user['password_changed_at'] != session_pwd_changed:
                session.clear()
                return jsonify({"ok": False, "erro": "Sessao invalidada. Faca login novamente."}), 401

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
        email TEXT DEFAULT '',
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
    CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT UNIQUE NOT NULL,
        expires_at TEXT NOT NULL,
        used INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS sectors (
        id TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS user_setores (
        user_id INTEGER NOT NULL,
        setor_id TEXT NOT NULL,
        PRIMARY KEY (user_id, setor_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (setor_id) REFERENCES sectors(id)
    );
    """)
    for col, tbl in [
        ('arquivo_contrato', 'contracts'), ('tipo', 'contracts'), ('empresa_id', 'contracts'), ('forma_pagamento', 'contracts'),
        ('comprovante', 'payments'), ('contrato_num', 'payments'),
        ('arquivo_contrato', 'additives'),
        ('active', 'companies'), ('active', 'contracts'),
        ('email', 'users'), ('password_changed_at', 'users'),
        ('resumo', 'contracts'), ('resumo', 'additives'),
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

    # Cria setores padrao se nao existirem
    default_setores = ['Financeiro', 'RH', 'Juridico', 'Administrativo', 'TI', 'Comercial', 'Operacional', 'Fiscal']
    existing = query_db("SELECT id FROM sectors")
    if not existing:
        for nome in default_setores:
            execute_db("INSERT INTO sectors (id, nome) VALUES (?, ?)", (str(uuid.uuid4()), nome))
        print(f"[INFO] {len(default_setores)} setores padrao criados.")

    # Limpa audit_log com mais de 1 ano
    try:
        limite = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        db.execute("DELETE FROM audit_log WHERE created_at < ?", (limite,))
        db.commit()
    except Exception:
        pass

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def audit(action, entity, entity_id="", details=""):
    user = session.get("username", "desconhecido")
    execute_db(
        "INSERT INTO audit_log (user_id,action,entity,entity_id,details) VALUES(?,?,?,?,?)",
        (session.get("user_id"), action, entity, entity_id, details)
    )
    app.logger.info("AUDIT: %s - %s %s %s | %s", user, action, entity, entity_id, details)

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

def validar_senha_forte(senha):
    if len(senha) < 8:
        return False, "Senha deve ter no minimo 8 caracteres"
    if not re.search(r'[A-Z]', senha):
        return False, "Senha deve conter pelo menos 1 letra maiuscula"
    if not re.search(r'[a-z]', senha):
        return False, "Senha deve conter pelo menos 1 letra minuscula"
    if not re.search(r'[0-9]', senha):
        return False, "Senha deve conter pelo menos 1 numero"
    return True, ""

def validar_email_server(email):
    if not email:
        return True
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

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

# ─── API DE AUTENTICAÇÃO ────────────────────────────────────────────────────

@app.route('/api/csrf-token')
def api_csrf_token():
    return jsonify({"csrf_token": generate_csrf_token()})

@app.route('/api/me')
def api_me():
    if 'user_id' not in session:
        return jsonify({"ok": False, "user": None}), 401
    user = query_db("SELECT id, username, full_name, role FROM users WHERE id=?", (session['user_id'],), one=True)
    return jsonify({"ok": True, "user": user, "csrf_token": generate_csrf_token()})

@app.route('/api/change-password', methods=['POST'])
def api_change_password():
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    data = request.json or {}
    current_password = data.get('current_password') or ''
    new_password = data.get('new_password') or ''
    if not current_password or not new_password:
        return jsonify({"ok": False, "erro": "Senha atual e nova senha sao obrigatorias."}), 400
    user = query_db("SELECT id, password_hash FROM users WHERE id=?", (session['user_id'],), one=True)
    if not user:
        return jsonify({"ok": False, "erro": "Usuario nao encontrado."}), 404
    if not check_password(user['password_hash'], current_password):
        return jsonify({"ok": False, "erro": "Senha atual incorreta."}), 400
    if len(new_password) < 8:
        return jsonify({"ok": False, "erro": "A nova senha deve ter no minimo 8 caracteres."}), 400
    if not re.search(r'[A-Z]', new_password):
        return jsonify({"ok": False, "erro": "Nova senha deve conter pelo menos 1 letra maiuscula."}), 400
    if not re.search(r'[a-z]', new_password):
        return jsonify({"ok": False, "erro": "Nova senha deve conter pelo menos 1 letra minuscula."}), 400
    if not re.search(r'[0-9]', new_password):
        return jsonify({"ok": False, "erro": "Nova senha deve conter pelo menos 1 numero."}), 400
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    execute_db("UPDATE users SET password_hash=?, password_changed_at=? WHERE id=?",
               (hash_password(new_password), now, session['user_id']))
    audit('change_password', 'user', str(session['user_id']), 'Senha alterada pelo proprio usuario')
    return jsonify({"ok": True, "msg": "Senha alterada com sucesso!"})

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
            'full_name': user['full_name'], 'role': user['role'],
            '_password_changed_at': user.get('password_changed_at') or ''
        })
        audit("LOGIN", "user", str(user['id']), f"Login: {user['username']}")
        return jsonify({
            "ok": True,
            "user": {"id": user['id'], "username": user['username'], "full_name": user['full_name'], "role": user['role']},
            "csrf_token": generate_csrf_token()
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

# ─── API DE HISTÓRICO / AUDIT LOG ──────────────────────────────────────────

@app.route('/api/audit', methods=['GET'])
def api_audit_list():
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
    limit = min(int(request.args.get('limit', 50)), 200)
    logs = query_db(
        """SELECT a.id, a.action, a.entity, a.entity_id, a.details, a.created_at,
                  u.username as user_name
           FROM audit_log a
           LEFT JOIN users u ON a.user_id = u.id
           ORDER BY a.id DESC LIMIT ?""",
        (limit,)
    )
    return jsonify([dict(l) for l in logs])

# ─── API DE USUARIOS ──────────────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
def api_users_list():
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
    admin_err = require_admin()
    if admin_err:
        return admin_err
    users = query_db("SELECT id, username, full_name, email, role, active, created_at FROM users ORDER BY id")
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
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'user').strip()
    if not username or not full_name or not password:
        return jsonify({"ok": False, "erro": "Preencha todos os campos"}), 400
    if email and not validar_email_server(email):
        return jsonify({"ok": False, "erro": "Email invalido"}), 400
    senha_ok, senha_erro = validar_senha_forte(password)
    if not senha_ok:
        return jsonify({"ok": False, "erro": senha_erro}), 400
    if query_db("SELECT id FROM users WHERE username=?", (username,), one=True):
        return jsonify({"ok": False, "erro": "Usuario ja existe"}), 400
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    user_id = execute_db(
        "INSERT INTO users (username,full_name,email,password_hash,role,password_changed_at) VALUES (?,?,?,?,?,?)",
        (username, full_name, email, hash_password(password), role, now_str)
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
        email = data.get('email', '').strip()
        role = data.get('role', 'user').strip()
        active = 1 if data.get('active', True) else 0
        password = data.get('password', '').strip()
        if email and not validar_email_server(email):
            return jsonify({"ok": False, "erro": "Email invalido"}), 400
        if password:
            senha_ok, senha_erro = validar_senha_forte(password)
            if not senha_ok:
                return jsonify({"ok": False, "erro": senha_erro}), 400
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            execute_db("UPDATE users SET full_name=?, email=?, role=?, active=?, password_hash=?, password_changed_at=? WHERE id=?", (full_name, email, role, active, hash_password(password), now_str, uid))
        else:
            execute_db("UPDATE users SET full_name=?, email=?, role=?, active=? WHERE id=?", (full_name, email, role, active, uid))
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

@app.route('/api/contracts/<contract_id>', methods=['PUT', 'DELETE'])
def api_modify_contract(contract_id):
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401

    if request.method == 'DELETE':
        admin_err = require_admin()
        if admin_err:
            return admin_err
        execute_db("DELETE FROM payments WHERE contract_id=?", (contract_id,))
        execute_db("DELETE FROM additives WHERE contract_id=?", (contract_id,))
        execute_db("DELETE FROM contracts WHERE id=?", (contract_id,))
        audit("DELETE", "contract", contract_id, f"Contrato {contract_id} excluido por {session.get('username')}")
        return jsonify({"ok": True})

    dados = request.get_json(silent=True) or {}
    upd = {}
    if 'active' in dados:
        upd['active'] = 1 if dados['active'] not in (0, '0', False, None) else 0
    if upd:
        execute_db(f"UPDATE contracts SET {', '.join(f'{k}=?' for k in upd)} WHERE id=?", (*upd.values(), contract_id))
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
    for c in contratos:
        val = c.get('active')
        c['active'] = 1 if val is not None and val != 0 and val != '0' else 0
    pagamentos = query_db("SELECT * FROM payments ORDER BY vencimento ASC")
    usuarios = query_db("SELECT id, username, full_name, role, created_at FROM users ORDER BY id")
    aditivos = query_db("SELECT * FROM additives ORDER BY created_at ASC")
    empresas = query_db("SELECT * FROM companies ORDER BY nome ASC")
    for e in empresas:
        val = e.get('active')
        e['active'] = 1 if val is not None and val != 0 and val != '0' else 0
    destinatarios = query_db("SELECT * FROM destinatarios ORDER BY criado_em ASC")
    sectors = query_db("SELECT * FROM sectors ORDER BY nome ASC")
    for s in sectors:
        val = s.get('active')
        s['active'] = 1 if val is not None and val != 0 and val != '0' else 0
    return jsonify({"contratos": contratos, "pagamentos": pagamentos, "usuarios": usuarios, "aditivos": aditivos, "empresas": empresas, "destinatarios": destinatarios, "sectors": sectors})

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
        cnpj_val = (c.get("doc") or "").strip()
        if cnpj_val and not validar_cpf_cnpj(cnpj_val):
            return jsonify({"ok": False, "erro": f"CPF/CNPJ invalido no contrato {numero}: {cnpj_val}"}), 400
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

    for s in dados.get("sectors", []):
        sid = (s.get("id") or "").strip()
        nome = (s.get("nome") or "").strip()
        if not sid or not nome:
            importados["ignorados"] += 1
            continue
        active = 1 if s.get("active") not in (0, '0', False, None) else 0
        existing = query_db("SELECT id FROM sectors WHERE id=?", (sid,), one=True)
        if existing:
            execute_db("UPDATE sectors SET nome=?, active=? WHERE id=?", (nome, active, sid))
        else:
            execute_db("INSERT INTO sectors (id, nome, active) VALUES (?,?,?)", (sid, nome, active))
        importados["sectors"] = importados.get("sectors", 0) + 1

    audit("SYNC", "system", "", f"Sincronizacao concluida: {importados}")
    return jsonify({"ok": True, "importados": importados})

# ─── API DE EMPRESAS ─────────────────────────────────────────────────────────

@app.route('/api/companies', methods=['GET', 'POST'])
def api_companies():
    if request.method == 'GET':
        empresas = query_db("SELECT * FROM companies ORDER BY nome ASC")
        for e in empresas:
            val = e.get('active')
            e['active'] = 1 if val is not None and val != 0 and val != '0' else 0
        return jsonify(empresas)
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
    active = dados.get('active')
    existing = query_db("SELECT id FROM companies WHERE id=?", (cid,), one=True)
    if existing:
        if active is not None:
            execute_db("UPDATE companies SET nome=?, cnpj=?, active=? WHERE id=?", (nome, cnpj, 1 if active not in (0, '0', False, None) else 0, cid))
        else:
            execute_db("UPDATE companies SET nome=?, cnpj=? WHERE id=?", (nome, cnpj, cid))
    else:
        execute_db("INSERT INTO companies (id, nome, cnpj, active) VALUES (?,?,?,?)", (cid, nome, cnpj, 1 if active is None or active not in (0, '0', False, None) else 0))
    return jsonify({"ok": True, "id": cid})

@app.route('/api/companies/<cid>', methods=['PUT', 'DELETE'])
def api_modify_company(cid):
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401

    if request.method == 'DELETE':
        admin_err = require_admin()
        if admin_err:
            return admin_err
        execute_db("DELETE FROM companies WHERE id=?", (cid,))
        return jsonify({"ok": True})

    dados = request.get_json(silent=True) or {}
    upd = {}
    if 'active' in dados:
        upd['active'] = 1 if dados['active'] not in (0, '0', False, None) else 0
    if 'nome' in dados:
        upd['nome'] = (dados['nome'] or '').strip()
    if 'cnpj' in dados:
        upd['cnpj'] = (dados['cnpj'] or '').strip()
    if upd:
        execute_db(f"UPDATE companies SET {', '.join(f'{k}=?' for k in upd)} WHERE id=?", (*upd.values(), cid))
    return jsonify({"ok": True})

# ─── API DE SETORES ──────────────────────────────────────────────────────

@app.route('/api/sectors', methods=['GET', 'POST'])
def api_sectors():
    if request.method == 'GET':
        sectors = query_db("SELECT * FROM sectors ORDER BY nome ASC")
        for s in sectors:
            val = s.get('active')
            s['active'] = 1 if val is not None and val != 0 and val != '0' else 0
        return jsonify(sectors)
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
    sid = dados.get('id') or str(uuid.uuid4())
    nome = (dados.get('nome') or '').strip()
    if not nome:
        return jsonify({"ok": False, "erro": "Nome do setor e obrigatorio."}), 400
    active = dados.get('active')
    existing = query_db("SELECT id FROM sectors WHERE id=?", (sid,), one=True)
    if existing:
        if active is not None:
            execute_db("UPDATE sectors SET nome=?, active=? WHERE id=?", (nome, 1 if active not in (0, '0', False, None) else 0, sid))
        else:
            execute_db("UPDATE sectors SET nome=? WHERE id=?", (nome, sid))
    else:
        execute_db("INSERT INTO sectors (id, nome, active) VALUES (?,?,?)", (sid, nome, 1 if active is None or active not in (0, '0', False, None) else 0))
    return jsonify({"ok": True, "id": sid})

@app.route('/api/sectors/<sid>', methods=['PUT', 'DELETE'])
def api_modify_sector(sid):
    if not validate_csrf():
        return jsonify({"ok": False, "erro": "CSRF invalido"}), 403
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401
    if request.method == 'DELETE':
        admin_err = require_admin()
        if admin_err:
            return admin_err
        execute_db("DELETE FROM sectors WHERE id=?", (sid,))
        execute_db("DELETE FROM user_setores WHERE setor_id=?", (sid,))
        return jsonify({"ok": True})
    dados = request.get_json(silent=True) or {}
    upd = {}
    if 'active' in dados:
        upd['active'] = 1 if dados['active'] not in (0, '0', False, None) else 0
    if 'nome' in dados:
        upd['nome'] = (dados['nome'] or '').strip()
    if upd:
        execute_db(f"UPDATE sectors SET {', '.join(f'{k}=?' for k in upd)} WHERE id=?", (*upd.values(), sid))
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

# ─── FORGOT / RESET PASSWORD ────────────────────────────────────────────────

_forgot_password_attempts = {}

def _check_forgot_rate_limit(ip):
    now = time.time()
    attempts = _forgot_password_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < 60]
    _forgot_password_attempts[ip] = attempts
    if len(attempts) >= 5:
        return False
    attempts.append(now)
    return True

@app.route('/api/forgot-password', methods=['POST'])
def api_forgot_password():
    client_ip = request.remote_addr or 'unknown'
    if not _check_forgot_rate_limit(client_ip):
        return jsonify({"ok": False, "erro": "Muitas tentativas. Aguarde 1 minuto."}), 429
    data = request.json or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({"ok": False, "erro": "Informe o nome de usuario."}), 400
    user = query_db("SELECT id, username, full_name, email FROM users WHERE username=?", (username,), one=True)
    if not user:
        return jsonify({"ok": True, "msg": "Se o usuario existir, um email sera enviado."})
    token = secrets.token_hex(32)
    expires_at = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    execute_db("DELETE FROM password_resets WHERE user_id=?", (user['id'],))
    execute_db(
        "INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user['id'], token, expires_at)
    )
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        if cfg.get('email_senha_enc'):
            cfg['email_senha'] = decrypt_text(cfg['email_senha_enc'])
    email_to = user.get('email') or cfg.get('email_remetente')
    if cfg.get('email_remetente') and cfg.get('email_senha') and email_to:
        host = request.host or 'localhost:5000'
        scheme = 'https' if os.environ.get('HTTPS') == '1' else 'http'
        reset_url = f"{scheme}://{host}/?reset_token={token}"
        html = f"""
        <h2>Redefinição de Senha</h2>
        <p>Olá {html.escape(user['full_name'] or user['username'])},</p>
        <p>Clique no link abaixo para redefinir sua senha:</p>
        <p><a href="{reset_url}">{reset_url}</a></p>
        <p>Este link expira em 1 hora.</p>
        <p>Se você não solicitou esta redefinição, ignore este email.</p>
        """
        try:
            enviar_email(cfg, html, 'Redefinição de Senha - Controle de Contratos', email_to)
        except Exception as e:
            app.logger.warning("Erro ao enviar email de redefinicao: %s", e)
    return jsonify({"ok": True, "msg": "Se o usuario existir, um email sera enviado."})

@app.route('/api/reset-password', methods=['POST'])
def api_reset_password():
    data = request.json or {}
    token = (data.get('token') or '').strip()
    password = data.get('password') or ''
    if not token or not password:
        return jsonify({"ok": False, "erro": "Token e nova senha sao obrigatorios."}), 400
    if len(password) < 8:
        return jsonify({"ok": False, "erro": "A senha deve ter no minimo 8 caracteres."}), 400
    if not re.search(r'[A-Z]', password):
        return jsonify({"ok": False, "erro": "Senha deve conter pelo menos 1 letra maiuscula."}), 400
    if not re.search(r'[a-z]', password):
        return jsonify({"ok": False, "erro": "Senha deve conter pelo menos 1 letra minuscula."}), 400
    if not re.search(r'[0-9]', password):
        return jsonify({"ok": False, "erro": "Senha deve conter pelo menos 1 numero."}), 400
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    reset = query_db(
        "SELECT id, user_id, expires_at FROM password_resets WHERE token=? AND used=0",
        (token,), one=True
    )
    if not reset:
        return jsonify({"ok": False, "erro": "Token invalido ou ja utilizado."}), 400
    if reset['expires_at'] < now:
        return jsonify({"ok": False, "erro": "Token expirado. Solicite uma nova redefinicao."}), 400
    execute_db("UPDATE users SET password_hash=?, password_changed_at=? WHERE id=?",
               (hash_password(password), now, reset['user_id']))
    execute_db("UPDATE password_resets SET used=1 WHERE id=?", (reset['id'],))
    return jsonify({"ok": True, "msg": "Senha redefinida com sucesso!"})

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

# ─── RESUMO DE CONTRATOS VIA GEMINI ────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OLLAMA_API = "http://localhost:11434/api"
OLLAMA_MODEL = "gemma3:1b"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def extrair_pdf(arquivo_json):
    dados = json.loads(arquivo_json) if isinstance(arquivo_json, str) else arquivo_json
    data_url = dados.get("data") or dados.get("filePath", "")
    if not data_url:
        return None
    if "," in data_url:
        b64 = data_url.split(",", 1)[1]
    else:
        b64 = data_url
    return base64.b64decode(b64)

def extrair_texto_pdf(arquivo_json):
    try:
        raw = extrair_pdf(arquivo_json)
        if raw is None:
            return None
        doc = fitz.open(stream=raw, filetype="pdf")
        texto = "\n".join(page.get_text() for page in doc)
        doc.close()
        return texto.strip()
    except Exception as e:
        app.logger.error("Erro ao extrair texto do PDF: %s", e)
        return None

def pdf_para_imagens(arquivo_json):
    try:
        raw = extrair_pdf(arquivo_json)
        if raw is None:
            return None
        doc = fitz.open(stream=raw, filetype="pdf")
        imagens = []
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            imagens.append(img_bytes)
        doc.close()
        return imagens
    except Exception as e:
        app.logger.error("Erro ao converter PDF para imagens: %s", e)
        return None

def _prompt_resumo():
    return (
        "Voce e um assistente juridico especializado em contratos. "
        "Leia o texto abaixo e faca um resumo claro e objetivo em portugues.\n\n"
        "INSTRUCOES:\n"
        "1. Resuma em 2 a 3 paragrafos.\n"
        "2. Identifique as partes envolvidas (exequente e executada).\n"
        "3. Informe o valor original da divida e o valor acordado.\n"
        "4. Detalhe os prazos de pagamento: datas, valores das parcelas e forma de pagamento.\n"
        "5. Ao final, liste com bullet points os PONTOS DE ATENCAO:\n"
        "   - Prazos de vencimento proximos\n"
        "   - Multas ou clausulas penal\n"
        "   - Valores relevantes\n"
        "   - Riscos ou pontos que merecem cuidado especial\n"
        "   - Qualquer obrigacao importante\n\n"
        "TEXTO DO DOCUMENTO:\n"
    )

def _chamar_gemini(texto):
    if not GEMINI_API_KEY:
        return None
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        resp = model.generate_content(_prompt_resumo() + texto[:8000])
        resp_text = resp.text.strip()
        if len(resp_text) > 50:
            return resp_text
    except Exception as e:
        app.logger.error("Gemini falhou: %s", str(e))
    return None

def _chamar_ollama(texto):
    try:
        r = requests.post(f"{OLLAMA_API}/generate", json={
            "model": OLLAMA_MODEL,
            "prompt": _prompt_resumo() + texto[:3000],
            "stream": False
        }, timeout=180)
        if r.status_code == 200:
            resp = r.json().get("response", "").strip()
            if len(resp) > 50:
                return resp
    except Exception:
        pass
    return None

def gerar_resumo_ollama(texto):
    # Extrair dados estruturados via regex (rapido, sem LLM)
    dados = extrair_resumo_contrato(texto)
    resumo = formatar_resumo(dados)
    return resumo, None

def gerar_resumo_ollama_imagens(imagens):
    try:
        from PIL import Image
        textos = []
        for i, img_bytes in enumerate(imagens):
            img = Image.open(io.BytesIO(img_bytes))
            t = pytesseract.image_to_string(img, lang="por").strip()
            if len(t) > 10:
                textos.append(t)
        texto_completo = "\n\n".join(textos)
        if not texto_completo or len(texto_completo) < 20:
            return None, "Nao foi possivel reconhecer texto nas imagens"
    except Exception as e:
        app.logger.error("OCR falhou: %s", str(e))
        return None, str(e)

    # Extrair dados estruturados via regex (rapido, sem LLM)
    dados = extrair_resumo_contrato(texto_completo)
    resumo = formatar_resumo(dados)

    return resumo, None

@app.route('/api/resumo', methods=['GET', 'POST'])
def api_resumo():
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401

    data = request.get_json(silent=True) or {}
    entity = data.get('entity', '')
    entity_id = data.get('entity_id', '')

    if entity not in ('contract', 'additive'):
        return jsonify({"ok": False, "erro": "Entidade invalida. Use 'contract' ou 'additive'"}), 400

    table = 'contracts' if entity == 'contract' else 'additives'
    id_col = 'id' if entity == 'contract' else 'id'

    coluna_arquivo = 'arquivo_contrato' if entity == 'contract' else 'arquivo_aditivo'
    row = query_db(f"SELECT {coluna_arquivo} as arquivo, resumo FROM {table} WHERE {id_col}=?", (entity_id,), one=True)
    if not row:
        return jsonify({"ok": False, "erro": "Registro nao encontrado"}), 404

    arquivo = row.get("arquivo")
    if not arquivo:
        return jsonify({"ok": False, "erro": "Nenhum arquivo anexado a este registro"}), 400

    texto = extrair_texto_pdf(arquivo)
    if texto and len(texto) >= 50:
        resumo, erro = gerar_resumo_ollama(texto)
    else:
        imagens = pdf_para_imagens(arquivo)
        if not imagens:
            return jsonify({"ok": False, "erro": "Nao foi possivel extrair conteudo do PDF"}), 400
        resumo, erro = gerar_resumo_ollama_imagens(imagens)

    if erro:
        return jsonify({"ok": False, "erro": f"Erro ao gerar resumo: {erro}"}), 500

    execute_db(f"UPDATE {table} SET resumo=? WHERE {id_col}=?", (resumo, entity_id))
    return jsonify({"ok": True, "resumo": resumo})

# ─── ESTÁTICO / FALLBACK ──────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/extrair')
def serve_extract():
    return send_from_directory(".", "extract.html")

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

ALLOWED_STATIC_EXTENSIONS = {
    '.html', '.js', '.css', '.json',
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp',
    '.woff', '.woff2', '.ttf', '.eot',
    '.pdf', '.txt', '.md',
}

BLOCKED_STATIC_FILES = {
    '.env', '.env.example', '.env.local',
    'config_email.json', 'contratos.db', 'database.db',
    'key.pem', 'cert.pem',
    'site_id.json', 'site_info.json', 'env_vars.json',
    'cookies.txt', 'login_body.json', 'login_admin.json',
    'deploy_info.json', 'dados.json', 'body.json',
    'app.py', 'servidor.py', 'lembrete.py', 'extrator_contrato.py',
    'env_body.json', 'create_env.json', 'query_body.json',
    'lock_body.json', 'rename_body.json', 'active_body.json',
    'patch_body.json', 'alter_query.json', 'forgot_body.json',
}

@app.route('/<path:filename>')
def static_files(filename):
    if filename.startswith('api/') or filename.startswith('uploads/'):
        return jsonify({"ok": False, "erro": "Nao encontrado"}), 404
    basename = os.path.basename(filename)
    if basename in BLOCKED_STATIC_FILES:
        return jsonify({"ok": False, "erro": "Nao encontrado"}), 404
    ext = os.path.splitext(basename)[1].lower()
    if ext not in ALLOWED_STATIC_EXTENSIONS:
        return jsonify({"ok": False, "erro": "Nao encontrado"}), 404
    return send_from_directory('.', filename)

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

# ─── ASSISTENTE VIRTUAL ──────────────────────────────────────────────────────

SYSTEM_PROMPT_ASSISTENTE = """Voce e o Assistente Virtual do sistema CONTROLE DE CONTRATOS E PAGAMENTOS da Ideal Alimentacao.
Seu papel e ajudar o usuario a entender e usar o sistema. Responda SEMPRE em portugues brasileiro, de forma simples e direta.

SOBRE O SISTEMA:
O sistema e uma aplicacao web para gerenciar contratos, pagamentos e vencimentos de empresas. Foi desenvolvido em Python (Flask) com banco SQLite.

TELAS PRINCIPAIS:
1. DASHBOARD - Tela inicial com resumo: cards com totais, proximos vencimentos e contratos ativos. Permite filtrar por fornecedor/CNPJ/CPF e data de vencimento.
2. CONTRATOS - Lista todos os contratos cadastrados. Permite buscar, editar, excluir e ver detalhes. Tem filtros avancados e exportacao Excel.
3. NOVO CONTRATO - Formulario para cadastrar um novo contrato com todos os dados.
4. PAGAMENTOS - Lista todas as parcelas/pagamentos. Permite filtrar por contrato, status, periodo e valor. Registra pagamentos, anexa comprovantes e tem operacoes em lote.
5. CONFIGURACAO - Sub-menu com: Minha Conta, Usuarios, Empresas, Tipos de Servico, Destinatarios de E-mail, E-mail (SMTP), Historico, Informacoes do Sistema.

COMO CADASTRAR UM CONTRATO:
1. Clique em "+ Novo Contrato" no menu
2. Preencha os campos obrigatorios: Numero do Contrato, Tipo, Empresa, Objeto, Fornecedor/Cliente, Valor Total, Data de Inicio, Data de Fim
3. Se for um contrato com pagamentos, marque a checkbox e preencha: Forma de Pagamento, Quantidade de Parcelas, Dia de Vencimento, Valor da Parcela
4. Clique em "Salvar Contrato"
5. Os pagamentos serao criados automaticamente

COMO REGISTRAR UM PAGAMENTO:
1. Va em "Pagamentos"
2. Clique no botao "Baixar" ao lado do pagamento pendente
3. Informe: Data do Pagamento, Valor Pago, Forma de Pagamento
4. Opcionalmente anexe o comprovante (imagem ou PDF)
5. Confirme
6. Para baixar varios de uma vez, marque os checkboxes e clique em "Baixar Selecionados"

COMO EDITAR UM CONTRATO:
1. Va em "Contratos"
2. Clique no botao "Editar" ao lado do contrato
3. Altere os dados necessarios
4. Salve

COMO ADICIONAR ADITIVO:
1. Abra o detalhe do contrato
2. Clique em "Adit"
3. Preencha: Numero do Aditivo, Data, Tipo, Nova Data de Fim e/ou Acrescimo de Valor
4. Salve

RECURSOS AVANCADOS:
- Filtros avancados: por fornecedor, status, periodo e valor nas telas de Contratos e Pagamentos
- Exportacao Excel: botao "Exportar Excel" nas telas de Contratos e Pagamentos
- Paginacao: 25 registros por pagina nas listas
- Preview de PDF/Imagens: clique em "Ver" para visualizar anexos sem baixar
- Impressao: disponivel no modal de preview de anexos
- Operacoes em lote: selecione varios pagamentos e baixe, estorne ou exclua de uma vez
- Notificacoes: sino no canto superior direito com alertas de vencimentos
- Alteracao de senha: Configuracao > Minha Conta
- Historico de acoes: Configuracao > Historico mostra quem fez o que e quando
- Resumo de contratos via IA (Gemini) quando ha arquivo PDF anexado
- Tema claro/escuro: clique no icone da lua/sol no header
- Atalhos: Enter no login para entrar, Esc para fechar modais

Dicas:
- Preencha sempre o CNPJ/CPF do fornecedor para facilitar buscas
- Use os filtros para encontrar contratos e pagamentos rapidamente
- Configure o e-mail SMTP para receber alertas automaticos
- Use operacoes em lote para ganhar produtividade
- Cadastre os tipos de servico antes de criar contratos

Se o usuario perguntar algo fora do escopo do sistema, redirecione gentilmente para o tema. Seja prestativo e amigavel."""

@app.route('/api/assistente', methods=['POST'])
def api_assistente():
    if 'user_id' not in session:
        return jsonify({"ok": False, "erro": "Nao autenticado"}), 401

    data = request.get_json(silent=True) or {}
    pergunta = (data.get('pergunta') or '').strip()

    if not pergunta:
        return jsonify({"ok": False, "erro": "Pergunta vazia"}), 400

    if not GEMINI_API_KEY:
        return jsonify({"ok": True, "resposta": _resposta_offline(pergunta)})

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        resp = model.generate_content(
            SYSTEM_PROMPT_ASSISTENTE + "\n\nPERGUNTA DO USUARIO:\n" + pergunta[:2000],
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=800,
            )
        )
        resposta = resp.text.strip()
        if len(resposta) > 10:
            return jsonify({"ok": True, "resposta": resposta})
    except Exception as e:
        app.logger.error("Gemini assistente falhou: %s", str(e))

    return jsonify({"ok": True, "resposta": _resposta_offline(pergunta)})


def _resposta_offline(pergunta):
    p = pergunta.lower()
    if any(w in p for w in ['contrato', 'cadastr', 'novo', 'criar']):
        return ("Para cadastrar um contrato, clique em '+ Novo Contrato' no menu. "
                "Preencha os campos obrigatorios (Numero, Tipo, Empresa, Objeto, Fornecedor, Valor, Datas) "
                "e salve. Se tiver pagamentos, marque a checkbox e preencha as parcelas.")
    if any(w in p for w in ['pagamento', 'parcela', 'pay']):
        return ("Para registrar um pagamento, va em 'Pagamentos', clique em 'Baixar' ao lado "
                "do pagamento pendente, informe data, valor e forma de pagamento, e confirme. "
                "Voce pode selecionar varios pagamentos e baixar em lote usando os checkboxes.")
    if any(w in p for w in ['editar', 'alterar', 'mudar']):
        return ("Para editar, va em 'Contratos', clique no botao 'Editar' ao lado do contrato, "
                "altere os dados e salve.")
    if any(w in p for w in ['aditivo', 'prorrog', 'acresc']):
        return ("Para adicionar um aditivo, abra o detalhe do contrato e clique em 'Adit'. "
                "Informe o numero, data, tipo (Prazo/Valor/Ambos) e os novos dados.")
    if any(w in p for w in ['email', 'smtp', 'alerta', 'lembrete']):
        return ("Configure o e-mail em Configuracao > E-mail. Informe servidor SMTP, porta, email remetente e senha. "
                "Depois clique em 'Enviar Lembrete' ou 'Enviar Alertas' para notificar.")
    if any(w in p for w in ['usuario', 'senha', 'login', 'acesso']):
        return ("Para gerenciar usuarios, va em Configuracao > Usuarios. La voce pode criar, editar "
                "ou excluir usuarios, definir perfil (admin/usuario) e quais empresas tem acesso. "
                "Para alterar sua propria senha, va em Configuracao > Minha Conta.")
    if any(w in p for w in ['empresa', 'cnpj']):
        return ("Para cadastrar empresas, va em Configuracao > Empresas. Informe o nome e CNPJ. "
                "As empresas sao vinculadas aos contratos e aos usuarios.")
    if any(w in p for w in ['dashboard', 'inicio', 'resumo']):
        return ("O Dashboard mostra um resumo com cards (totais), proximos vencimentos e contratos. "
                "Use os filtros por fornecedor/CNPJ e data de vencimento.")
    if any(w in p for w in ['tema', 'escuro', 'claro', 'dark']):
        return ("Para mudar o tema, clique no icone da lua/sol no canto superior direito do header.")
    if any(w in p for w in ['filtro', 'filtrar', 'buscar', 'procurar']):
        return ("Na tela de Contratos, use os filtros por Fornecedor, Status, Periodo e Valor. "
                "Na tela de Pagamentos, pode filtrar por Contrato, Status, Periodo e Valor tambem.")
    if any(w in p for w in ['excel', 'exportar', 'planilha', 'csv']):
        return ("Para exportar para Excel, va em Contratos ou Pagamentos e clique no botao 'Exportar Excel' "
                "no topo da pagina. O arquivo sera baixado em formato CSV compativel com Excel.")
    if any(w in p for w in ['senha', 'trocar', 'alterar senha', 'minha conta']):
        return ("Para alterar sua senha, va em Configuracao > Minha Conta. "
                "Informe a senha atual e a nova senha (min. 8 caracteres, 1 maiuscula, 1 minuscula, 1 numero).")
    if any(w in p for w in ['notificac', 'sino', 'alerta visual']):
        return ("O sino de notificacoes no canto superior direito mostra alertas de contratos vencendo "
                "e pagamentos atrasados. Clique nele para ver os detalhes.")
    if any(w in p for w in ['pdf', 'anexo', 'visualizar', 'preview']):
        return ("Para visualizar um anexo, clique em 'Ver' na coluna Anexo de Contratos ou Pagamentos. "
                "O PDF ou imagem sera aberto num modal. Voce pode baixar ou imprimir diretamente de la.")
    if any(w in p for w in ['lote', 'varios', 'selecionar']):
        return ("Na tela de Pagamentos, marque os checkboxes ao lado de cada pagamento para selecionar varios. "
                "Depois use os botoes: Baixar Selecionados, Estornar Selecionados ou Excluir Selecionados.")
    if any(w in p for w in ['historico', 'log', 'auditoria', 'registro']):
        return ("Para ver o historico de acoes, va em Configuracao > Historico. "
                "La voce ve quem fez o que e quando (criar, editar, excluir, login, etc).")
    if any(w in p for w in ['resumo', 'ia', 'inteligencia', 'artificial']):
        return ("Para gerar o resumo com IA, abra o detalhe do contrato e clique em 'Gerar Resumo com IA'. "
                "Se ja existir um resumo, o botao aparece como 'Regenerar Resumo com IA'.")
    if any(w in p for w in ['enter', 'esc', 'atalho', 'tecla']):
        return ("Atalhos disponiveis: pressione Enter nos campos de Usuario ou Senha para fazer login. "
                "Pressione Esc para fechar qualquer tela/modal aberta.")
    return ("Posso ajudar com: cadastro de contratos, pagamentos, aditivos, empresas, usuarios, "
            "filtros, exportacao Excel, notificacoes, historico, alteracao de senha, "
            "visualizacao de PDF, operacoes em lote e mais. Faca sua pergunta!")

# ─── INICIALIZAÇÃO ───────────────────────────────────────────────────────────

import threading

def _enviar_emails_automaticos():
    """Envia lembretes de pagamentos e alertas de contratos automaticamente."""
    with app.app_context():
        try:
            cfg = ler_config()
            if not cfg.get('email_remetente') or not cfg.get('email_senha'):
                print("[EMAIL AUTO] Configuracao de e-mail nao encontrada. Pulando.")
                return

            destinatarios = query_db("SELECT * FROM destinatarios")
            if not destinatarios:
                print("[EMAIL AUTO] Nenhum destinatario cadastrado. Pulando.")
                return

            contratos = query_db("SELECT * FROM contracts")
            pagamentos = query_db("SELECT * from payments")
            empresas = query_db("SELECT * FROM empresas")
            empresa_nomes = {e['id']: e['nome'] for e in empresas if e.get('id') and e.get('nome')}
            hoje = date.today()

            enviados = 0
            erros = []

            # Lembretes de pagamentos
            for dest in destinatarios:
                email = (dest.get('email') or '').strip()
                if not email:
                    continue
                empresa_ids = dest.get('empresaIds') or dest.get('empresa_ids') or ''
                if isinstance(empresa_ids, str):
                    empresa_ids = [int(x.strip()) for x in empresa_ids.split(',') if x.strip().isdigit()]
                dest_nome = dest.get('nome', '')
                emp_ids_set = set(empresa_ids) if empresa_ids else None
                contrato_ids_emp = {c['id'] for c in contratos if emp_ids_set is None or c.get('empresa_id') in emp_ids_set}
                emp_pagamentos = [p for p in pagamentos if p.get('contract_id') in contrato_ids_emp]
                vencidos, vence_hoje, vence_amanha = processar_pagamentos(contratos, emp_pagamentos, hoje, empresa_nomes)
                if not (vencidos or vence_hoje or vence_amanha):
                    continue
                rotulo = f" - {dest_nome}" if dest_nome else ""
                partes = montar_html_pagamentos(vencidos, vence_hoje, vence_amanha, rotulo)
                html_content = f"""<html><body style="font-family:Arial,sans-serif;padding:20px">
                {''.join(partes)}
                <p style="color:#666;font-size:12px">Gerado automaticamente em {datetime.now().strftime("%d/%m/%Y %H:%M")}</p></body></html>"""
                try:
                    enviar_email(cfg, html_content,
                                 f'Lembrete de Pagamentos{rotulo} - {hoje.strftime("%d/%m/%Y")}',
                                 email)
                    enviados += 1
                except Exception as e:
                    erros.append(f"Pagamentos {email}: {e}")

            # Alertas de contratos
            for dest in destinatarios:
                email = (dest.get('email') or '').strip()
                if not email:
                    continue
                empresa_ids = dest.get('empresaIds') or dest.get('empresa_ids') or ''
                if isinstance(empresa_ids, str):
                    empresa_ids = [int(x.strip()) for x in empresa_ids.split(',') if x.strip().isdigit()]
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
                <p style="color:#666;font-size:12px">Gerado automaticamente em {datetime.now().strftime("%d/%m/%Y %H:%M")}</p></body></html>"""
                try:
                    enviar_email(cfg, emp_html,
                                 f'Alerta de Contratos{rotulo} - {hoje.strftime("%d/%m/%Y")}',
                                 email)
                    enviados += 1
                except Exception as e:
                    erros.append(f"Contratos {email}: {e}")

            if enviados > 0:
                print(f"[EMAIL AUTO] {enviados} e-mail(s) enviado(s) as {datetime.now().strftime('%H:%M')}")
            else:
                print(f"[EMAIL AUTO] Nenhum pendente para enviar as {datetime.now().strftime('%H:%M')}")
            if erros:
                print(f"[EMAIL AUTO] Erros: {'; '.join(erros)}")

        except Exception as e:
            print(f"[EMAIL AUTO] Erro geral: {e}")


def _agendar_emails_diarios():
    """Agenda envio de emails para todos os dias as 10h da manha."""
    import time
    while True:
        agora = datetime.now()
        proximo = agora.replace(hour=10, minute=0, second=0, microsecond=0)
        if agora >= proximo:
            proximo += timedelta(days=1)
        espera = (proximo - agora).total_seconds()
        print(f"[EMAIL AUTO] Proximo envio: {proximo.strftime('%d/%m/%Y %H:%M')} (em {int(espera/3600)}h{int((espera%3600)/60)}min)")
        time.sleep(espera)
        _enviar_emails_automaticos()


def _iniciar_scheduler():
    t = threading.Thread(target=_agendar_emails_diarios, daemon=True)
    t.start()
    print("[EMAIL AUTO] Scheduler de emails iniciado (todos os dias as 10h)")


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    https_enabled = os.environ.get("HTTPS", "0") == "1"
    port = int(os.environ.get('PORT', 5000))
    try:
        with app.app_context():
            init_db()
        print("=" * 50)
        print("Sistema iniciado com sucesso!")
        _iniciar_scheduler()
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
        if debug_mode:
            app.run(host='0.0.0.0', port=port, debug=True, ssl_context=ssl_ctx)
        else:
            from waitress import serve
            print("[WAITRESS] Servidor production iniciado")
            serve(app, host='0.0.0.0', port=port, url_scheme='https' if https_enabled else 'http')
    except Exception as e:
        app.logger.error("Erro ao iniciar: %s", traceback.format_exc())
        print("\n" + "=" * 50)
        print("ERRO AO INICIAR:")
        print(str(e))
        print("=" * 50)
        input("\nAperte ENTER para fechar...")
