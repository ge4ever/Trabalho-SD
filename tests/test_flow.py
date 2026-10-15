import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from gateway.server import app, JWT_SECRET, JWT_ALGORITHM
from database.db import db
import jwt


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def reset_database():
    """Restaura os saldos iniciais de teste antes de cada bateria."""
    db.execute("UPDATE contas SET saldo = 1250.75 WHERE chave_pix = 'alice@pix.local';")
    db.execute("UPDATE contas SET saldo = 340.20 WHERE chave_pix = 'bob@pix.local';")
    db.execute("DELETE FROM transacoes WHERE mensagem = 'Teste Automatizado';")


def test_401_unauthorized_sem_token(client):
    """Requisito 6: Requisições sem token válido devem ser imediatamente barradas na borda com 401 Unauthorized."""
    # Consulta de saldo sem token
    res = client.get("/pix/saldo/alice@pix.local")
    assert res.status_code == 401
    assert res.json["sucesso"] is False

    # Transferência sem token
    res2 = client.post("/pix/transferir", json={"chave_destino": "bob@pix.local", "valor": 50})
    assert res2.status_code == 401
    assert res2.json["sucesso"] is False


def test_401_unauthorized_token_invalido(client):
    """Requisito 6: Token malformado ou adulterado deve ser barrado com 401."""
    headers = {"Authorization": "Bearer token-completamente-falso-12345"}
    res = client.get("/pix/saldo/alice@pix.local", headers=headers)
    assert res.status_code == 401
    assert "inválido" in res.json["mensagem"].lower()


def test_login_e_emissao_jwt(client):
    """Requisito 6: Emissão correta de JWT assinado após validação no microsserviço de contas."""
    res = client.post("/auth/login", json={"chave_pix": "alice@pix.local", "senha": "123456"})
    assert res.status_code == 200
    data = res.json
    assert data["sucesso"] is True
    assert "token" in data
    token = data["token"]

    # Decodifica para checar integridade
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == "alice@pix.local"
    assert payload["titular"] == "Alice Silva"


def test_400_bad_request_validacao_payload(client):
    """Requisito 5: Validação obrigatória do payload JSON no Gateway com retorno explícito de 400 Bad Request."""
    # Obter token de Alice
    login_res = client.post("/auth/login", json={"chave_pix": "alice@pix.local", "senha": "123456"})
    token = login_res.json["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Caso 1: Payload vazio
    res1 = client.post("/pix/transferir", data="", content_type="application/json", headers=headers)
    assert res1.status_code == 400

    # Caso 2: Falta de campo obrigatório (sem chave destino)
    res2 = client.post("/pix/transferir", json={"valor": 100}, headers=headers)
    assert res2.status_code == 400
    assert "erros" in res2.json

    # Caso 3: Valor inválido (menor ou igual a zero)
    res3 = client.post("/pix/transferir", json={"chave_destino": "bob@pix.local", "valor": -50}, headers=headers)
    assert res3.status_code == 400
    assert any("maior que zero" in err for err in res3.json.get("erros", []))

    # Caso 4: Origem igual ao destino
    res4 = client.post("/pix/transferir", json={"chave_origem": "alice@pix.local", "chave_destino": "alice@pix.local", "valor": 50}, headers=headers)
    assert res4.status_code == 400
    assert any("diferente" in err for err in res4.json.get("erros", []))


def test_consulta_saldo_grpc(client):
    """Requisitos 2 e 7: Gateway recebe GET, valida JWT e consulta AccountService via gRPC."""
    login_res = client.post("/auth/login", json={"chave_pix": "alice@pix.local", "senha": "123456"})
    token = login_res.json["token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/pix/saldo/alice@pix.local", headers=headers)
    assert res.status_code == 200
    data = res.json
    assert data["sucesso"] is True
    assert data["titular"] == "Alice Silva"
    assert float(data["saldo"]) == 1250.75


def test_transferencia_real_persistida_no_banco(client):
    """Requisitos 1, 4, 5 e 7: Fluxo completo de transferência real refletido no banco de dados e retorno 201 Created."""
    login_res = client.post("/auth/login", json={"chave_pix": "alice@pix.local", "senha": "123456"})
    token = login_res.json["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Saldo antes
    saldo_alice_antes = float(db.query_one("SELECT saldo FROM contas WHERE chave_pix = 'alice@pix.local';")["saldo"])
    saldo_bob_antes = float(db.query_one("SELECT saldo FROM contas WHERE chave_pix = 'bob@pix.local';")["saldo"])

    # Executa transferência de R$ 50.75
    payload = {
        "chave_origem": "alice@pix.local",
        "chave_destino": "bob@pix.local",
        "valor": 50.75,
        "descricao": "Teste Automatizado"
    }
    res = client.post("/pix/transferir", json=payload, headers=headers)

    # 1. Deve retornar HTTP 201 Created
    assert res.status_code == 201
    data = res.json
    assert data["sucesso"] is True
    assert "transacao_id" in data
    tx_id = data["transacao_id"]

    # 2. Deve ter debitado Alice no banco de dados real
    saldo_alice_depois = float(db.query_one("SELECT saldo FROM contas WHERE chave_pix = 'alice@pix.local';")["saldo"])
    assert round(saldo_alice_depois, 2) == round(saldo_alice_antes - 50.75, 2)

    # 3. Deve ter creditado Bob no banco de dados real
    saldo_bob_depois = float(db.query_one("SELECT saldo FROM contas WHERE chave_pix = 'bob@pix.local';")["saldo"])
    assert round(saldo_bob_depois, 2) == round(saldo_bob_antes + 50.75, 2)

    # 4. Deve ter registrado a transação no banco de dados real
    tx_row = db.query_one("SELECT * FROM transacoes WHERE id = %s;", (tx_id,))
    assert tx_row is not None
    assert tx_row["chave_origem"] == "alice@pix.local"
    assert tx_row["chave_destino"] == "bob@pix.local"
    assert float(tx_row["valor"]) == 50.75
    assert tx_row["status"] == "CONCLUIDO"


def test_transferencia_saldo_insuficiente(client):
    """Validação de saldo insuficiente retornando 400."""
    login_res = client.post("/auth/login", json={"chave_pix": "bob@pix.local", "senha": "123456"})
    token = login_res.json["token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "chave_origem": "bob@pix.local",
        "chave_destino": "alice@pix.local",
        "valor": 99999.00,
        "descricao": "Tentativa sem saldo"
    }
    res = client.post("/pix/transferir", json=payload, headers=headers)
    assert res.status_code == 400
    assert "saldo insuficiente" in res.json["mensagem"].lower()
