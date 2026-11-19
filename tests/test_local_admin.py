"""Personal Concat Web: independent local admin, sessions and owner isolation.

No Scene SQLite, VPS host, YouTube, Drive or GPU is accessed in these tests.
"""
from contextlib import ExitStack
import base64
import hashlib
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import Principal, require_owned_resource
from app.main import create_app
from app.modules.admin.security import COOKIE


def urlsafe(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class LocalAdminTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.database = self.folder / "local-security.sqlite3"
        self.origin = "https://concat.scenebuilder.online"
        self.username = "personaladmin"
        self.password = "strong-personal-passphrase-for-tests"
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(self.password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
        self.environment = {
            "CONCAT_AUTH_MODE": "local",
            "CONCAT_LOCAL_ADMIN_USERNAME": self.username,
            "CONCAT_LOCAL_ADMIN_PASSWORD_HASH": "scrypt$16384$8$1$" + urlsafe(salt) + "$" + urlsafe(digest),
            "CONCAT_LOCAL_SESSION_SECRET": "separate-32-byte-plus-private-session-secret",
            "CONCAT_WEB_SECURITY_DB": str(self.database),
            "CONCAT_WEB_PUBLIC_ORIGIN": self.origin,
            "CONCAT_UPLOADER_ENABLED": "0",
        }
        self.stack.enter_context(patch.dict(os.environ, self.environment))
        self.app = create_app()
        self.client = TestClient(self.app, base_url=self.origin, follow_redirects=False)
        self.addCleanup(self.client.close)

    def post_login(self, username=None, password=None, origin=None):
        return self.client.post(
            "/auth/login",
            data={"username": self.username if username is None else username,
                  "password": self.password if password is None else password},
            headers={"origin": self.origin if origin is None else origin},
        )

    def sign_in(self):
        reply = self.post_login()
        self.assertEqual(reply.status_code, 303, reply.text[:200])
        self.assertEqual(reply.headers["location"], "/dashboard")
        self.assertIn("Secure", reply.headers["set-cookie"])
        self.assertIn("HttpOnly", reply.headers["set-cookie"])
        self.assertTrue(self.client.cookies.get(COOKIE))
        return self.client.get("/api/v1/auth/csrf").json()["csrf_token"]

    def test_no_scene_dependency_and_protected_routes(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/auth/login").status_code, 200)
        self.assertEqual(self.client.get("/auth/scene/start").status_code, 404)
        self.assertEqual(self.client.get("/auth/scene/callback").status_code, 404)
        for url in ("/", "/dashboard", "/admin", "/concat/production",
                    "/concat-uploader/queue", "/api/v1/admin/users", "/api/v1/session"):
            with self.subTest(url=url):
                response = self.client.get(url, headers={
                    "X-Auth-User": self.username, "X-Is-Admin": "true",
                    "X-Forwarded-User": self.username, "X-App-Access": "all",
                })
                self.assertEqual(response.status_code, 401)

    def test_login_routes_auth_admin_and_logout(self):
        csrf = self.sign_in()
        self.assertEqual(self.client.get("/api/v1/session").json()["username"], self.username)
        self.assertEqual(self.client.get("/admin").status_code, 200)
        self.assertEqual(self.client.get("/concat/production").status_code, 200)
        users = self.client.get("/api/v1/admin/users").json()["users"]
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["username"], self.username)
        self.assertNotIn("password", str(users))
        self.assertEqual(self.client.post("/auth/logout", headers={
            "origin": self.origin, "X-CSRF-Token": csrf,
        }).status_code, 303)
        self.assertEqual(self.client.get("/dashboard").status_code, 401)

    def test_bad_password_wrong_username_cross_origin_and_no_headers(self):
        self.assertEqual(self.post_login(password="wrong-password").status_code, 401)
        self.assertEqual(self.post_login(username="root").status_code, 401)
        self.assertEqual(self.post_login(origin="https://evil.example").status_code, 403)
        self.assertEqual(self.client.post("/auth/login", data={
            "username": self.username, "password": self.password,
        }).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/session").status_code, 401)
        self.sign_in()

    def test_durable_login_lockout(self):
        for _ in range(5):
            self.assertEqual(self.post_login(password="not-it").status_code, 401)
        self.assertEqual(self.post_login().status_code, 429)
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE local_login_attempts SET locked_until=0,failures=0")
        self.sign_in()

    def test_session_csrf_revoke_and_expiry(self):
        csrf = self.sign_in()
        url = "/api/v1/admin/config"
        self.assertEqual(self.client.post(url, json={"session_max_minutes": 30},
                                           headers={"origin": self.origin}).status_code, 403)
        self.assertEqual(self.client.post(url, json={"session_max_minutes": 30},
                                           headers={"origin": "https://evil.example",
                                                    "X-CSRF-Token": csrf}).status_code, 403)
        self.assertEqual(self.client.post(url, json={"session_max_minutes": 30},
                                           headers={"origin": self.origin,
                                                    "X-CSRF-Token": csrf}).status_code, 200)
        self.assertEqual(self.client.post(
            "/api/v1/admin/users/personaladmin/access", json={"concat_granted": False},
            headers={"origin": self.origin, "X-CSRF-Token": csrf},
        ).status_code, 409)
        self.assertEqual(self.client.post(
            "/api/v1/admin/users/personaladmin/revoke-sessions",
            headers={"origin": self.origin, "X-CSRF-Token": csrf},
        ).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/session").status_code, 401)
        self.sign_in()
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE local_sessions SET expires_at=?", (int(time.time())-1,))
        self.assertEqual(self.client.get("/dashboard").status_code, 401)

    def test_foreign_owner_and_legacy_records_denied_to_admin(self):
        self.sign_in()
        administrator = Principal(self.username, is_active=True, is_admin=True, concat_granted=True)
        records = [
            {"owner_username": self.username, "app": "concat", "id": 1},
            {"owner_username": "other", "app": "concat", "id": 2},
            {"owner_username": "__default__", "app": "concat", "id": 3},
            {"owner_username": self.username, "app": "concat-uploader", "id": 4},
            {"app": "concat", "id": 5},
        ]
        self.assertEqual(require_owned_resource(administrator, records[0], "concat")["id"], 1)
        for record in records[1:]:
            with self.subTest(record=record["id"]):
                with self.assertRaises(HTTPException) as caught:
                    require_owned_resource(administrator, record, "concat")
                self.assertEqual(caught.exception.status_code, 404)

    def test_missing_or_invalid_configuration_fails_closed(self):
        self.client.cookies.clear()
        for changes in (
            {"CONCAT_AUTH_MODE": "something-else"},
            {"CONCAT_LOCAL_SESSION_SECRET": ""},
            {"CONCAT_LOCAL_ADMIN_PASSWORD_HASH": "plaintext"},
            {"CONCAT_LOCAL_ADMIN_USERNAME": "__default__"},
        ):
            with self.subTest(changes=list(changes)):
                with patch.dict(os.environ, changes):
                    isolated_app = create_app()
                    with TestClient(isolated_app, base_url=self.origin) as isolated:
                        self.assertEqual(isolated.get("/api/v1/session").status_code, 401)
                        self.assertNotEqual(isolated.post("/auth/login",
                            data={"username": self.username, "password": self.password},
                            headers={"origin": self.origin}).status_code, 303)


if __name__ == "__main__":
    unittest.main()
