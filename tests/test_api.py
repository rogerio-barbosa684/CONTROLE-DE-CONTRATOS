import sys
import os
import json
import tempfile
import sqlite3
import uuid
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db, hash_password, get_db, query_db, login_attempts


@pytest.fixture
def client():
    db_fd, app.config['DATABASE'] = tempfile.mkstemp(suffix='.db')
    app.config['TESTING'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    login_attempts.clear()

    with app.test_client() as client:
        with app.app_context():
            init_db()
            db = get_db()
            if not query_db("SELECT id FROM users WHERE username=?", ("testadmin",), one=True):
                db.execute(
                    "INSERT INTO users (username, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
                    ("testadmin", "Admin Teste", hash_password("Admin123"), "admin")
                )
            if not query_db("SELECT id FROM users WHERE username=?", ("testuser",), one=True):
                db.execute(
                    "INSERT INTO users (username, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
                    ("testuser", "Usuario Teste", hash_password("Usuario12"), "user")
                )
            db.commit()
        yield client

    os.close(db_fd)
    os.unlink(app.config['DATABASE'])


def do_login(client, username, password):
    resp = client.post('/api/login', json={
        "username": username,
        "password": password
    }, content_type='application/json')
    data = json.loads(resp.data)
    return resp, data


def do_login_get_csrf(client, username, password):
    resp, data = do_login(client, username, password)
    return data.get('csrf_token', '')


class TestLogin:
    def test_login_sucesso(self, client):
        resp, data = do_login(client, "testadmin", "Admin123")
        assert resp.status_code == 200
        assert data['ok'] is True
        assert data['user']['username'] == 'testadmin'
        assert data['user']['role'] == 'admin'

    def test_login_senha_errada(self, client):
        resp, data = do_login(client, "testadmin", "senhaerrada")
        assert resp.status_code == 401
        assert data['ok'] is False

    def test_login_usuario_inexistente(self, client):
        resp, _ = do_login(client, "naoexiste", "qualquer1")
        assert resp.status_code == 401

    def test_login_campos_vazios(self, client):
        resp, _ = do_login(client, "", "")
        assert resp.status_code == 401


class TestLogout:
    def test_logout(self, client):
        do_login(client, "testadmin", "Admin123")
        resp = client.post('/api/logout')
        data = json.loads(resp.data)
        assert resp.status_code == 200
        assert data['ok'] is True


class TestCSRF:
    def test_csrf_token_disponivel(self, client):
        resp = client.get('/api/csrf-token')
        data = json.loads(resp.data)
        assert 'csrf_token' in data
        assert len(data['csrf_token']) > 0

    def test_csrf_invalido_rejeitado(self, client):
        do_login(client, "testadmin", "Admin123")
        resp = client.post('/api/users', json={
            "username": "testcsrf",
            "full_name": "Test CSRF",
            "password": "Test1234Abc",
            "role": "user",
            "csrf_token": "token_invalido"
        }, content_type='application/json')
        assert resp.status_code == 403


class TestRateLimiting:
    def test_bloqueio_apos_5_tentativas(self, client):
        for _ in range(6):
            do_login(client, "testadmin", "senhaerrada")

        resp, data = do_login(client, "testadmin", "Admin123")
        assert resp.status_code == 429
        assert "Aguarde" in data['erro']


class TestUsuarios:
    def test_listar_usuarios_admin(self, client):
        resp, data = do_login(client, "testadmin", "Admin123")
        csrf = data['csrf_token']
        resp = client.get('/api/users', headers={'X-CSRF-Token': csrf})
        assert resp.status_code == 200

    def test_listar_usuarios_sem_admin(self, client):
        resp, data = do_login(client, "testuser", "Usuario12")
        csrf = data['csrf_token']
        resp = client.get('/api/users', headers={'X-CSRF-Token': csrf})
        assert resp.status_code == 403

    def test_criar_usuario_senha_fraca(self, client):
        resp, data = do_login(client, "testadmin", "Admin123")
        csrf = data['csrf_token']
        username = f"fraco_{uuid.uuid4().hex[:8]}"
        resp = client.post('/api/users', json={
            "username": username,
            "full_name": "Senha Fraca",
            "password": "123",
            "role": "user",
            "csrf_token": csrf
        }, content_type='application/json')
        data = json.loads(resp.data)
        assert resp.status_code == 400
        assert "8 caracteres" in data['erro']

    def test_criar_usuario_senha_forte(self, client):
        resp, data = do_login(client, "testadmin", "Admin123")
        csrf = data['csrf_token']
        username = f"forte_{uuid.uuid4().hex[:8]}"
        resp = client.post('/api/users', json={
            "username": username,
            "full_name": "Senha Forte",
            "password": "Fortaleza1",
            "role": "user",
            "csrf_token": csrf
        }, content_type='application/json')
        data = json.loads(resp.data)
        assert resp.status_code == 200
        assert data['ok'] is True

    def test_criar_usuario_email_invalido(self, client):
        resp, data = do_login(client, "testadmin", "Admin123")
        csrf = data['csrf_token']
        username = f"email_{uuid.uuid4().hex[:8]}"
        resp = client.post('/api/users', json={
            "username": username,
            "full_name": "Email Errado",
            "password": "Senha1234",
            "email": "naoeumemail",
            "role": "user",
            "csrf_token": csrf
        }, content_type='application/json')
        data = json.loads(resp.data)
        assert resp.status_code == 400
        assert "Email invalido" in data['erro']


class TestSync:
    def test_sync_get_autenticado(self, client):
        resp, data = do_login(client, "testadmin", "Admin123")
        csrf = data['csrf_token']
        resp = client.get('/api/sync', headers={'X-CSRF-Token': csrf})
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'contratos' in data
        assert 'pagamentos' in data

    def test_sync_get_nao_autenticado(self, client):
        resp = client.get('/api/sync')
        assert resp.status_code == 401


class TestStaticFiles:
    def test_index_html_acessivel(self, client):
        resp = client.get('/index.html')
        assert resp.status_code == 200

    def test_env_bloqueado(self, client):
        resp = client.get('/.env')
        assert resp.status_code == 404

    def test_key_pem_bloqueado(self, client):
        resp = client.get('/key.pem')
        assert resp.status_code == 404

    def test_config_email_bloqueado(self, client):
        resp = client.get('/config_email.json')
        assert resp.status_code == 404

    def test_contratos_db_bloqueado(self, client):
        resp = client.get('/contratos.db')
        assert resp.status_code == 404
