import subprocess
import sys
import time
import logging
from datetime import datetime

# ── Configurações ────────────────────────────────────────────────────────────
REMOTE_HOST     = "switchyard.proxy.rlwy.net"
REMOTE_PORT     = "48072"
REMOTE_DB       = "railway"
REMOTE_USER     = "postgres"
REMOTE_PASSWORD = "VymtDMKopjCZdYzXmHbIiaOYwgLSKGQK"

LOCAL_HOST      = "localhost"
LOCAL_PORT      = "5432"
LOCAL_DB        = "coxinhas_local"
LOCAL_USER      = "postgres"
LOCAL_PASSWORD  = "postgres"   # senha definida na instalação local

PG_BIN          = r"C:\Program Files\PostgreSQL\18\bin"
DUMP_FILE       = r"C:\coxinhas_sync\dump.sql"
LOG_FILE        = r"C:\coxinhas_sync\sync.log"
INTERVAL        = 60  # segundos

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def log(msg, level="info"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    getattr(logging, level)(msg)

def sync():
    import os
    os.makedirs(r"C:\coxinhas_sync", exist_ok=True)

    env = {**__import__("os").environ, "PGPASSWORD": REMOTE_PASSWORD}

    # 1. pg_dump do Railway
    log("Iniciando dump do Railway...")
    dump = subprocess.run([
        rf"{PG_BIN}\pg_dump.exe",
        "-h", REMOTE_HOST,
        "-p", REMOTE_PORT,
        "-U", REMOTE_USER,
        "-d", REMOTE_DB,
        "-f", DUMP_FILE,
        "--no-owner",
        "--no-acl",
        "-c",          # inclui DROP antes de CREATE (clean restore)
    ], env=env, capture_output=True, text=True)

    if dump.returncode != 0:
        log(f"Erro no dump: {dump.stderr}", "error")
        return False

    log(f"Dump concluído.")

    # 2. Restore no banco local
    env_local = {**__import__("os").environ, "PGPASSWORD": LOCAL_PASSWORD}

    restore = subprocess.run([
        rf"{PG_BIN}\psql.exe",
        "-h", LOCAL_HOST,
        "-p", LOCAL_PORT,
        "-U", LOCAL_USER,
        "-d", LOCAL_DB,
        "-f", DUMP_FILE,
        "-q",  # quiet
    ], env=env_local, capture_output=True, text=True)

    if restore.returncode != 0:
        log(f"Erro no restore: {restore.stderr}", "error")
        return False

    log("Sync concluído com sucesso.")
    return True

if __name__ == "__main__":
    log("=== Serviço de sync Railway → Local iniciado ===")
    log(f"Intervalo: {INTERVAL} segundos")

    while True:
        try:
            sync()
        except Exception as e:
            log(f"Exceção inesperada: {e}", "error")
        time.sleep(INTERVAL)
