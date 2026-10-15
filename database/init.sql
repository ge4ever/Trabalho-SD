-- Script de inicialização do banco de dados relacional (PostgreSQL / SQLite)

CREATE TABLE IF NOT EXISTS contas (
    id SERIAL PRIMARY KEY,
    chave_pix VARCHAR(120) UNIQUE NOT NULL,
    titular VARCHAR(150) NOT NULL,
    saldo NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    senha VARCHAR(100) NOT NULL DEFAULT '123456',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transacoes (
    id VARCHAR(64) PRIMARY KEY,
    chave_origem VARCHAR(120) NOT NULL,
    titular_origem VARCHAR(150) NOT NULL,
    chave_destino VARCHAR(120) NOT NULL,
    titular_destino VARCHAR(150) NOT NULL,
    valor NUMERIC(12, 2) NOT NULL,
    status VARCHAR(30) NOT NULL,
    mensagem TEXT,
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- População de contas iniciais reais
INSERT INTO contas (chave_pix, titular, saldo, senha) VALUES
('alice@pix.local', 'Alice Silva', 1250.75, '123456'),
('bob@pix.local', 'Bob Santos', 340.20, '123456')
ON CONFLICT (chave_pix) DO NOTHING;
