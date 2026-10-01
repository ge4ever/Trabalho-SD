import os
import sys
from flask import Flask, jsonify, request
import grpc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "grpc-generated"))

import pix_pb2
import pix_pb2_grpc

app = Flask(__name__)

ACCOUNT_SERVICE_HOST = os.getenv("ACCOUNT_SERVICE_HOST", "localhost:50052")


@app.route("/pix/saldo/<chave_pix>", methods=["GET"])
def consultar_saldo(chave_pix):
    print(f"[LOG] Consulta de saldo recebida para a chave: '{chave_pix}'")
    try:
        with grpc.insecure_channel(ACCOUNT_SERVICE_HOST) as channel:
            account_stub = pix_pb2_grpc.AccountServiceStub(channel)
            saldo_request = pix_pb2.SaldoRequest(chave_pix=chave_pix)
            conta = account_stub.ConsultarConta(saldo_request)

            status_code = 200 if conta.sucesso else 404
            return jsonify({
                "sucesso": conta.sucesso,
                "titular": conta.titular,
                "saldo": conta.saldo,
                "mensagem": conta.mensagem
            }), status_code
    except grpc.RpcError as e:
        print(f"[ERRO] Falha ao comunicar com AccountService: {e}")
        return jsonify({
            "sucesso": False,
            "mensagem": "Erro de comunicação com o serviço de contas (AccountService)."
        }), 503


@app.route("/pix/verificar", methods=["POST"])
def verificar_pix():
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({
            "sucesso": False,
            "mensagem": "Corpo da requisição deve ser um JSON válido."
        }), 400

    chave = dados.get("chave_pix")
    valor = dados.get("valor")

    if not chave or valor is None:
        return jsonify({
            "sucesso": False,
            "mensagem": "Campos 'chave_pix' e 'valor' são obrigatórios."
        }), 400

    try:
        valor = float(valor)
    except (ValueError, TypeError):
        return jsonify({
            "sucesso": False,
            "mensagem": "O campo 'valor' deve ser numérico."
        }), 400

    print(
        f"[LOG] Verificação de Pix para a chave "
        f"'{chave}' no valor de R$ {valor:.2f}"
    )

    try:
        with grpc.insecure_channel(ACCOUNT_SERVICE_HOST) as channel:
            account_stub = pix_pb2_grpc.AccountServiceStub(channel)
            saldo_request = pix_pb2.SaldoRequest(chave_pix=chave)
            conta = account_stub.ConsultarConta(saldo_request)

        # se a conta não foi encontrada, rejeita o Pix
        if not conta.sucesso:
            return jsonify({
                "sucesso": False,
                "titular": "",
                "saldo": 0.0,
                "valor": valor,
                "mensagem": "Pix não autorizado: chave Pix não encontrada."
            }), 200

        # o saldo precisa ser suficiente
        if conta.saldo >= valor:
            return jsonify({
                "sucesso": True,
                "titular": conta.titular,
                "saldo": conta.saldo,
                "valor": valor,
                "mensagem": "Pix autorizado."
            }), 200

        return jsonify({
            "sucesso": False,
            "titular": conta.titular,
            "saldo": conta.saldo,
            "valor": valor,
            "mensagem": "Pix não autorizado: saldo insuficiente."
        }), 200

    except grpc.RpcError as e:
        print(f"[ERRO] Falha ao comunicar com AccountService: {e}")
        return jsonify({
            "sucesso": False,
            "mensagem": "Erro de comunicação com o serviço de contas (AccountService)."
        }), 503


def serve():
    porta = int(os.getenv("PORT", 50051))
    print(f"[*] Servidor REST (PixService) ativo na porta {porta}...")
    app.run(host="0.0.0.0", port=porta)


if __name__ == "__main__":
    serve()

