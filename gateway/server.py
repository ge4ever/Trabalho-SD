import datetime
from functools import wraps
import os
import sys
from flask import Flask, g, jsonify, render_template, request
import jwt

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
GRPC_DIR = os.path.join(ROOT_DIR, "grpc-generated")
if GRPC_DIR not in sys.path:
    sys.path.insert(0, GRPC_DIR)

import grpc
import pix_pb2
import pix_pb2_grpc

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
    static_url_path="/static"
)

# Configurações de ambiente
JWT_SECRET = os.getenv("JWT_SECRET", "chave-secreta-jwt-banco-sd-2026-super-segura-distribuidos-ufg-2026")
JWT_ALGORITHM = "HS256"


def resolve_service_host(env_var_name, default_port):
    """
    Resolve o endereço do serviço gRPC com suporte a:
    - Variável de ambiente específica (ACCOUNT_SERVICE_HOST ou PIX_SERVICE_HOST)
    - Variável global BACKEND_HOST (ex: BACKEND_HOST=136.80.4.171)
    - Fallback padrão inteligente para '136.80.4.171' ou 'localhost'
    - Limpeza automática de prefixos http:// e adição de porta se ausente.
    """
    raw_val = os.getenv(env_var_name, "").strip()
    if not raw_val:
        backend_geral = os.getenv("BACKEND_HOST", "").strip()
        if backend_geral:
            raw_val = f"{backend_geral}:{default_port}"
        else:
            raw_val = f"136.80.4.171:{default_port}"

    raw_val = raw_val.replace("http://", "").replace("https://", "").strip()
    if ":" not in raw_val:
        raw_val = f"{raw_val}:{default_port}"
    return raw_val


ACCOUNT_SERVICE_HOST = resolve_service_host("ACCOUNT_SERVICE_HOST", 50052)
PIX_SERVICE_HOST = resolve_service_host("PIX_SERVICE_HOST", 50053)


# ==============================================================================
# CORS Headers
# ==============================================================================
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


# ==============================================================================
# Middleware de Segurança JWT
# ==============================================================================
def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({
                "sucesso": False,
                "mensagem": "Cabeçalho de autenticação ausente. Forneça o token no formato 'Authorization: Bearer <token>'."
            }), 401

        partes = auth_header.strip().split(" ")
        if len(partes) != 2 or partes[0].lower() != "bearer":
            return jsonify({
                "sucesso": False,
                "mensagem": "Formato de token inválido. Esperado 'Bearer <token>'."
            }), 401

        token = partes[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            g.usuario = payload
        except jwt.ExpiredSignatureError:
            return jsonify({
                "sucesso": False,
                "mensagem": "Sessão expirada. O token JWT informado expirou."
            }), 401
        except jwt.InvalidTokenError as e:
            return jsonify({
                "sucesso": False,
                "mensagem": f"Token JWT inválido: {str(e)}."
            }), 401

        return f(*args, **kwargs)

    return decorated_function


# ==============================================================================
# Rotas Públicas (Frontend e Autenticação)
# ==============================================================================
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/auth/login", methods=["POST"])
def login():
    """Autentica o usuário no microsserviço AccountService e emite token JWT."""
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({
            "sucesso": False,
            "mensagem": "Corpo da requisição deve ser um JSON válido."
        }), 400

    chave = dados.get("chave_pix", "").strip()
    senha = dados.get("senha", "").strip() or "123456"

    if not chave:
        return jsonify({
            "sucesso": False,
            "mensagem": "O campo 'chave_pix' é obrigatório para autenticação."
        }), 400

    # Tradução de Protocolo: REST/JSON -> gRPC com AccountService
    print(f"[GATEWAY] [LOGIN] Tentando autenticar '{chave}' via gRPC em {ACCOUNT_SERVICE_HOST}...")
    try:
        with grpc.insecure_channel(ACCOUNT_SERVICE_HOST) as channel:
            account_stub = pix_pb2_grpc.AccountServiceStub(channel)
            auth_resp = account_stub.Autenticar(
                pix_pb2.AuthRequest(chave_pix=chave, senha=senha),
                timeout=5.0
            )

        if not auth_resp.sucesso:
            print(f"[GATEWAY] [LOGIN] Autenticação recusada para '{chave}': {auth_resp.mensagem}")
            return jsonify({
                "sucesso": False,
                "mensagem": auth_resp.mensagem
            }), 401

        # Geração do Token JWT com validade de 24 horas
        exp_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        token = jwt.encode(
            {
                "sub": chave,
                "titular": auth_resp.titular,
                "exp": exp_time,
                "iat": datetime.datetime.now(datetime.timezone.utc),
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM
        )

        print(f"[GATEWAY] [LOGIN] Sucesso! JWT emitido para '{chave}' ({auth_resp.titular})")
        return jsonify({
            "sucesso": True,
            "token": token,
            "chave_pix": chave,
            "titular": auth_resp.titular,
            "mensagem": "Login efetuado com sucesso."
        }), 200

    except grpc.RpcError as e:
        detalhes = e.details() if hasattr(e, "details") else str(e)
        status = e.code() if hasattr(e, "code") else "UNKNOWN"
        print(f"[GATEWAY ERRO] Falha gRPC ao comunicar com AccountService em '{ACCOUNT_SERVICE_HOST}': status={status}, detalhes={detalhes}")
        return jsonify({
            "sucesso": False,
            "alvo": ACCOUNT_SERVICE_HOST,
            "mensagem": f"Erro de comunicação com o serviço de contas em '{ACCOUNT_SERVICE_HOST}'. Verifique se o AccountService está rodando. Detalhes: {detalhes or status}"
        }), 503


# ==============================================================================
# Rotas Protegidas por JWT (Tradução e Orquestração gRPC)
# ==============================================================================

@app.route("/pix/saldo/<chave_pix>", methods=["GET"])
@jwt_required
def consultar_saldo(chave_pix):
    """Consulta de saldo protegida por JWT via gRPC no AccountService."""
    chave_pix = chave_pix.strip()
    if not chave_pix:
        return jsonify({
            "sucesso": False,
            "mensagem": "Chave Pix não fornecida na URL."
        }), 400

    print(f"[GATEWAY] [SALDO] Consultando saldo de '{chave_pix}' via gRPC em {ACCOUNT_SERVICE_HOST}...")
    try:
        with grpc.insecure_channel(ACCOUNT_SERVICE_HOST) as channel:
            account_stub = pix_pb2_grpc.AccountServiceStub(channel)
            saldo_resp = account_stub.ConsultarConta(
                pix_pb2.SaldoRequest(chave_pix=chave_pix),
                timeout=5.0
            )

        status_code = 200 if saldo_resp.sucesso else 404
        return jsonify({
            "sucesso": saldo_resp.sucesso,
            "titular": saldo_resp.titular,
            "saldo": saldo_resp.saldo,
            "mensagem": saldo_resp.mensagem
        }), status_code

    except grpc.RpcError as e:
        detalhes = e.details() if hasattr(e, "details") else str(e)
        status = e.code() if hasattr(e, "code") else "UNKNOWN"
        print(f"[GATEWAY ERRO] Falha gRPC ao consultar saldo em AccountService ({ACCOUNT_SERVICE_HOST}): {status} - {detalhes}")
        return jsonify({
            "sucesso": False,
            "alvo": ACCOUNT_SERVICE_HOST,
            "mensagem": f"Erro ao comunicar com AccountService em '{ACCOUNT_SERVICE_HOST}': {detalhes or status}"
        }), 503


@app.route("/pix/transferir", methods=["POST"])
@jwt_required
def transferir_pix():
    """Validação de payload, segurança JWT e orquestração gRPC com PixService."""
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({
            "sucesso": False,
            "mensagem": "Corpo da requisição deve ser um JSON válido."
        }), 400

    # Validação obrigatória de campos de negócio
    erros = []
    chave_origem = dados.get("chave_origem") or g.usuario.get("sub", "")
    chave_origem = chave_origem.strip()
    chave_destino = (dados.get("chave_destino") or dados.get("chave_pix") or "").strip()
    valor_raw = dados.get("valor")
    descricao = dados.get("descricao", "Transferência Pix").strip()

    if not chave_origem:
        erros.append("Campo 'chave_origem' é obrigatório.")

    if not chave_destino:
        erros.append("Campo 'chave_destino' é obrigatório.")

    if chave_origem and chave_destino and chave_origem == chave_destino:
        erros.append("A chave de destino deve ser diferente da conta de origem.")

    if valor_raw is None:
        erros.append("Campo 'valor' é obrigatório.")
    else:
        try:
            valor = float(valor_raw)
            if valor <= 0:
                erros.append("O campo 'valor' deve ser maior que zero (R$ 0,00).")
        except (ValueError, TypeError):
            erros.append("O campo 'valor' deve ser numérico.")

    # Retorno explícito de 400 Bad Request se houver falhas de validação
    if erros:
        return jsonify({
            "sucesso": False,
            "mensagem": "Dados inválidos para a transferência Pix.",
            "erros": erros
        }), 400

    # Tradução de protocolo e delegação para o Microsserviço gRPC (PixService)
    print(f"[GATEWAY] [PIX] Solicitando transferência: '{chave_origem}' -> '{chave_destino}' (R$ {valor:.2f}) para PixService ({PIX_SERVICE_HOST})...")
    try:
        with grpc.insecure_channel(PIX_SERVICE_HOST) as channel:
            pix_stub = pix_pb2_grpc.PixServiceStub(channel)
            resp = pix_stub.TransferirPix(
                pix_pb2.TransferenciaRequest(
                    chave_origem=chave_origem,
                    chave_destino=chave_destino,
                    valor=valor,
                    descricao=descricao
                ),
                timeout=8.0
            )

        if resp.sucesso:
            print(f"[GATEWAY] [PIX] Transferência concluída com sucesso (TxID: {resp.transacao_id})")
            # Retorno semântico 201 Created para nova transferência criada com sucesso
            return jsonify({
                "sucesso": True,
                "transacao_id": resp.transacao_id,
                "titular_origem": resp.titular_origem,
                "titular_destino": resp.titular_destino,
                "valor": resp.valor,
                "saldo": resp.saldo_remanescente,
                "mensagem": resp.mensagem,
                "data_hora": resp.data_hora
            }), 201
        else:
            print(f"[GATEWAY] [PIX] Transferência rejeitada pela regra de negócio: {resp.mensagem}")
            # Rejeição de negócio semântica
            return jsonify({
                "sucesso": False,
                "titular": resp.titular_origem,
                "saldo": resp.saldo_remanescente,
                "valor": resp.valor,
                "mensagem": resp.mensagem,
                "data_hora": resp.data_hora
            }), 400

    except grpc.RpcError as e:
        detalhes = e.details() if hasattr(e, "details") else str(e)
        status = e.code() if hasattr(e, "code") else "UNKNOWN"
        print(f"[GATEWAY ERRO] Falha gRPC ao comunicar com PixService em '{PIX_SERVICE_HOST}': {status} - {detalhes}")
        return jsonify({
            "sucesso": False,
            "alvo": PIX_SERVICE_HOST,
            "mensagem": f"Erro de comunicação com o microsserviço de transferências ({PIX_SERVICE_HOST}): {detalhes or status}"
        }), 503


@app.route("/pix/historico", methods=["GET"])
@app.route("/pix/historico/<chave_pix>", methods=["GET"])
@jwt_required
def listar_historico(chave_pix=None):
    """Consulta de histórico real persistido no banco de dados via gRPC PixService."""
    chave = (chave_pix or g.usuario.get("sub", "")).strip()

    print(f"[GATEWAY] [HISTÓRICO] Consultando histórico de '{chave}' via gRPC em {PIX_SERVICE_HOST}...")
    try:
        with grpc.insecure_channel(PIX_SERVICE_HOST) as channel:
            pix_stub = pix_pb2_grpc.PixServiceStub(channel)
            resp = pix_stub.ListarHistorico(
                pix_pb2.HistoricoRequest(chave_pix=chave),
                timeout=5.0
            )

        transacoes = []
        for t in resp.transacoes:
            transacoes.append({
                "id": t.id,
                "chave_origem": t.chave_origem,
                "titular_origem": t.titular_origem,
                "chave_destino": t.chave_destino,
                "titular_destino": t.titular_destino,
                "valor": t.valor,
                "status": t.status,
                "mensagem": t.mensagem,
                "data_hora": t.data_hora
            })

        return jsonify({
            "sucesso": True,
            "chave_pix": chave,
            "total": len(transacoes),
            "transacoes": transacoes
        }), 200

    except grpc.RpcError as e:
        detalhes = e.details() if hasattr(e, "details") else str(e)
        status = e.code() if hasattr(e, "code") else "UNKNOWN"
        print(f"[GATEWAY ERRO] Falha gRPC ao consultar histórico em PixService ({PIX_SERVICE_HOST}): {status} - {detalhes}")
        return jsonify({
            "sucesso": False,
            "alvo": PIX_SERVICE_HOST,
            "mensagem": f"Erro de comunicação com o serviço de Pix ({PIX_SERVICE_HOST}): {detalhes or status}"
        }), 503


@app.route("/pix/verificar", methods=["POST"])
@jwt_required
def verificar_pix_legado():
    """Rota legada de verificação, agora autenticada e delegando via gRPC."""
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({
            "sucesso": False,
            "mensagem": "Corpo da requisição deve ser um JSON válido."
        }), 400

    chave = dados.get("chave_pix", "").strip()
    valor_raw = dados.get("valor")

    if not chave or valor_raw is None:
        return jsonify({
            "sucesso": False,
            "mensagem": "Campos 'chave_pix' e 'valor' são obrigatórios."
        }), 400

    try:
        valor = float(valor_raw)
    except (ValueError, TypeError):
        return jsonify({
            "sucesso": False,
            "mensagem": "O campo 'valor' deve ser numérico."
        }), 400

    print(f"[GATEWAY] [VERIFICAR] Verificando Pix de '{chave}' (R$ {valor:.2f}) em {PIX_SERVICE_HOST}...")
    try:
        with grpc.insecure_channel(PIX_SERVICE_HOST) as channel:
            pix_stub = pix_pb2_grpc.PixServiceStub(channel)
            resp = pix_stub.VerificarPix(
                pix_pb2.PixRequest(chave_pix=chave, valor=valor),
                timeout=5.0
            )

        return jsonify({
            "sucesso": resp.sucesso,
            "titular": resp.titular,
            "saldo": resp.saldo,
            "valor": resp.valor,
            "mensagem": resp.mensagem
        }), 200

    except grpc.RpcError as e:
        detalhes = e.details() if hasattr(e, "details") else str(e)
        status = e.code() if hasattr(e, "code") else "UNKNOWN"
        print(f"[GATEWAY ERRO] Falha ao verificar Pix em PixService ({PIX_SERVICE_HOST}): {status} - {detalhes}")
        return jsonify({
            "sucesso": False,
            "alvo": PIX_SERVICE_HOST,
            "mensagem": f"Erro ao comunicar com PixService ({PIX_SERVICE_HOST}): {detalhes or status}"
        }), 503


def serve():
    porta = int(os.getenv("PORT", "50051"))
    print("=" * 65)
    print(f"[*] API Gateway REST (Flask) ATIVO na porta {porta}")
    print(f"[*] -> AccountService alvo : {ACCOUNT_SERVICE_HOST}")
    print(f"[*] -> PixService alvo     : {PIX_SERVICE_HOST}")
    print(f"[*] Escutando em: 0.0.0.0:{porta} (Interface Web e REST)")
    print("=" * 65)
    app.run(host="0.0.0.0", port=porta)


if __name__ == "__main__":
    serve()
