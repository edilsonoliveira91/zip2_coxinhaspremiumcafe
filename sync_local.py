import subprocess
import sys
import time
import logging
import os
import urllib.request
from pathlib import Path
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
LOCAL_PASSWORD  = "Oliver169352"

PG_BIN          = r"C:\Program Files\PostgreSQL\18\bin"
DUMP_FILE       = r"C:\coxinhas_sync\dump.sql"
LOG_FILE        = r"C:\coxinhas_sync\sync.log"
INTERVAL        = 60  # segundos

RAILWAY_URL     = "https://zip2coxinhaspremiumcafe-production.up.railway.app"
MEDIA_LOCAL     = r"C:\Users\User\Documents\coxinhas\media"


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

    # 3. Sync de imagens
    sync_media()

    return True

def sync_media():
    """Baixa do Railway imagens que ainda não existem localmente."""
    # Tabelas e colunas com imagens
    queries = [
        "SELECT image FROM products_product WHERE image IS NOT NULL AND image != ''",
        "SELECT image FROM products_comboproduct WHERE image IS NOT NULL AND image != ''",
        "SELECT image FROM kiosk_kioskslide WHERE image IS NOT NULL AND image != ''",
    ]
    env_local = {**os.environ, "PGPASSWORD": LOCAL_PASSWORD}
    paths = []
    for sql in queries:
        r = subprocess.run([
            rf"{PG_BIN}\psql.exe",
            "-h", LOCAL_HOST, "-p", LOCAL_PORT,
            "-U", LOCAL_USER, "-d", LOCAL_DB,
            "-t", "-c", sql,
        ], env=env_local, capture_output=True, text=True)
        for line in r.stdout.splitlines():
            line = line.strip()
            if line:
                paths.append(line)

    downloaded = 0
    for rel_path in paths:
        dest = Path(MEDIA_LOCAL) / rel_path
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"{RAILWAY_URL}/media/{rel_path}"
        try:
            urllib.request.urlretrieve(url, dest)
            downloaded += 1
        except Exception as e:
            log(f"  Erro ao baixar {rel_path}: {e}", "warning")

    if downloaded:
        log(f"Imagens sincronizadas: {downloaded} arquivo(s) baixado(s).")
    else:
        log("Imagens: nenhuma nova para baixar.")


if __name__ == "__main__":
    log("=== Serviço de sync Railway → Local iniciado ===")
    log(f"Intervalo: {INTERVAL} segundos")

    while True:
        try:
            sync()
        except Exception as e:
            log(f"Exceção inesperada: {e}", "error")
        time.sleep(INTERVAL)
