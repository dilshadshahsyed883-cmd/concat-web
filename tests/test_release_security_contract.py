"""Offline regression gates: local-admin deploy preflight; no automated release."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PersonalManualReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
        cls.helper = (ROOT / "deploy/guarded-release.sh").read_text()
        cls.service = (ROOT / "deploy/concat-web.service").read_text()
        cls.example = (ROOT / ".env.example").read_text()

    def test_guarded_release_shell_parses(self):
        p = subprocess.run(
            ["bash", "-n", str(ROOT / "deploy/guarded-release.sh")],
            capture_output=True, text=True,
        )
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_no_github_automatic_deployment(self):
        workflow = self.workflow
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("ssh ", workflow)
        self.assertNotIn("scp ", workflow)
        self.assertNotIn("tailscale/", workflow)
        self.assertNotIn("deploy deploy", workflow)
        self.assertNotIn("vps1deploy@", workflow)
        self.assertIn("NO DEPLOY", workflow)

    def test_guarded_helper_is_private_concat_only(self):
        sh = self.helper
        for marker in (
            "CONCAT_AUTH_MODE", "CONCAT_LOCAL_ADMIN_USERNAME",
            "CONCAT_LOCAL_ADMIN_PASSWORD_HASH", "CONCAT_LOCAL_SESSION_SECRET",
            "LUM_SESSION_SECRET", "CONCAT_WEB_SECURITY_DB",
            "root-owned", "readlink -f -- \"$0\"",
            "stat -c %U", "sha256sum -c -",
            "runuser -u concatweb", "SWITCHED=1",
            "cleanup_and_rollback", "/healthz",
            "/api/v1/session", "/dashboard", '== 401',
            'if [[ "$MODE" == preflight ]]',
        ):
            self.assertIn(marker, sh)
        for unsafe in (
            "CONCAT_SCENE_SSO_SECRET", "CONCAT_SCENE_USERS_DB",
            "concat_sso_sessions", "systemctl restart scene-",
            "systemctl restart vps1", "systemctl reload nginx",
            "ssh-keyscan", "chmod -R 777",
        ):
            self.assertNotIn(unsafe, sh)
        self.assertNotIn("nginx -s reload", sh)

    def test_explicit_local_mode_and_private_env(self):
        example = self.example
        for marker in (
            "CONCAT_AUTH_MODE=local", "CONCAT_LOCAL_ADMIN_USERNAME=",
            "CONCAT_LOCAL_ADMIN_PASSWORD_HASH=", "CONCAT_LOCAL_SESSION_SECRET=",
            "CONCAT_WEB_SECURITY_DB=/var/lib/concat-web/security.sqlite3",
            "CONCAT_WEB_HOST=127.0.0.1",
        ):
            self.assertIn(marker, example)
        self.assertNotIn("CONCAT_SCENE_SSO_SECRET=", example)
        self.assertNotIn("CONCAT_SCENE_USERS_DB=", example)
        self.assertIn("EnvironmentFile=/etc/concat-web/concat-web.env", self.service)
        self.assertIn("User=concatweb", self.service)
        self.assertIn("ReadWritePaths=/var/lib/concat-web", self.service)

    def test_login_requires_password_hash_and_no_bypass(self):
        security = (ROOT / "app/modules/admin/local_security.py").read_text()
        routes = (ROOT / "app/modules/admin/routes.py").read_text()
        self.assertIn("hashlib.scrypt", security)
        self.assertIn("hmac.compare_digest", security)
        self.assertIn("MAX_FAILURES = 5", security)
        self.assertIn("local_sessions", security)
        self.assertIn("secure=True", routes)
        self.assertIn("httponly=True", routes)
        self.assertIn('"/auth/login"', routes)


if __name__ == "__main__":
    unittest.main()
