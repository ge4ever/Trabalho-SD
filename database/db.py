import os
import sqlite3
from pathlib import Path

# Tentativa de carregar psycopg2 para PostgreSQL
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


DB_DIR = Path(__file__).resolve().parent
SQLITE_PATH = DB_DIR / "banco_sd.db"

DB_HOST = os.getenv("DB_HOST", "35.202.26.114")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "banco_sd")
DB_USER = os.getenv("DB_USER", "sd_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "sd_password")


class DatabaseConnection:
    def __init__(self):
        self.driver = None
        self._detect_and_init_db()

    def _detect_and_init_db(self):
        # Tenta conectar ao PostgreSQL se configurado ou disponível
        if PSYCOPG2_AVAILABLE:
            try:
                conn = psycopg2.connect(
                    host=DB_HOST,
                    port=DB_PORT,
                    dbname=DB_NAME,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    connect_timeout=5
                )
                conn.close()
                self.driver = "postgres"
                print(f"[DATABASE] Conectado ao PostgreSQL com sucesso ({DB_HOST}:{DB_PORT}/{DB_NAME})")
                self._init_postgres()
                return
            except Exception as e:
                print(f"[DATABASE AVISO] Não foi possível conectar ao PostgreSQL ({DB_HOST}:{DB_PORT}/{DB_NAME}): {e}")
                print(f"[DATABASE] Utilizando fallback com SQLite real ({SQLITE_PATH}).")

        # Fallback para SQLite real persistente em arquivo
        self.driver = "sqlite"
        print(f"[DATABASE] Conectado ao SQLite real ({SQLITE_PATH})")
        self._init_sqlite()

    def _init_sqlite(self):
        conn = sqlite3.connect(SQLITE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave_pix TEXT UNIQUE NOT NULL,
                titular TEXT NOT NULL,
                saldo REAL NOT NULL DEFAULT 0.0,
                senha TEXT NOT NULL DEFAULT '123456',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transacoes (
                id TEXT PRIMARY KEY,
                chave_origem TEXT NOT NULL,
                titular_origem TEXT NOT NULL,
                chave_destino TEXT NOT NULL,
                titular_destino TEXT NOT NULL,
                valor REAL NOT NULL,
                status TEXT NOT NULL,
                mensagem TEXT,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Seeds iniciais se vazio
        cursor.execute("SELECT COUNT(*) FROM contas;")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("""
                INSERT INTO contas (chave_pix, titular, saldo, senha)
                VALUES (?, ?, ?, ?);
            """, [
                ("alice@pix.local", "Alice Silva", 1250.75, "123456"),
                ("bob@pix.local", "Bob Santos", 340.20, "123456"),
            ])
            conn.commit()
            print("[DATABASE] Contas iniciais reais populadas no SQLite com sucesso.")
        conn.close()

    def _init_postgres(self):
        conn = self._get_raw_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contas (
                id SERIAL PRIMARY KEY,
                chave_pix VARCHAR(120) UNIQUE NOT NULL,
                titular VARCHAR(150) NOT NULL,
                saldo NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                senha VARCHAR(100) NOT NULL DEFAULT '123456',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
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
        """)
        cursor.execute("""
            INSERT INTO contas (chave_pix, titular, saldo, senha) VALUES
            ('alice@pix.local', 'Alice Silva', 1250.75, '123456'),
            ('bob@pix.local', 'Bob Santos', 340.20, '123456')
            ON CONFLICT (chave_pix) DO NOTHING;
        """)
        conn.commit()
        cursor.close()
        conn.close()

    def _get_raw_conn(self):
        if self.driver == "postgres":
            return psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=5
            )
        else:
            conn = sqlite3.connect(SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            return conn

    def query_one(self, sql, params=()):
        conn = self._get_raw_conn()
        try:
            if self.driver == "sqlite":
                sql = sql.replace("%s", "?")
            cursor = conn.cursor()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            if row is None:
                return None
            if self.driver == "sqlite":
                return dict(row)
            else:
                desc = [d[0] for d in cursor.description]
                return dict(zip(desc, row))
        finally:
            conn.close()

    def query_all(self, sql, params=()):
        conn = self._get_raw_conn()
        try:
            if self.driver == "sqlite":
                sql = sql.replace("%s", "?")
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if self.driver == "sqlite":
                return [dict(r) for r in rows]
            else:
                desc = [d[0] for d in cursor.description]
                return [dict(zip(desc, r)) for r in rows]
        finally:
            conn.close()

    def execute(self, sql, params=()):
        conn = self._get_raw_conn()
        try:
            if self.driver == "sqlite":
                sql = sql.replace("%s", "?")
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


# Instância global reutilizável
db = DatabaseConnection()
