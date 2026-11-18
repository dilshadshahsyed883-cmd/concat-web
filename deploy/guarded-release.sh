#!/usr/bin/env bash
# Host-side, isolated Concat Web release. Never edits Nginx, Scene, OAuth or Drive Bridge.
set -Eeuo pipefail
umask 077
[[ "$#" -eq 2 ]] || { echo "usage: guarded-release.sh <commit-sha> <archive>" >&2; exit 2; }
sha="$1"
archive="$2"
[[ "$sha" =~ ^[a-f0-9]{40}$ ]] || { echo "invalid SHA" >&2; exit 2; }
[[ "$EUID" -eq 0 ]] || { echo "root/sudo required" >&2; exit 2; }
[[ "$archive" == "/tmp/concat-web-$sha-"*".tgz" && -f "$archive" && ! -L "$archive" ]] || exit 2
exec 9>/run/lock/concat-web-release.lock
flock -n 9 || { echo "another Concat deployment is running" >&2; exit 1; }

root=/srv/concat-web
envfile=/etc/concat-web/concat-web.env
service=concat-web.service
release="$root/releases/$sha"
[[ -f "$envfile" && ! -L "$envfile" && "$(stat -c %U "$envfile")" == root ]] || { echo "private root-owned Concat env missing" >&2; exit 1; }
[[ -z "$(find "$envfile" -maxdepth 0 -perm /007 -print -quit)" ]] || { echo "Concat env accessible to others" >&2; exit 1; }
id concatweb >/dev/null
systemctl cat "$service" >/dev/null
[[ "$(systemctl show -P User "$service")" == "concatweb" ]] || { echo "wrong service account" >&2; exit 1; }
[[ -d /var/lib/concat-web && "$(stat -c %U /var/lib/concat-web)" == concatweb ]] || { echo "persistent owner storage missing" >&2; exit 1; }
[[ -d "$root/releases" && ! -L "$root" ]] || { echo "isolated release root missing" >&2; exit 1; }
[[ ! -e "$root/current" || -L "$root/current" ]] || { echo "current must be a symlink" >&2; exit 1; }

# Only a trusted, root-owned, private environment file is sourced. Never log values.
set -a
# shellcheck disable=SC1090
source "$envfile"
set +a
[[ "${CONCAT_WEB_HOST:-}" == "127.0.0.1" && "${CONCAT_WEB_PORT:-}" == "18873" ]] || exit 1
[[ "${CONCAT_WEB_PUBLIC_ORIGIN:-}" == "https://concat.scenebuilder.online" ]] || exit 1
[[ "${CONCAT_SCENE_PUBLIC_ORIGIN:-}" == "https://app.scenebuilder.online" ]] || exit 1
[[ "${CONCAT_WEB_DATA_ROOT:-}" == "/var/lib/concat-web" ]] || exit 1
[[ "${CONCAT_CLOUD_RENDER_ROOT:-}" == "/var/lib/concat-web" ]] || exit 1
[[ "${CONCAT_WEB_SECURITY_DB:-}" == "/var/lib/concat-web/security.sqlite3" ]] || exit 1
[[ "${LUM_DATA_DIR:-}" == "/var/lib/concat-web/uploader" ]] || exit 1
[[ "${CONCAT_UPLOADER_ENABLED:-}" == "1" ]] || exit 1
[[ "${#CONCAT_SCENE_SSO_SECRET}" -ge 32 && "${#LUM_SESSION_SECRET}" -ge 32 ]] || { echo "independent secrets missing" >&2; exit 1; }
[[ -f "${CONCAT_SCENE_USERS_DB:-}" && "${CONCAT_SCENE_USERS_DB}" != "${CONCAT_WEB_SECURITY_DB}" ]] || exit 1

# Test actual Concat identity's read-only SQLite access, including WAL-visible schema.
runuser -u concatweb -- python3 - "$CONCAT_SCENE_USERS_DB" <<'PY'
import os, sqlite3, sys
from pathlib import Path
from urllib.parse import quote
p = Path(sys.argv[1]).resolve()
if not p.is_file() or os.access(p, os.W_OK):
    raise SystemExit("Scene database must exist and be read-only for concatweb")
uri = "file:" + quote(str(p), safe="/") + "?mode=ro"
with sqlite3.connect(uri, uri=True, timeout=5) as db:
    db.execute("PRAGMA query_only=ON")
    db.execute("SELECT username,is_active,is_admin,created_at FROM users LIMIT 1").fetchall()
    db.execute("SELECT sid_hash,username_key,expires_at,revoked_at FROM concat_sso_sessions LIMIT 1").fetchall()
print("Scene account + revocable session read-only check passed")
PY

# This script never touches public ingress. The dedicated unit must already be configured.
nginx -t >/dev/null
old=""
if [[ -L "$root/current" ]]; then
  old="$(readlink -f "$root/current")"
  [[ "$old" == "$root/releases/"* ]] || exit 1
fi
switched=0
rollback() {
  result=$?
  trap - EXIT
  if (( result != 0 && switched == 1 )); then
    echo "Concat-only release failed; restoring previous unit" >&2
    if [[ -n "$old" ]]; then
      ln -s "$old" "$root/.rollback-$sha"
      mv -Tf "$root/.rollback-$sha" "$root/current"
      systemctl restart "$service" || true
    else
      systemctl stop "$service" || true
      rm -f "$root/current"
    fi
  fi
  rm -f "$archive"
  exit "$result"
}
trap rollback EXIT

if [[ -e "$release" ]]; then
  echo "Release SHA already staged; refusing overwrite" >&2
  exit 1
fi
mkdir -m 0755 "$release"
tar -xzf "$archive" -C "$release" --no-same-owner --no-same-permissions
[[ -f "$release/run.py" && -d "$release/wheelhouse" ]] || exit 1
python3 -m venv "$release/.venv"
"$release/.venv/bin/pip" --disable-pip-version-check install --no-index --find-links="$release/wheelhouse" "concat-web==0.1.0"
chown -R root:root "$release"
chmod -R go-w "$release"
ln -s "$release" "$root/.candidate-$sha"
mv -Tf "$root/.candidate-$sha" "$root/current"
switched=1
systemctl restart "$service"
healthy=0
for _ in $(seq 1 25); do
  if curl -fsS --max-time 2 http://127.0.0.1:18873/healthz | python3 -c 'import json,sys; x=json.load(sys.stdin); assert x["ok"] is True and x["service"]=="concat-web"' 2>/dev/null; then
    healthy=1
    break
  fi
  sleep 1
done
[[ "$healthy" == 1 ]] || { echo "Concat loopback health failed" >&2; exit 1; }
# Anonymous requests must remain denied. A 200 here would be a release blocker.
status="$(curl -sS --max-time 4 -o /dev/null -w '%{http_code}' http://127.0.0.1:18873/api/v1/session)"
[[ "$status" == 401 ]] || { echo "anonymous session was not denied" >&2; exit 1; }
status="$(curl -sS --max-time 4 -o /dev/null -w '%{http_code}' http://127.0.0.1:18873/dashboard)"
[[ "$status" == 401 ]] || { echo "anonymous dashboard was not denied" >&2; exit 1; }
echo "PASS: Concat Web SHA $sha staged on loopback; public Nginx routes unchanged"
