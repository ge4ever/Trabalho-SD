import os
import sys
import requests


def run():
    server_host = os.getenv("SERVER_HOST", "localhost")
    server_port = os.getenv("SERVER_PORT", "50051")
    base_url = f"http://{server_host}:{server_port}"

    chave_origem = os.getenv("PIX_ORIGEM", "alice@pix.local")
    chave_destino = sys.argv[1] if len(sys.argv) > 1 else "bob@pix.local"
    try:
        valor = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
    except ValueError:
        print("[!] Valor inválido fornecido. Deve ser numérico.")
        return

    print(f"[*] Conectando ao API Gateway REST em {base_url}...")
    print(f"[*] Passo 1: Autenticando com JWT para a conta '{chave_origem}'...")

    # 1. Autenticação na Borda (API Gateway) para obter token JWT
    try:
        login_resp = requests.post(
            f"{base_url}/auth/login",
            json={"chave_pix": chave_origem, "senha": "123456"},
            timeout=5
        )
        if login_resp.status_code != 200:
            print(f"[!] Falha na autenticação (Status {login_resp.status_code}): {login_resp.text}")
            return

        token = login_resp.json().get("token")
        print(f"[*] JWT obtido com sucesso! ({token[:20]}...)")

        # 2. Execução da Transferência Pix autenticada
        print(f"[*] Passo 2: Executando transferência de R$ {valor:.2f} para '{chave_destino}'...")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "chave_origem": chave_origem,
            "chave_destino": chave_destino,
            "valor": valor,
            "descricao": "Transferência via CLI Client"
        }

        resp = requests.post(f"{base_url}/pix/transferir", json=payload, headers=headers, timeout=10)

        data = resp.json()
        print(f"\n--- Resultado da Operação (HTTP Status {resp.status_code}) ---")
        if resp.status_code == 201:
            print(f"Status      : SUCESSO (201 Created)")
            print(f"ID Transação: {data.get('transacao_id')}")
            print(f"Origem      : {data.get('titular_origem')} ({chave_origem})")
            print(f"Destino     : {data.get('titular_destino')} ({chave_destino})")
            print(f"Valor       : R$ {float(data.get('valor', 0.0)):.2f}")
            print(f"Saldo Atual : R$ {float(data.get('saldo', 0.0)):.2f}")
            print(f"Mensagem    : {data.get('mensagem')}")
            print(f"Data e Hora : {data.get('data_hora')}")
        else:
            print(f"Status      : RECUSADO / ERRO ({resp.status_code})")
            print(f"Mensagem    : {data.get('mensagem')}")
            if data.get("erros"):
                for err in data.get("erros"):
                    print(f" - {err}")

    except requests.exceptions.ConnectionError:
        print(f"[!] Erro: não foi possível conectar ao API Gateway em {base_url}.")
        print("[!] Verifique se o API Gateway (gateway/server.py) está ativo na porta 50051.")
    except Exception as e:
        print(f"[!] Erro inesperado na requisição: {e}")


if __name__ == "__main__":
    run()
