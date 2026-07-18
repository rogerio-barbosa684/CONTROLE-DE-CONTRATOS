import json, os, smtplib, ssl, html, base64
from datetime import date, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, send_from_directory
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ATENCAO: Este servidor (porta 5001) NAO possui autenticacao.
# Use apenas em rede local confiavel ou substitua pelo app.py (porta 5000)
# que possui login, CSRF e auditoria.

app = Flask(__name__, static_folder='.')
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24).hex()
DATA_FILE = os.path.join(os.path.dirname(__file__), 'dados.json')
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config_email.json')


def _get_cipher():
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        salt = b'contratos_salt_fixo'
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        key = base64.urlsafe_b64encode(kdf.derive(app.secret_key.encode()))
    else:
        key = key.encode() if isinstance(key, str) else key
    return Fernet(key)


def encrypt_text(text):
    if not text:
        return ""
    return _get_cipher().encrypt(text.encode()).decode()


def decrypt_text(encrypted):
    if not encrypted:
        return ""
    try:
        return _get_cipher().decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted

def ler_dados():
    if not os.path.exists(DATA_FILE):
        return {"contratos": [], "pagamentos": [], "usuarios": []}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def salvar_dados(dados):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def ler_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    if cfg.get('email_senha') and not cfg.get('email_senha_enc'):
        cfg['email_senha_enc'] = encrypt_text(cfg['email_senha'])
        cfg['email_senha'] = decrypt_text(cfg['email_senha_enc'])
    elif cfg.get('email_senha_enc'):
        cfg['email_senha'] = decrypt_text(cfg['email_senha_enc'])
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

def formatar_data(d):
    if not d: return '-'
    try:
        p = d[:10].split('-')
        return f'{p[2]}/{p[1]}/{p[0]}'
    except: return str(d)

def formatar_moeda(v):
    try:
        return f'{float(v):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except: return '0,00'

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/extrair')
def extrair():
    return send_from_directory('.', 'extract.html')

@app.route('/api/sync', methods=['POST'])
def sync():
    dados = request.json
    salvar_dados(dados)
    return jsonify({"ok": True})

@app.route('/api/sync', methods=['GET'])
def get_sync():
    return jsonify(ler_dados())

@app.route('/api/config-email', methods=['GET', 'POST'])
def config_email():
    if request.method == 'POST':
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

@app.route('/api/enviar-lembrete', methods=['POST'])
def enviar_lembrete():
    cfg = ler_config()
    if not cfg.get('email_remetente') or not cfg.get('email_senha'):
        return jsonify({"ok": False, "erro": "Configure o e-mail primeiro."})

    dados = ler_dados()
    pagamentos = dados.get('pagamentos', [])
    contratos = dados.get('contratos', [])
    hoje = date.today()

    vencidos, vence_hoje, vence_amanha = [], [], []

    for p in pagamentos:
        if p.get('dataPagamento'): continue
        venc = p.get('vencimento', '')[:10]
        try:
            dv = datetime.strptime(venc, '%Y-%m-%d').date()
        except:
            continue
        c = next((c for c in contratos if c.get('id') == p.get('contratoId')), None)
        info = {
            'contrato': p.get('contratoNum', '?'),
            'parte': c.get('parte', '?') if c else '?',
            'descricao': p.get('descricao', '?'),
            'vencimento': formatar_data(venc),
            'valor': formatar_moeda(p.get('valor', 0))
        }
        if dv < hoje:
            info['dias'] = (hoje - dv).days
            vencidos.append(info)
        elif dv == hoje:
            vence_hoje.append(info)
        elif (dv - hoje).days == 1:
            vence_amanha.append(info)

    if not (vencidos or vence_hoje or vence_amanha):
        return jsonify({"ok": True, "msg": "Nenhum vencimento pendente encontrado."})

    html_content = """<html><body style="font-family:Arial,sans-serif;padding:20px">
    <h2 style="color:#1a3c5e">Lembrete de Vencimentos</h2>"""

    if vencidos:
        html_content += """<h3 style="color:#c0392b">VENCIDOS</h3><table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px">
        <tr style="background:#ffe1e1"><th>Contrato</th><th>Fornecedor</th><th>Parcela</th><th>Vencimento</th><th>Valor</th><th>Dias</th></tr>"""
        for v in vencidos:
            html_content += f'<tr><td>{html.escape(v["contrato"])}</td><td>{html.escape(v["parte"])}</td><td>{html.escape(v["descricao"])}</td><td>{html.escape(v["vencimento"])}</td><td>R$ {html.escape(v["valor"])}</td><td>{v["dias"]} dia(s)</td></tr>'
        html_content += '</table>'

    if vence_hoje:
        html_content += """<h3 style="color:#d4820a">VENCEM HOJE</h3><table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px">
        <tr style="background:#fff3cd"><th>Contrato</th><th>Fornecedor</th><th>Parcela</th><th>Vencimento</th><th>Valor</th></tr>"""
        for v in vence_hoje:
            html_content += f'<tr><td>{html.escape(v["contrato"])}</td><td>{html.escape(v["parte"])}</td><td>{html.escape(v["descricao"])}</td><td>{html.escape(v["vencimento"])}</td><td>R$ {html.escape(v["valor"])}</td></tr>'
        html_content += '</table>'

    if vence_amanha:
        html_content += """<h3 style="color:#24527a">VENCEM AMANHA</h3><table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:20px">
        <tr style="background:#eef6ff"><th>Contrato</th><th>Fornecedor</th><th>Parcela</th><th>Vencimento</th><th>Valor</th></tr>"""
        for v in vence_amanha:
            html_content += f'<tr><td>{html.escape(v["contrato"])}</td><td>{html.escape(v["parte"])}</td><td>{html.escape(v["descricao"])}</td><td>{html.escape(v["vencimento"])}</td><td>R$ {html.escape(v["valor"])}</td></tr>'
        html_content += '</table>'

    html_content += f'<p style="color:#666;font-size:12px">Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}</p></body></html>'

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Lembrete de Vencimentos - {hoje.strftime("%d/%m/%Y")}'
        msg['From'] = cfg['email_remetente']
        msg['To'] = cfg.get('email_destinatario', cfg['email_remetente'])
        msg.attach(MIMEText(html_content, 'html'))

        ctx = ssl.create_default_context()
        with smtplib.SMTP(cfg.get('smtp_server', 'smtp.gmail.com'), int(cfg.get('smtp_port', 587))) as server:
            server.starttls(context=ctx)
            server.login(cfg['email_remetente'], cfg['email_senha'])
            server.sendmail(msg['From'], msg['To'].split(','), msg.as_string())

        total = len(vencidos) + len(vence_hoje) + len(vence_amanha)
        return jsonify({"ok": True, "msg": f"E-mail enviado! {total} vencimento(s) encontrado(s)."})
    except Exception as e:
        print("ERRO EMAIL:", e)
        return jsonify({"ok": False, "erro": "Erro ao enviar e-mail. Verifique as configurações."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
