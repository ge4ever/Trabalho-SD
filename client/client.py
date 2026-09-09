import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "grpc-generated"))

import grpc
import pix_pb2
import pix_pb2_grpc


def run():
    server_host = os.getenv("SERVER_HOST", "localhost")
    endereco = f"{server_host}:50051"

    chave = sys.argv[1] if len(sys.argv) > 1 else "alice@pix.local"
    valor = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0

    print(f"[*] Conectando ao Servidor gRPC em {endereco}...")
    print(f"[*] Verificando Pix para '{chave}' no valor de R$ {valor:.2f}")

    with grpc.insecure_channel(endereco) as channel:
        stub = pix_pb2_grpc.PixServiceStub(channel)

        request = pix_pb2.PixRequest(
            chave_pix=chave,
            valor=valor
        )

        response = stub.VerificarPix(request)

    print("\n--- Resultado da Verificação Pix ---")
    print(f"Titular : {response.titular}")
    print(f"Saldo   : R$ {response.saldo:.2f}")
    print(f"Valor   : R$ {response.valor:.2f}")
    print(f"Resultado: {response.mensagem}")


if __name__ == "__main__":
    run()
