from flask import Flask, jsonify, request
from pydantic import BaseModel, ValidationError, Field
import uuid

from database import get_connection


app = Flask(__name__)


class ContaRequest(BaseModel):
    chave_pix: str = Field(min_length=1)
    titular: str = Field(min_length=1)
    saldo: float = Field(ge=0)


@app.post("/contas")
def criar_conta():
    try:
        dados = ContaRequest.model_validate(request.get_json())

    except ValidationError as erro:
        erros = {}

        for item in erro.errors():
            campo = item["loc"][0]
            erros[campo] = item["msg"]

        return jsonify({
            "mensagem": "Dados da conta inválidos",
            "erros": erros
        }), 400

    conta_id = uuid.uuid4()

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO contas (id, chave_pix, titular, saldo)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        conta_id,
                        dados.chave_pix,
                        dados.titular,
                        dados.saldo
                    )
                )

        return jsonify({
            "id": str(conta_id),
            "chave_pix": dados.chave_pix,
            "titular": dados.titular,
            "saldo": dados.saldo,
            "mensagem": "Conta criada com sucesso."
        }), 201

    except Exception as erro:
        return jsonify({
            "mensagem": "Erro ao criar conta",
            "erro": str(erro)
        }), 500


@app.get("/contas/<chave_pix>")
def consultar_conta(chave_pix):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT titular, saldo
                FROM contas
                WHERE chave_pix = %s
                """,
                (chave_pix,)
            )

            conta = cursor.fetchone()

    if conta is None:
        return jsonify({
            "sucesso": False,
            "titular": "",
            "saldo": 0.0,
            "mensagem": "Chave Pix não encontrada."
        }), 404

    return jsonify({
        "sucesso": True,
        "titular": conta[0],
        "saldo": float(conta[1]),
        "mensagem": "Conta localizada com sucesso."
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=50052)
