import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import validar_senha_forte, validar_cpf_cnpj, validar_email_server


class TestValidarSenhaForte:
    def test_senha_valida(self):
        assert validar_senha_forte("Abcdef123") == (True, "")

    def test_senha_forte_com_caracteres_especiais(self):
        assert validar_senha_forte("Abcdef1!") == (True, "")

    def test_senha_muito_curta(self):
        ok, msg = validar_senha_forte("Ab1")
        assert ok is False
        assert "8 caracteres" in msg

    def test_senha_sem_maiuscula(self):
        ok, msg = validar_senha_forte("abcdef12")
        assert ok is False
        assert "maiuscula" in msg

    def test_senha_sem_minuscula(self):
        ok, msg = validar_senha_forte("ABCDEF12")
        assert ok is False
        assert "minuscula" in msg

    def test_senha_sem_numero(self):
        ok, msg = validar_senha_forte("Abcdefgh")
        assert ok is False
        assert "numero" in msg

    def test_senha_exatamente_8_chars(self):
        assert validar_senha_forte("Abcdef12") == (True, "")

    def test_senha_7_chars(self):
        ok, _ = validar_senha_forte("Abcdef1")
        assert ok is False

    def test_senha_vazia(self):
        ok, _ = validar_senha_forte("")
        assert ok is False


class TestValidarCpfCnpj:
    def test_cpf_valido(self):
        assert validar_cpf_cnpj("529.982.247-25") is True

    def test_cpf_valido_sem_formatacao(self):
        assert validar_cpf_cnpj("52998224725") is True

    def test_cpf_invalido(self):
        assert validar_cpf_cnpj("123.456.789-00") is False

    def test_cpf_todos_iguais(self):
        assert validar_cpf_cnpj("111.111.111-11") is False

    def test_cnpj_valido(self):
        assert validar_cpf_cnpj("11.222.333/0001-81") is True

    def test_cnpj_valido_sem_formatacao(self):
        assert validar_cpf_cnpj("11222333000181") is True

    def test_cnpj_invalido(self):
        assert validar_cpf_cnpj("11.222.333/0001-00") is False

    def test_cnpj_todos_iguais(self):
        assert validar_cpf_cnpj("11.111.111/1111-11") is False

    def test_valor_vazio(self):
        assert validar_cpf_cnpj("") is True

    def test_valor_none(self):
        assert validar_cpf_cnpj(None) is True

    def test_valor_curto(self):
        assert validar_cpf_cnpj("123") is True


class TestValidarEmailServer:
    def test_email_valido(self):
        assert validar_email_server("teste@email.com") is True

    def test_email_com_ponto(self):
        assert validar_email_server("teste.sobrenome@email.com.br") is True

    def test_email_com_mais(self):
        assert validar_email_server("user+tag@email.com") is True

    def test_email_invalido_sem_arroba(self):
        assert validar_email_server("testeemail.com") is False

    def test_email_invalido_sem_dominio(self):
        assert validar_email_server("teste@") is False

    def test_email_invalido_sem_usuario(self):
        assert validar_email_server("@email.com") is False

    def test_email_vazio(self):
        assert validar_email_server("") is True

    def test_email_none(self):
        assert validar_email_server(None) is True
