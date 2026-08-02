from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "printer_jobs.db"
INDEX_PATH = BASE_DIR / "index.html"
SETTINGS_PATH = BASE_DIR / "settings.html"
MOBILE_PATH = BASE_DIR / "mobile.html"
LOGIN_PATH = BASE_DIR / "login.html"
ASSETS_PATH = BASE_DIR / "assets"
PAGE_SIZE = 10
ADMIN_USERNAME = os.getenv("IPRINT_ADMIN_USERNAME", "i-print")
ADMIN_PASSWORD = os.getenv("IPRINT_ADMIN_PASSWORD", "ssu")
AUTH_SECRET = os.getenv("IPRINT_AUTH_SECRET", "iprint-local-session-secret-change-before-public")
AUTH_COOKIE_NAME = "iprint_admin_session"
AUTH_COOKIE_MAX_AGE = 60 * 60 * 12
PC_5800X_AGENT_URL = "http://100.117.206.9:8898/status"
MAC_MINI_AGENT_URL = "http://100.116.128.62:8898/status"
TELEGRAM_ALERT_ENV_PATHS = (
    BASE_DIR / ".env",
    Path("/home/bourne/telegram-gateway/telegram_gateway.env"),
)
TELEGRAM_ALERT_CHECK_INTERVAL_SECONDS = int(
    os.getenv("IPRINT_TELEGRAM_ALERT_CHECK_INTERVAL_SECONDS", "60")
)
PRINTER_QUEUE_ALERT_THRESHOLD_MINUTES = int(
    os.getenv("IPRINT_PRINTER_QUEUE_ALERT_MINUTES", "3")
)
TELEGRAM_ALERT_STATE_PATH = BASE_DIR / "Backup" / "telegram_alert_state.json"

app = FastAPI(title="i-Print Dashboard")
app.mount("/assets", StaticFiles(directory=ASSETS_PATH), name="assets")
_telegram_alert_thread_started = False


def _load_env_file_if_present(path: Path) -> None:
    if not path.exists():
        return
    try:
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            os.environ.setdefault(key, value)
    except OSError as error:
        logging.getLogger("i_print_telegram_alerts").warning(
            "텔레그램 환경 파일을 읽지 못했습니다: %s", error
        )


for _telegram_env_path in TELEGRAM_ALERT_ENV_PATHS:
    _load_env_file_if_present(_telegram_env_path)


def _load_alert_state() -> dict[str, bool]:
    try:
        raw = TELEGRAM_ALERT_STATE_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(key): bool(value) for key, value in data.items()}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def _save_alert_state(state: dict[str, bool]) -> None:
    TELEGRAM_ALERT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TELEGRAM_ALERT_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _parse_chat_ids(raw: str) -> list[str]:
    chat_ids: list[str] = []
    for token in re.split(r"[\s,]+", str(raw or "").strip()):
        if token:
            chat_ids.append(token)
    return chat_ids


def _send_telegram_message(message: str) -> bool:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids = _parse_chat_ids(os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", ""))
    if not bot_token or not chat_ids:
        logging.getLogger("i_print_telegram_alerts").warning(
            "텔레그램 토큰 또는 chat_id가 없어 알림을 보낼 수 없습니다."
        )
        return False

    success = False
    for chat_id in chat_ids:
        payload = urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=payload,
            method="POST",
        )
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if 200 <= getattr(response, "status", 0) < 300:
                    success = True
        except Exception as error:
            logging.getLogger("i_print_telegram_alerts").warning(
                "텔레그램 발송 실패(%s): %s", chat_id, error
            )
    return success


def _device_is_online(payload: dict[str, Any]) -> bool:
    return bool(payload.get("agent_reachable")) and str(payload.get("pc_status", "")).lower() == "online"


def _fetch_json(url: str) -> dict[str, Any]:
    if url.endswith("/api/devices/5800x/status"):
        return get_5800x_status()
    if url.endswith("/api/devices/macmini/status"):
        return get_macmini_status()
    with urllib.request.urlopen(url, timeout=6) as response:
        return json.loads(response.read().decode("utf-8"))


def _build_alert_message(device_name: str, online: bool, payload: dict[str, Any], error: str = "") -> str:
    state_label = "복구" if online else "오프라인"
    pc_status = str(payload.get("pc_status") or "Unknown")
    tailscale_status = str(payload.get("tailscale_status") or "Unknown")
    agent_status = "연결됨" if payload.get("agent_reachable") else "연결 안 됨"
    lines = [
        f"[I-PRINT {state_label}] {device_name}",
        f"PC 상태: {pc_status}",
        f"Tailscale 상태: {tailscale_status}",
        f"에이전트: {agent_status}",
    ]
    if error:
        lines.append(f"오류: {error}")
    return "\n".join(lines)


def _parse_wait_time_minutes(wait_time: Any) -> float | None:
    text = str(wait_time or "").strip().lower()
    if not text:
        return None

    minute_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes|m|분)", text)
    if minute_match:
        return float(minute_match.group(1))

    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hour|hours|hr|hrs|h|시간)", text)
    if hour_match:
        return float(hour_match.group(1)) * 60.0

    time_match = re.search(r"^(\d+):(\d{1,2})(?::(\d{1,2}))?$", text)
    if time_match:
        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        seconds = int(time_match.group(3) or 0)
        return hours * 60.0 + minutes + seconds / 60.0

    return None


def _summarize_queue_targets(items: list[dict[str, Any]]) -> str:
    names: list[str] = []
    for item in items:
        name = str(item.get("computer_name") or "Unknown").strip()
        if name and name not in names:
            names.append(name)
    if not names:
        return "Unknown"
    if len(names) == 1:
        return names[0]
    return f"{names[0]} 외 {len(names) - 1}대"


def _build_printer_queue_message(items: list[dict[str, Any]], longest_wait: float) -> str:
    top = items[0]
    target_pc = _summarize_queue_targets(items)
    lines = [
        "[I-PRINT 대기열 3분 초과]",
        f"대상 PC: {target_pc}",
        f"초과 대기 작업: {len(items)}건",
        f"최대 대기: {longest_wait:.1f}분",
        (
            "최대 작업: "
            f"{top.get('computer_name', 'Unknown')} / "
            f"{top.get('printer_name', 'Unknown')} / "
            f"{top.get('user_name', 'Unknown')} / "
            f"{top.get('document_name', 'Unknown')}"
        ),
        f"작업 상태: {top.get('status', 'Queued')} · 대기: {top.get('wait_time', '-')}",
    ]
    return "\n".join(lines)


def _check_printer_queue_and_notify(state: dict[str, bool]) -> None:
    queue_items: list[dict[str, Any]] = []
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, computer_name, printer_name, user_name,
                   document_name, status, wait_time, details
            FROM printer_jobs
            WHERE (
                   LOWER(status) LIKE 'queued%'
                OR LOWER(status) LIKE 'queue%'
                OR LOWER(status) LIKE 'waiting%'
            )
              AND LOWER(COALESCE(document_name, '')) NOT LIKE 'sample_document_%'
            ORDER BY id DESC
            LIMIT 50
            """
        ).fetchall()

    for row in rows:
        wait_minutes = _parse_wait_time_minutes(row["wait_time"])
        if wait_minutes is None:
            continue
        item = dict(row)
        item["wait_minutes"] = wait_minutes
        queue_items.append(item)

    over_threshold = [item for item in queue_items if item["wait_minutes"] >= PRINTER_QUEUE_ALERT_THRESHOLD_MINUTES]
    active = bool(over_threshold)
    previous = state.get("printer_queue_3m")

    if previous is None:
        state["printer_queue_3m"] = active
        _save_alert_state(state)
        if active:
            longest = max(item["wait_minutes"] for item in over_threshold)
            _send_telegram_message(_build_printer_queue_message(sorted(over_threshold, key=lambda item: item["wait_minutes"], reverse=True), longest))
        return

    if previous == active:
        if active:
            longest = max(item["wait_minutes"] for item in over_threshold)
            _send_telegram_message(
                _build_printer_queue_message(
                    sorted(over_threshold, key=lambda item: item["wait_minutes"], reverse=True),
                    longest,
                )
            )
        return

    state["printer_queue_3m"] = active
    _save_alert_state(state)

    if active:
        longest = max(item["wait_minutes"] for item in over_threshold)
        _send_telegram_message(_build_printer_queue_message(sorted(over_threshold, key=lambda item: item["wait_minutes"], reverse=True), longest))
    else:
        _send_telegram_message(
            "[I-PRINT 대기열 해소]\n"
            f"{PRINTER_QUEUE_ALERT_THRESHOLD_MINUTES}분 초과 대기열이 해소되었습니다."
        )


def _check_device_and_notify(device_key: str, device_name: str, status_url: str, state: dict[str, bool]) -> None:
    payload: dict[str, Any]
    online = False
    error_message = ""
    try:
        payload = _fetch_json(status_url)
        online = _device_is_online(payload)
    except Exception as error:
        payload = {
            "pc_status": "Offline",
            "tailscale_status": "Offline",
            "agent_reachable": False,
        }
        error_message = str(error)
        online = False

    previous = state.get(device_key)
    if previous is None:
        state[device_key] = online
        _save_alert_state(state)
        if not online:
            _send_telegram_message(_build_alert_message(device_name, online, payload, error_message))
        return

    if previous == online:
        if not online:
            _send_telegram_message(
                _build_alert_message(device_name, online, payload, error_message)
            )
        return

    state[device_key] = online
    _save_alert_state(state)
    _send_telegram_message(_build_alert_message(device_name, online, payload, error_message))


def _telegram_alert_loop() -> None:
    logger = logging.getLogger("i_print_telegram_alerts")
    logger.info("텔레그램 상태 감시 시작: %s초 간격", TELEGRAM_ALERT_CHECK_INTERVAL_SECONDS)
    state = _load_alert_state()
    while True:
        try:
            _check_device_and_notify("5800x", "5800X", "http://127.0.0.1:8897/api/devices/5800x/status", state)
            _check_device_and_notify("macmini", "Mac mini", "http://127.0.0.1:8897/api/devices/macmini/status", state)
            _check_printer_queue_and_notify(state)
        except Exception as error:
            logger.exception("텔레그램 상태 감시 중 오류: %s", error)
        time.sleep(TELEGRAM_ALERT_CHECK_INTERVAL_SECONDS)


def _start_telegram_alert_monitor() -> None:
    global _telegram_alert_thread_started
    if _telegram_alert_thread_started:
        return
    thread = threading.Thread(target=_telegram_alert_loop, name="i-print-telegram-alert-monitor", daemon=True)
    thread.start()
    _telegram_alert_thread_started = True


def create_auth_token() -> str:
    return hmac.new(
        AUTH_SECRET.encode("utf-8"),
        ADMIN_USERNAME.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def is_authenticated(request: Request) -> bool:
    received_token = request.cookies.get(AUTH_COOKIE_NAME, "")
    return bool(received_token) and hmac.compare_digest(received_token, create_auth_token())


@app.middleware("http")
async def require_admin_login(request: Request, call_next):
    public_paths = {"/login", "/api/login", "/health"}
    path = request.url.path

    if path in public_paths or path.startswith("/assets/"):
        return await call_next(request)

    if is_authenticated(request):
        return await call_next(request)

    if path.startswith("/api/"):
        return JSONResponse({"ok": False, "detail": "로그인이 필요합니다."}, status_code=401)

    return RedirectResponse(url="/login", status_code=302)


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS printer_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                computer_name TEXT NOT NULL,
                printer_name TEXT NOT NULL,
                user_name TEXT NOT NULL,
                document_name TEXT NOT NULL,
                status TEXT NOT NULL,
                wait_time TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_printer_jobs_created_at ON printer_jobs(created_at DESC)"
        )

        count = connection.execute("SELECT COUNT(*) FROM printer_jobs").fetchone()[0]
        if count == 0:
            sample_rows = []
            statuses = ["Completed", "Queued", "Printing", "Error"]
            for number in range(1, 36):
                pc_number = ((number - 1) % 12) + 1
                computer = "5800X" if pc_number == 1 else "Mac mini" if pc_number == 2 else f"Remote PC {pc_number:02d}"
                printer = "No Printer Connected" if pc_number <= 2 else f"Printer {pc_number:02d}"
                status = statuses[number % len(statuses)]
                sample_rows.append(
                    (
                        f"2026-08-01 {1 + (number // 20):02d}:{(number * 3) % 60:02d}:{(number * 7) % 60:02d}",
                        computer,
                        printer,
                        f"user-{pc_number:02d}",
                        f"sample_document_{number:02d}.pdf",
                        status,
                        f"{number % 9} min",
                        "Dashboard sample record",
                    )
                )
            connection.executemany(
                """
                INSERT INTO printer_jobs (
                    created_at, computer_name, printer_name, user_name,
                    document_name, status, wait_time, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                sample_rows,
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS managed_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                computer_name TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                operating_system TEXT NOT NULL DEFAULT 'Windows',
                tailscale_ip TEXT NOT NULL DEFAULT '',
                agent_port INTEGER NOT NULL DEFAULT 8898,
                status_key TEXT NOT NULL DEFAULT '',
                display_order INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        device_count = connection.execute("SELECT COUNT(*) FROM managed_devices").fetchone()[0]
        if device_count == 0:
            seed_devices = [
                ("5800X", "DESKTOP-5S6BVJE", "관리 장비", "Windows 11 Home", "100.117.206.9", 8898, "5800x", 1),
                ("Mac mini", "MacMiniui-Macmini.local", "관리 장비", "macOS", "100.116.128.62", 8898, "macmini", 2),
                ("학생회관 01", "", "학생회관", "Windows", "", 8898, "", 3),
                ("학생회관 02", "", "학생회관", "Windows", "", 8898, "", 4),
                ("학생회관 03", "", "학생회관", "Windows", "", 8898, "", 5),
                ("학생회관 04", "", "학생회관", "Windows", "", 8898, "", 6),
                ("학생회관 05", "", "학생회관", "Windows", "", 8898, "", 7),
                ("학생회관 06", "", "학생회관", "Windows", "", 8898, "", 8),
                ("베어드홀", "", "베어드홀", "Windows", "", 8898, "", 9),
                ("숭덕경상관", "", "숭덕경상관", "Windows", "", 8898, "", 10),
                ("문화관", "", "문화관", "Windows", "", 8898, "", 11),
                ("미래관", "", "미래관", "Windows", "", 8898, "", 12),
                ("형남공학관", "", "형남공학관", "Windows", "", 8898, "", 13),
                ("교육관", "", "교육관", "Windows", "", 8898, "", 14),
                ("백마관", "", "백마관", "Windows", "", 8898, "", 15),
                ("한경직기념관", "", "한경직기념관", "Windows", "", 8898, "", 16),
                ("벤처중소기업센터", "", "벤처중소기업센터", "Windows", "", 8898, "", 17),
                ("신양관", "", "신양관", "Windows", "", 8898, "", 18),
                ("진리관", "", "진리관", "Windows", "", 8898, "", 19),
                ("중앙도서관", "", "중앙도서관", "Windows", "", 8898, "", 20),
                ("연구관", "", "연구관", "Windows", "", 8898, "", 21),
                ("창신관", "", "창신관", "Windows", "", 8898, "", 22),
                ("Residence Hall", "", "Residence Hall", "Windows", "", 8898, "", 23),
                ("전산관", "", "전산관", "Windows", "", 8898, "", 24),
                ("정보과학관", "", "정보과학관", "Windows", "", 8898, "", 25),
                ("웨스트민스터홀", "", "웨스트민스터홀", "Windows", "", 8898, "", 26),
                ("창의관", "", "창의관", "Windows", "", 8898, "", 27),
            ]
            connection.executemany(
                """
                INSERT INTO managed_devices (
                    display_name, computer_name, location, operating_system,
                    tailscale_ip, agent_port, status_key, display_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                seed_devices,
            )
        connection.commit()


@app.on_event("startup")
def startup_event() -> None:
    initialize_database()
    _start_telegram_alert_monitor()


@app.get("/login")
def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=302)
    return FileResponse(LOGIN_PATH)


@app.post("/api/login")
async def login(request: Request):
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse({"ok": False, "detail": "로그인 정보를 확인해주세요."}, status_code=400)

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    username_matches = hmac.compare_digest(username, ADMIN_USERNAME)
    password_matches = hmac.compare_digest(password, ADMIN_PASSWORD)

    if not (username_matches and password_matches):
        return JSONResponse({"ok": False, "detail": "아이디 또는 비밀번호가 올바르지 않습니다."}, status_code=401)

    response = JSONResponse({"ok": True})
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=create_auth_token(),
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


@app.get("/")
async def dashboard(request: Request):
    force_view = request.query_params.get("view", "").lower()

    if force_view == "pc":
        return FileResponse(INDEX_PATH)

    user_agent = request.headers.get("user-agent", "").lower()
    mobile_keywords = (
        "android",
        "iphone",
        "ipad",
        "ipod",
        "mobile",
    )

    if any(keyword in user_agent for keyword in mobile_keywords):
        return RedirectResponse(url="/mobile", status_code=302)

    return FileResponse(INDEX_PATH)


@app.get("/settings")
def settings_page() -> FileResponse:
    return FileResponse(SETTINGS_PATH)


@app.get("/mobile")
def mobile_dashboard() -> FileResponse:
    return FileResponse(MOBILE_PATH)


def serialize_device(row: sqlite3.Row) -> dict[str, Any]:
    tailscale_ip = row["tailscale_ip"] or ""
    agent_port = int(row["agent_port"] or 8898)
    return {
        "id": row["id"],
        "name": row["display_name"],
        "computer_name": row["computer_name"],
        "location": row["location"],
        "os": row["operating_system"],
        "tailscale_ip": tailscale_ip,
        "agent_port": agent_port,
        "status_key": row["status_key"],
        "display_order": row["display_order"],
        "enabled": bool(row["enabled"]),
        "address": f"Tailscale {tailscale_ip}" if tailscale_ip else "Agent Not Installed",
        "status_url": f"http://{tailscale_ip}:{agent_port}/status" if tailscale_ip else "",
    }


@app.get("/api/devices")
def list_managed_devices() -> dict[str, Any]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, display_name, computer_name, location, operating_system,
                   tailscale_ip, agent_port, status_key, display_order, enabled
            FROM managed_devices
            WHERE enabled = 1
            ORDER BY display_order ASC, id ASC
            """
        ).fetchall()
    return {"items": [serialize_device(row) for row in rows]}


@app.post("/api/admin/devices")
async def create_managed_device(request: Request):
    payload = await request.json()
    display_name = str(payload.get("name", "")).strip()
    if not display_name:
        return JSONResponse({"ok": False, "detail": "장비 이름을 입력해주세요."}, status_code=400)
    location = str(payload.get("location", "")).strip()
    computer_name = str(payload.get("computer_name", "")).strip()
    operating_system = str(payload.get("os", "Windows")).strip() or "Windows"
    tailscale_ip = str(payload.get("tailscale_ip", "")).strip()
    agent_port = int(payload.get("agent_port", 8898) or 8898)
    with get_connection() as connection:
        next_order = connection.execute(
            "SELECT COALESCE(MAX(display_order), 0) + 1 FROM managed_devices"
        ).fetchone()[0]
        cursor = connection.execute(
            """
            INSERT INTO managed_devices (
                display_name, computer_name, location, operating_system,
                tailscale_ip, agent_port, display_order, enabled, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            """,
            (display_name, computer_name, location, operating_system, tailscale_ip, agent_port, next_order),
        )
        connection.commit()
        device_id = cursor.lastrowid
    return {"ok": True, "id": device_id}


@app.put("/api/admin/devices/{device_id}")
async def update_managed_device(device_id: int, request: Request):
    payload = await request.json()
    display_name = str(payload.get("name", "")).strip()
    if not display_name:
        return JSONResponse({"ok": False, "detail": "장비 이름을 입력해주세요."}, status_code=400)
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM managed_devices WHERE id = ? AND enabled = 1", (device_id,)
        ).fetchone()
        if existing is None:
            return JSONResponse({"ok": False, "detail": "장비를 찾을 수 없습니다."}, status_code=404)
        connection.execute(
            """
            UPDATE managed_devices
            SET display_name = ?, computer_name = ?, location = ?, operating_system = ?,
                tailscale_ip = ?, agent_port = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                display_name,
                str(payload.get("computer_name", "")).strip(),
                str(payload.get("location", "")).strip(),
                str(payload.get("os", "Windows")).strip() or "Windows",
                str(payload.get("tailscale_ip", "")).strip(),
                int(payload.get("agent_port", 8898) or 8898),
                device_id,
            ),
        )
        connection.commit()
    return {"ok": True}


@app.delete("/api/admin/devices/{device_id}")
def delete_managed_device(device_id: int):
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE managed_devices SET enabled = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND enabled = 1",
            (device_id,),
        )
        connection.commit()
    if cursor.rowcount == 0:
        return JSONResponse({"ok": False, "detail": "장비를 찾을 수 없습니다."}, status_code=404)
    return {"ok": True}


@app.put("/api/admin/device-order")
async def reorder_managed_devices(request: Request):
    payload = await request.json()
    ordered_ids = payload.get("ordered_ids", [])
    if not isinstance(ordered_ids, list) or not ordered_ids:
        return JSONResponse({"ok": False, "detail": "저장할 장비 순서가 없습니다."}, status_code=400)
    with get_connection() as connection:
        for position, raw_id in enumerate(ordered_ids, start=1):
            connection.execute(
                "UPDATE managed_devices SET display_order = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND enabled = 1",
                (position, int(raw_id)),
            )
        connection.commit()
    return {"ok": True}


@app.get("/api/printer-jobs")
def list_printer_jobs(
    page: int = Query(default=1, ge=1),
    search: str = Query(default="", max_length=100),
) -> dict[str, Any]:
    search_text = search.strip()
    where_clause = ""
    parameters: list[Any] = []

    if search_text:
        where_clause = """
        WHERE computer_name LIKE ?
           OR printer_name LIKE ?
           OR user_name LIKE ?
           OR document_name LIKE ?
           OR status LIKE ?
        """
        pattern = f"%{search_text}%"
        parameters.extend([pattern] * 5)

    with get_connection() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM printer_jobs {where_clause}",
            parameters,
        ).fetchone()[0]

        total_pages = max(1, math.ceil(total / PAGE_SIZE))
        current_page = min(page, total_pages)
        offset = (current_page - 1) * PAGE_SIZE

        rows = connection.execute(
            f"""
            SELECT id, created_at, computer_name, printer_name, user_name,
                   document_name, status, wait_time, details
            FROM printer_jobs
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*parameters, PAGE_SIZE, offset],
        ).fetchall()

    return {
        "items": [dict(row) for row in rows],
        "page": current_page,
        "page_size": PAGE_SIZE,
        "total": total,
        "total_pages": total_pages,
        "search": search_text,
    }


@app.get("/api/devices/5800x/status")
def get_5800x_status() -> dict[str, Any]:
    try:
        with urllib.request.urlopen(PC_5800X_AGENT_URL, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
        payload["agent_reachable"] = True
        return payload
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
        return {
            "computer_name": "DESKTOP-5S6BVJE",
            "pc_status": "Offline",
            "tailscale_status": "Offline",
            "tailscale_ip": None,
            "cpu_percent": 0,
            "temperature_c": None,
            "memory_percent": 0,
            "disk_percent": 0,
            "printer_count": 0,
            "printer_name": "Unavailable",
            "spooler": "Unknown",
            "printing": 0,
            "queued": 0,
            "error": 0,
            "updated_at": None,
            "agent_reachable": False,
            "error_message": str(error),
        }


@app.get("/api/devices/macmini/status")
def get_macmini_status() -> dict[str, Any]:
    try:
        with urllib.request.urlopen(MAC_MINI_AGENT_URL, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
        payload["agent_reachable"] = True
        return payload
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
        return {
            "computer_name": "MacMiniui-Macmini.local",
            "pc_status": "Offline",
            "tailscale_status": "Offline",
            "tailscale_ip": None,
            "cpu_percent": 0,
            "cpu_name": "Apple M1",
            "temperature_c": None,
            "memory_percent": 0,
            "disk_percent": 0,
            "printer_count": 0,
            "printer_name": "Unavailable",
            "spooler": "Unknown",
            "printing": 0,
            "queued": 0,
            "error": 0,
            "updated_at": None,
            "agent_reachable": False,
            "error_message": str(error),
        }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "database": str(DB_PATH.name)}
