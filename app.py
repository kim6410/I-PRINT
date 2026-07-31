from __future__ import annotations

import json
import math
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "printer_jobs.db"
INDEX_PATH = BASE_DIR / "index.html"
MOBILE_PATH = BASE_DIR / "mobile.html"
ASSETS_PATH = BASE_DIR / "assets"
PAGE_SIZE = 10
PC_5800X_AGENT_URL = "http://100.117.206.9:8898/status"
MAC_MINI_AGENT_URL = "http://100.116.128.62:8898/status"

app = FastAPI(title="i-Print Dashboard")
app.mount("/assets", StaticFiles(directory=ASSETS_PATH), name="assets")


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
        connection.commit()


@app.on_event("startup")
def startup_event() -> None:
    initialize_database()


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


@app.get("/mobile")
def mobile_dashboard() -> FileResponse:
    return FileResponse(MOBILE_PATH)


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
