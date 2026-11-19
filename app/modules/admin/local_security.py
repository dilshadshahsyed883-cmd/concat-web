"""Independent personal-admin authentication for Concat Web.

Never trusts inbound identity headers or a Scene cookie. Credentials are
provisioned out of band in the root-owned systemd environment file.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from app.modules.admin.security import COOKIE, SecurityUnavailable, _valid_username

PASSWORD_FORMAT = re.compile(r"^scrypt\$16384\$8\$1\$([A-Za-z0-9_-]{22,86})\$([A-Za-z0-9_-]{43})$")
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{40,200}$")
WINDOW_SECONDS = 15 * 60
MAX_FAILURES = 5


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class LocalAdminSecurity:
    """One configured admin, private SQLite sessions and bounded login attempts."""

    is_local = True

    def __init__(self, username: str, password_hash: str, session_secret: str,
                 database: Path, origin: str):
        if not _valid_username(username) or username.casefold() == "__default__":
            raise SecurityUnavailable("Invalid local administrator username")
        match = PASSWORD_FORMAT.fullmatch(password_hash)
        if not match:
            raise SecurityUnavailable("Invalid local admin password hash format")
        try:
            salt, expected = _decode(match[1]), _decode(match[2])
        except (ValueError, base64.binascii.Error) as exc:
            raise SecurityUnavailable("Invalid local admin password hash") from exc
        if not 16 <= len(salt) <= 64 or len(expected) != 32:
            raise SecurityUnavailable("Invalid local admin password hash")
        if len(session_secret.encode("utf-8")) < 32:
            raise SecurityUnavailable("Missing strong independent session secret")
        parsed = urlsplit(origin)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
            raise SecurityUnavailable("Local admin requires HTTPS origin")
        self.username = username
        self.salt = salt
        self.expected = expected
        self.secret = session_secret.encode("utf-8")
        self.web_origin = origin.rstrip("/")
        self.security_database = database
        if database.is_symlink() or not database.parent.is_dir() or database.parent.is_symlink():
            raise SecurityUnavailable("Local auth storage must be a private directory")
        if not database.exists():
            try:
                fd = os.open(str(database), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                os.close(fd)
            except OSError as exc:
                raise SecurityUnavailable("Local auth storage unavailable") from exc
        info = database.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
            raise SecurityUnavailable("Local session database is not private")
        self._initialize()

    @classmethod
    def from_environment(cls, app) -> "LocalAdminSecurity":
        db_path = os.environ.get("CONCAT_WEB_SECURITY_DB", "").strip()
        if not db_path or not Path(db_path).is_absolute():
            raise SecurityUnavailable("Local admin database path missing")
        return cls(
            os.environ.get("CONCAT_LOCAL_ADMIN_USERNAME", "").strip(),
            os.environ.get("CONCAT_LOCAL_ADMIN_PASSWORD_HASH", ""),
            os.environ.get("CONCAT_LOCAL_SESSION_SECRET", ""),
            Path(db_path),
            app.state.settings.origin,
        )

    def _local(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.security_database), timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def _initialize(self) -> None:
        with self._local() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS local_sessions(
                    token_hash TEXT PRIMARY KEY, username_key TEXT NOT NULL,
                    csrf_hash TEXT NOT NULL, created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL, revoked_at INTEGER
                );
                CREATE INDEX IF NOT EXISTS local_sessions_owner
                    ON local_sessions(username_key, revoked_at);
                CREATE TABLE IF NOT EXISTS local_login_attempts(
                    client_hash TEXT PRIMARY KEY, failures INTEGER NOT NULL,
                    first_failure INTEGER NOT NULL, locked_until INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS config(
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, actor_key TEXT NOT NULL,
                    action TEXT NOT NULL, target_key TEXT NOT NULL, created_at INTEGER NOT NULL
                );
            """)

    def _client_key(self, request: Request) -> str:
        # Never trust X-Forwarded-For or any user-controlled identity header.
        address = request.client.host if request.client is not None else "unknown"
        return hmac.new(self.secret, ("client:" + address[:128]).encode(), hashlib.sha256).hexdigest()

    def _blocked(self, db: sqlite3.Connection, key: str, now: int) -> bool:
        row = db.execute(
            "SELECT failures, first_failure, locked_until FROM local_login_attempts WHERE client_hash=?",
            (key,),
        ).fetchone()
        return bool(row and row["locked_until"] > now)

    def _fail_login(self, db: sqlite3.Connection, key: str, now: int) -> None:
        row = db.execute(
            "SELECT failures,first_failure FROM local_login_attempts WHERE client_hash=?", (key,),
        ).fetchone()
        if row and now - row["first_failure"] < WINDOW_SECONDS:
            failures, first = row["failures"] + 1, row["first_failure"]
        else:
            failures, first = 1, now
        until = now + WINDOW_SECONDS if failures >= MAX_FAILURES else 0
        db.execute(
            """INSERT INTO local_login_attempts(client_hash,failures,first_failure,locked_until)
               VALUES(?,?,?,?) ON CONFLICT(client_hash) DO UPDATE SET
               failures=excluded.failures,first_failure=excluded.first_failure,
               locked_until=excluded.locked_until""",
            (key, failures, first, until),
        )

    def login(self, username: str, password: str, request: Request) -> tuple[str, int]:
        if not isinstance(username, str) or not isinstance(password, str):
            raise HTTPException(401, "Invalid username or password")
        # Reject oversized inputs before expensive password derivation.
        if len(username) > 128 or len(password.encode("utf-8")) > 1024:
            raise HTTPException(401, "Invalid username or password")
        now = int(time.time())
        key = self._client_key(request)
        with self._local() as db:
            if self._blocked(db, key, now):
                raise HTTPException(429, "Too many login attempts; try again later")
        digest = hashlib.scrypt(password.encode("utf-8"), salt=self.salt, n=16384, r=8, p=1, dklen=32)
        valid_user = hmac.compare_digest(
            _sha(username.casefold()), _sha(self.username.casefold())
        )
        valid = valid_user and hmac.compare_digest(digest, self.expected)
        with self._local() as db:
            # Serialize credential attempts as a unit; parallel requests cannot
            # sidestep the durable lockout decision.
            db.execute("BEGIN IMMEDIATE")
            if self._blocked(db, key, now):
                raise HTTPException(429, "Too many login attempts; try again later")
            if not valid:
                self._fail_login(db, key, now)
                db.commit()
                raise HTTPException(401, "Invalid username or password")
            db.execute("DELETE FROM local_login_attempts WHERE client_hash=?", (key,))
            config = self._config(db)
            max_age = config["session_max_minutes"] * 60
            token = secrets.token_urlsafe(48)
            csrf = self._csrf_for_token(token)
            db.execute(
                """INSERT INTO local_sessions
                   (token_hash,username_key,csrf_hash,created_at,expires_at)
                   VALUES(?,?,?,?,?)""",
                (_sha(token), self.username.casefold(), _sha(csrf), now, now + max_age),
            )
            db.execute(
                "INSERT INTO audit(actor_key,action,target_key,created_at) VALUES(?,?,?,?)",
                (self.username.casefold(), "login", self.username.casefold(), now),
            )
        return token, max_age

    def _raw_session(self, request: Request):
        token = request.cookies.get(COOKIE, "")
        if not SESSION_PATTERN.fullmatch(token):
            return None
        with self._local() as db:
            return db.execute(
                """SELECT * FROM local_sessions WHERE token_hash=? AND
                   revoked_at IS NULL AND expires_at>? AND username_key=?""",
                (_sha(token), int(time.time()), self.username.casefold()),
            ).fetchone()

    def authenticate(self, request: Request):
        if self._raw_session(request) is None:
            return None
        from app.auth import Principal
        return Principal(self.username, is_admin=True, is_active=True, concat_granted=True)

    def _csrf_for_token(self, token: str) -> str:
        return hmac.new(self.secret, ("csrf." + token).encode("utf-8"), hashlib.sha256).hexdigest()

    def csrf_token(self, request: Request) -> str | None:
        if self._raw_session(request) is None:
            return None
        return self._csrf_for_token(request.cookies.get(COOKIE, ""))

    def verify_csrf(self, request: Request) -> None:
        row = self._raw_session(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not row or not supplied or not hmac.compare_digest(_sha(supplied), row["csrf_hash"]):
            raise HTTPException(403, "CSRF validation failed")
        origin, referer = request.headers.get("origin"), request.headers.get("referer")
        if origin:
            if origin.rstrip("/") != self.web_origin:
                raise HTTPException(403, "Origin validation failed")
        elif referer:
            parsed = urlsplit(referer)
            if parsed.scheme + "://" + parsed.netloc != self.web_origin:
                raise HTTPException(403, "Origin validation failed")
        else:
            raise HTTPException(403, "Origin validation failed")

    def revoke_cookie(self, request: Request) -> None:
        token = request.cookies.get(COOKIE, "")
        if SESSION_PATTERN.fullmatch(token):
            with self._local() as db:
                db.execute(
                    "UPDATE local_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                    (int(time.time()), _sha(token)),
                )

    @staticmethod
    def _config(db: sqlite3.Connection) -> dict:
        import json
        result = {"maintenance_mode": False, "session_max_minutes": 480}
        for row in db.execute("SELECT key,value FROM config"):
            if row["key"] in result:
                try:
                    result[row["key"]] = json.loads(row["value"])
                except ValueError as exc:
                    raise SecurityUnavailable("Invalid local config") from exc
        if (type(result["maintenance_mode"]) is not bool or
                type(result["session_max_minutes"]) is not int or
                not 15 <= result["session_max_minutes"] <= 480):
            raise SecurityUnavailable("Invalid local config")
        return result

    def config(self) -> dict:
        with self._local() as db:
            return self._config(db)

    def users(self) -> list[dict]:
        return [{
            "username": self.username, "is_active": True, "is_admin": True,
            "created_at": None, "concat_granted": True,
        }]

    def grant(self, actor: str, username: str, granted: bool) -> None:
        raise HTTPException(409, "User access grants are disabled in personal mode")

    def revoke_user(self, actor: str, username: str) -> int:
        if username.casefold() != self.username.casefold():
            raise HTTPException(404, "User not found")
        with self._local() as db:
            cursor = db.execute(
                "UPDATE local_sessions SET revoked_at=? WHERE username_key=? AND revoked_at IS NULL",
                (int(time.time()), self.username.casefold()),
            )
            count = cursor.rowcount
        self._audit(actor, "revoke_sessions", username)
        return count

    def _audit(self, actor: str, action: str, target: str) -> None:
        with self._local() as db:
            db.execute(
                "INSERT INTO audit(actor_key,action,target_key,created_at) VALUES(?,?,?,?)",
                (actor.casefold(), action, target.casefold(), int(time.time())),
            )

    def update_config(self, actor: str, config: dict) -> dict:
        import json
        if not isinstance(config, dict) or not config or set(config) - {"maintenance_mode", "session_max_minutes"}:
            raise HTTPException(422, "Unsupported configuration key")
        if "maintenance_mode" in config and type(config["maintenance_mode"]) is not bool:
            raise HTTPException(422, "maintenance_mode must be boolean")
        if "session_max_minutes" in config and (
                type(config["session_max_minutes"]) is not int or
                not 15 <= config["session_max_minutes"] <= 480):
            raise HTTPException(422, "session_max_minutes must be 15 to 480")
        with self._local() as db:
            for key, value in config.items():
                db.execute(
                    """INSERT INTO config(key,value) VALUES (?,?)
                       ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                    (key, json.dumps(value)),
                )
        self._audit(actor, "system_config", ",".join(sorted(config)))
        return self.config()

    def audit(self) -> list[dict]:
        with self._local() as db:
            rows = db.execute(
                "SELECT actor_key,action,target_key,created_at FROM audit ORDER BY id DESC LIMIT 100"
            ).fetchall()
        return [dict(row) for row in rows]
