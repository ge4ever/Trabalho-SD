from concurrent import futures
import grpc
import pix_pb2
import pix_pb2_grpc


CONTAS_MOCK = {
    "alice@pix.local": {
        "titular": "Alice Silva",
        "saldo": 1250.75
    },
    "bob@pix.local": {
        "titular": "Bob Santos",
        "saldo": 340.20
    },
}


class AccountServicer(pix_pb2_grpc.AccountServiceServicer):

    def ConsultarConta(self, request, context):
        chave = request.chave_pix

        print(f"[ACCOUNT] Consulta recebida para: '{chave}'")

        if chave in CONTAS_MOCK:
            conta = CONTAS_MOCK[chave]

            return pix_pb2.SaldoResponse(
                sucesso=True,
                titular=conta["titular"],
                saldo=conta["saldo"],
                mensagem="Conta localizada com sucesso."
            )

        return pix_pb2.SaldoResponse(
            sucesso=False,
            titular="",
            saldo=0.0,
            mensagem="Chave Pix não encontrada."
        )


def serve():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=5)
    )

    pix_pb2_grpc.add_AccountServiceServicer_to_server(
        AccountServicer(),
        server
    )

    server.add_insecure_port("0.0.0.0:50052")

    print("[*] Microserviço de contas ativo na porta 50052...")

    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
