import os
import sys
import requests


def run():
    server_host = os.getenv("SERVER_HOST", "localhost")
    server_port = os.getenv("SERVER_PORT", "50051")
    url = f"http://{server_host}:{server_port}/pix/verificar"

    chave = sys.argv[1] if len(sys.argv) > 1 else "alice@pix.local"
    try:
        valor = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0
    except ValueError:
        print("[!] Valor inválido fornecido.")
        return

    print(f"[*] Conectando ao Servidor REST em {url}...")
    print(f"[*] Verificando Pix para '{chave}' no valor de R$ {valor:.2f}")

    try:
        response = requests.post(
            url,
            json={"chave_pix": chave, "valor": valor},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            print("\n--- Resultado da Verificação Pix ---")
            print(f"Titular : {data.get('titular', '')}")
            print(f"Saldo   : R$ {float(data.get('saldo', 0.0)):.2f}")
            print(f"Valor   : R$ {float(data.get('valor', 0.0)):.2f}")
            print(f"Resultado: {data.get('mensagem', '')}")
        else:
            try:
                erro = response.json().get("mensagem", response.text)
            except Exception:
                erro = response.text
            print(f"[!] Erro do servidor (Status {response.status_code}): {erro}")

    except requests.exceptions.ConnectionError:
        print(f"[!] Erro: não foi possível conectar ao servidor em {url}.")
        print("[!] Verifique se o PixService está em execução e acessível.")
    except requests.exceptions.RequestException as e:
        print(f"[!] Erro na requisição: {e}")


if __name__ == "__main__":
    run()

