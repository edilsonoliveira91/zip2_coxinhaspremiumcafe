import subprocess
import sys
import time
import logging
import os
import socket
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

# ── Configurações ──
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
INTERVAL        = 60

RAILWAY_URL     = "https://zip2coxinhaspremiumcafe-production.up.railway.app"
MEDIA_LOCAL     = r"C:\Users\User\Documents\coxinhas\media"

COUNT_TABLES = [
    "accounts_user",
    "orders_order",
    "checkouts_checkout",
    "products_product",
    "financials_fechamentocaixadiario",
    "financials_sangria",
]

# Fingerprint do ultimo sync (em memoria)
last_fingerprint = None

# ── Logging ──
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def log(msg, level="info"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    getattr(logging, level)(msg)


# ── SyncLog ──
def write_sync_log(started_at, finished_at, status, error_message=None,
                   records_downloaded=0, images_downloaded=0, tables_synced=None):
    """
    Insere um registro em utils_synclog no banco local via psycopg2.
    Chamado APOS o restore para que persista no banco local.
    """
    try:
        import psycopg2
    except ImportError:
        log("psycopg2 nao disponivel -- SyncLog nao gravado.", "warning")
        return

    duration = (finished_at - started_at).total_seconds()
    local_ip = None
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        pass

    tables_str = tables_synced or "dump completo Railway -> Local"

    try:
        conn = psycopg2.connect(
            host=LOCAL_HOST,
            port=LOCAL_PORT,
            dbname=LOCAL_DB,
            user=LOCAL_USER,
            password=LOCAL_PASSWORD,
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO utils_synclog
                (started_at, finished_at, duration_seconds, direction,
                 status, error_message, records_downloaded, records_uploaded,
                 records_created, records_updated, records_deleted,
                 images_downloaded, tables_synced, sync_from_datetime,
                 triggered_by, local_server_ip)
            VALUES
                (%s, %s, %s, 'railway_to_local',
                 %s, %s, %s, 0,
                 0, 0, 0,
                 %s, %s, NULL,
                 'automatic', %s)
        """, (
            started_at, finished_at, duration,
            status, error_message, records_downloaded,
            images_downloaded, tables_str, local_ip,
        ))
        cur.close()
        conn.close()
        log(f"SyncLog gravado: {status} | {duration:.1f}s | {records_downloaded} registros")
    except Exception as e:
        log(f"Erro ao gravar SyncLog: {e}", "error")


def count_local_records():
    """Conta total de registros nas tabelas principais apos o restore."""
    env_local = {**os.environ, "PGPASSWORD": LOCAL_PASSWORD}
    total = 0
    for table in COUNT_TABLES:
        r = subprocess.run([
            rf"{PG_BIN}\psql.exe",
            "-h", LOCAL_HOST, "-p", LOCAL_PORT,
            "-U", LOCAL_USER, "-d", LOCAL_DB,
            "-t", "-c", f"SELECT COUNT(*) FROM {table};",
        ], env=env_local, capture_output=True, text=True)
        try:
            total += int(r.stdout.strip())
        except ValueError:
            pass
    return total



def get_remote_fingerprint():
    """
    Consulta Railway via psycopg2 e retorna uma string resumo do estado atual
    (max id + count das tabelas principais). Rapido e sem dump.
    Retorna None em caso de erro (forcara o sync).
    """
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=REMOTE_HOST,
            port=int(REMOTE_PORT),
            dbname=REMOTE_DB,
            user=REMOTE_USER,
            password=REMOTE_PASSWORD,
            connect_timeout=10,
        )
        conn.autocommit = True
        cur = conn.cursor()
        parts = []
        for table in COUNT_TABLES:
            try:
                cur.execute(f"SELECT COUNT(*), COALESCE(MAX(id), 0) FROM {table}")
                count, max_id = cur.fetchone()
                parts.append(f"{table}:{count}:{max_id}")
            except Exception:
                pass
        cur.close()
        conn.close()
        return "|".join(parts)
    except Exception as e:
        log(f"Fingerprint: erro ao consultar Railway ({e}) -- forcando sync", "warning")
        return None


def sync():
    global last_fingerprint
    os.makedirs(r"C:\coxinhas_sync", exist_ok=True)

    # Verificar se houve mudanca no Railway antes de fazer o dump
    current_fingerprint = get_remote_fingerprint()
    if current_fingerprint is not None and current_fingerprint == last_fingerprint:
        log("Sem mudancas no Railway -- sync ignorado.")
        return True
    last_fingerprint = current_fingerprint

    started_at = datetime.now(timezone.utc)
    env = {**os.environ, "PGPASSWORD": REMOTE_PASSWORD}

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
        "-c",
    ], env=env, capture_output=True, text=True)

    if dump.returncode != 0:
        err = dump.stderr.strip()
        log(f"Erro no dump: {err}", "error")
        write_sync_log(
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            status="error",
            error_message=f"pg_dump falhou: {err[:500]}",
        )
        return False

    log("Dump concluido.")

    # 2. Restore no banco local
    env_local = {**os.environ, "PGPASSWORD": LOCAL_PASSWORD}

    restore = subprocess.run([
        rf"{PG_BIN}\psql.exe",
        "-h", LOCAL_HOST,
        "-p", LOCAL_PORT,
        "-U", LOCAL_USER,
        "-d", LOCAL_DB,
        "-f", DUMP_FILE,
        "-q",
    ], env=env_local, capture_output=True, text=True)

    if restore.returncode != 0:
        err = restore.stderr.strip()
        log(f"Erro no restore: {err}", "error")
        write_sync_log(
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            status="error",
            error_message=f"psql restore falhou: {err[:500]}",
        )
        return False

    log("Restore concluido.")

    # 3. Sync de imagens
    images_downloaded = sync_media()

    # 4. Contagem de registros
    records = count_local_records()

    # 5. Gravar SyncLog (APOS restore -- garante persistencia)
    write_sync_log(
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        status="success",
        records_downloaded=records,
        images_downloaded=images_downloaded,
        tables_synced=", ".join(COUNT_TABLES),
    )

    log("Sync concluido com sucesso.")
    return True


def sync_media():
    """Baixa do Railway imagens que ainda nao existem localmente. Retorna contagem."""
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

    return downloaded


if __name__ == "__main__":
    log("=== Servico de sync Railway -> Local iniciado ===")
    log(f"Intervalo: {INTERVAL} segundos")

    while True:
        try:
            sync()
        except Exception as e:
            log(f"Excecao inesperada: {e}", "error")
        time.sleep(INTERVAL)
