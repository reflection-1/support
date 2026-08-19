"""support: a small SQLite-backed ticket dashboard."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DATABASE_PATH = ROOT / "supportops.db"


SAMPLE_TICKETS = [
    ("Wi-Fi says no after a password reset", "Mina P.", "Access", "High", "Open", "2026-08-10 09:15", "2026-08-11 09:15", None, "Jordan Lee", "A student can sign in on their phone but their laptop will not reconnect after a password change."),
    ("Event sign-up sheet has duplicate rows", "Campus Events", "Data", "Medium", "In Progress", "2026-08-11 10:30", "2026-08-13 10:30", None, "Jordan Lee", "A CSV export is repeating attendee records, so the registration count is unreliable."),
    ("New volunteer needs email and Teams", "Sofia M.", "Access", "Low", "Resolved", "2026-08-12 08:40", "2026-08-12 16:40", "2026-08-12 11:10", "Taylor Brooks", "Created the requested accounts and confirmed the first sign-in with the coordinator."),
    ("Large order export keeps timing out", "Northwind Retail", "Application", "High", "In Progress", "2026-08-12 13:20", "2026-08-13 13:20", None, "Taylor Brooks", "An export with more than 1,000 rows fails after roughly 30 seconds."),
    ("Room 240 projector will not see HDMI", "Learning Spaces", "Hardware", "Medium", "Open", "2026-08-13 09:05", "2026-08-14 09:05", None, "Jordan Lee", "The projector works with one laptop but not another. A quick check before a workshop is needed."),
    ("Password reset instructions are confusing", "Sam W.", "Knowledge", "Low", "Resolved", "2026-08-13 14:10", "2026-08-14 14:10", "2026-08-13 15:20", "Taylor Brooks", "Rewrote the help article in plain language and added the step people were missing."),
    ("Checkout tablet cannot join Wi-Fi", "Pop-up Shop", "Network", "High", "Open", "2026-08-14 07:50", "2026-08-14 15:50", None, "Jordan Lee", "Two tablets cannot join the guest network before the shop opens."),
    ("Monthly report is double-counting sales", "Sales Operations", "Data", "Medium", "Resolved", "2026-08-14 11:35", "2026-08-15 11:35", "2026-08-14 16:45", "Taylor Brooks", "A duplicate join in the reporting query was corrected and the fix was documented."),
    ("Could we add a preferred-name field?", "Account Management", "Application", "Low", "Open", "2026-08-15 10:00", "2026-08-18 10:00", None, "Jordan Lee", "A small request to make an account form more welcoming and easier to use."),
    ("Laptop encryption status is missing", "IT Security", "Hardware", "High", "In Progress", "2026-08-15 15:25", "2026-08-16 15:25", None, "Taylor Brooks", "The endpoint console has not reported encryption status for one laptop."),
]


def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                requester TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL CHECK(priority IN ('High', 'Medium', 'Low')),
                status TEXT NOT NULL CHECK(status IN ('Open', 'In Progress', 'Resolved')),
                opened_at TEXT NOT NULL,
                due_at TEXT NOT NULL,
                resolved_at TEXT,
                assigned_to TEXT NOT NULL,
                description TEXT NOT NULL
            )
            """
        )
        ticket_count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        if ticket_count == 0:
            seed_demo_tickets(conn)


def seed_demo_tickets(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT INTO tickets (
            title, requester, category, priority, status, opened_at,
            due_at, resolved_at, assigned_to, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        SAMPLE_TICKETS,
    )


def reset_demo_tickets() -> None:
    """Reset the fictional sample tickets without touching the application code."""
    initialize_database()
    with connection() as conn:
        conn.execute("DELETE FROM tickets")
        seed_demo_tickets(conn)


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def get_tickets(params: dict[str, list[str]]) -> list[dict]:
    filters: list[str] = []
    values: list[str] = []

    status = params.get("status", [""])[0]
    priority = params.get("priority", [""])[0]
    query = params.get("query", [""])[0].strip()

    if status in {"Open", "In Progress", "Resolved"}:
        filters.append("status = ?")
        values.append(status)
    if priority in {"High", "Medium", "Low"}:
        filters.append("priority = ?")
        values.append(priority)
    if query:
        filters.append("(title LIKE ? OR requester LIKE ? OR category LIKE ? OR description LIKE ?)")
        values.extend([f"%{query}%"] * 4)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    sql = f"""
        SELECT id, title, requester, category, priority, status, opened_at,
               due_at, resolved_at, assigned_to, description
        FROM tickets
        {where_clause}
        ORDER BY
            CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
            datetime(opened_at) DESC
    """
    with connection() as conn:
        return rows_to_dicts(conn.execute(sql, values).fetchall())


def get_metrics() -> dict:
    today = date.today().isoformat()
    with connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        open_count = conn.execute("SELECT COUNT(*) FROM tickets WHERE status != 'Resolved'").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Resolved'").fetchone()[0]
        overdue = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE status != 'Resolved' AND date(due_at) < date(?)",
            (today,),
        ).fetchone()[0]
        average_hours = conn.execute(
            """
            SELECT ROUND(AVG((julianday(resolved_at) - julianday(opened_at)) * 24), 1)
            FROM tickets
            WHERE resolved_at IS NOT NULL
            """
        ).fetchone()[0]
        by_category = rows_to_dicts(
            conn.execute(
                "SELECT category, COUNT(*) AS count FROM tickets GROUP BY category ORDER BY count DESC, category"
            ).fetchall()
        )
        by_status = rows_to_dicts(
            conn.execute(
                "SELECT status, COUNT(*) AS count FROM tickets GROUP BY status ORDER BY count DESC"
            ).fetchall()
        )

    return {
        "total": total,
        "open": open_count,
        "resolved": resolved,
        "overdue": overdue,
        "average_resolution_hours": average_hours or 0,
        "by_category": by_category,
        "by_status": by_status,
    }


def create_ticket(payload: dict) -> dict:
    required_fields = ("title", "requester", "category", "priority", "description")
    cleaned = {field: str(payload.get(field, "")).strip() for field in required_fields}

    if any(not cleaned[field] for field in required_fields):
        raise ValueError("please complete every field")
    if cleaned["category"] not in {"Access", "Application", "Data", "Hardware", "Knowledge", "Network"}:
        raise ValueError("please choose a valid category")
    if cleaned["priority"] not in {"High", "Medium", "Low"}:
        raise ValueError("please choose a valid priority")
    if len(cleaned["title"]) > 100 or len(cleaned["requester"]) > 60 or len(cleaned["description"]) > 400:
        raise ValueError("one of those fields is a little too long")

    now = datetime.now().replace(microsecond=0)
    due_days = {"High": 1, "Medium": 2, "Low": 3}
    due_at = now + timedelta(days=due_days[cleaned["priority"]])

    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tickets (
                title, requester, category, priority, status, opened_at,
                due_at, resolved_at, assigned_to, description
            ) VALUES (?, ?, ?, ?, 'Open', ?, ?, NULL, 'Sara', ?)
            """,
            (
                cleaned["title"],
                cleaned["requester"],
                cleaned["category"],
                cleaned["priority"],
                now.isoformat(sep=" "),
                due_at.isoformat(sep=" "),
                cleaned["description"],
            ),
        )
        ticket_id = cursor.lastrowid
        ticket = conn.execute(
            """
            SELECT id, title, requester, category, priority, status, opened_at,
                   due_at, resolved_at, assigned_to, description
            FROM tickets WHERE id = ?
            """,
            (ticket_id,),
        ).fetchone()

    return dict(ticket)


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def send_json(self, data: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - required by the base class
        parsed = urlparse(self.path)
        if parsed.path == "/api/metrics":
            self.send_json(get_metrics())
            return
        if parsed.path == "/api/tickets":
            self.send_json({"tickets": get_tickets(parse_qs(parsed.query))})
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - required by the base class
        if urlparse(self.path).path != "/api/tickets":
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 10_000:
                raise ValueError("that ticket could not be read")
            payload = json.loads(self.rfile.read(content_length))
            if not isinstance(payload, dict):
                raise ValueError("that ticket could not be read")
            ticket = create_ticket(payload)
        except (json.JSONDecodeError, ValueError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json({"ticket": ticket}, HTTPStatus.CREATED)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the support demo dashboard.")
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        help="replace local tickets with the fictional sample data before starting",
    )
    parser.add_argument("--port", type=int, default=8000, help="local port to use (default: 8000)")
    args = parser.parse_args()

    if args.reset_demo:
        reset_demo_tickets()
    initialize_database()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"support is running at http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
