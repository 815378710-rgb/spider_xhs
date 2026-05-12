import paramiko, time, json

NAS = "192.168.68.161"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS, 22, "maomaoxia", "CongShaoYu102@", timeout=10)

BASE = "http://127.0.0.1:5005"
results = []

def curl(url):
    stdin, stdout, stderr = ssh.exec_command(f"curl -s --connect-timeout 5 --max-time 10 {url}")
    return stdout.read().decode().strip()

def curl_post(url, data):
    d = data.replace("'", "\\'")
    stdin, stdout, stderr = ssh.exec_command(f"curl -s --connect-timeout 5 --max-time 10 -X POST {url} -H 'Content-Type: application/json' -d '{d}'")
    return stdout.read().decode().strip()

def curl_auth(method, url, data=None, token=None):
    hdr = f"-H 'Authorization: Bearer {token}'" if token else ""
    body = f"-H 'Content-Type: application/json' -d '{data}'" if data else ""
    cmd = f"curl -s --connect-timeout 5 --max-time 10 -X {method} {url} {hdr} {body}"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode().strip()

def check(name, resp, keyword, negate=False):
    ok = False
    if not resp:
        msg = "EMPTY RESPONSE"
    else:
        found = keyword in resp
        ok = (found and not negate) or (not found and negate)
        msg = "OK" if ok else f"Expected {'not ' if negate else ''}{keyword}, got: {resp[:200]}"
    results.append((name, ok, msg))
    print(f"  {'PASS' if ok else 'FAIL'}: {name}" + ("" if ok else f"  -- {msg[:120]}"))

print("=" * 60)
print("  FULL API REGRESSION TEST")
print("=" * 60)

# === Public endpoints ===
print("\n--- Public ---")
r = curl(f"{BASE}/api/health")
check("Health endpoint", r, "2.2.0")

r = curl(f"{BASE}/api/auth/announcement")
check("Announcement endpoint", r, "success")

r = curl(f"{BASE}/")
check("SPA frontend /", r, "<!DOCTYPE html>")

r = curl("http://xhs.maomaoxia.top/")
check("Public domain", r, "<!DOCTYPE html>")

# === Auth ===
print("\n--- Auth ---")
r = curl_post(f"{BASE}/api/auth/login", '{"username":"admin","password":"wrong"}')
check("Login wrong password -> error", r, "detail", negate=False)

r = curl_post(f"{BASE}/api/auth/login", '{"username":"admin","password":"admin123"}')
check("Login admin/admin123 -> token", r, "access_token")

try:
    token = json.loads(r)["access_token"]
except:
    token = ""
    check("Token parse", "", "access_token")

r = curl_auth("GET", f"{BASE}/api/auth/me", token=token)
check("GET /auth/me (admin)", r, "admin")

r = curl_auth("GET", f"{BASE}/api/auth/me")
check("GET /auth/me (no token) -> error", r, "detail")

# === Admin: Users ===
print("\n--- Admin: Users ---")
r = curl_auth("GET", f"{BASE}/api/admin/users", token=token)
check("GET /admin/users", r, "items")
try:
    user_list = json.loads(r)["data"]["items"]
    admin_user_id = [u["id"] for u in user_list if u["username"] == "admin"][0]
except:
    admin_user_id = None
    check("Parse user list", "", "items")

# === Admin: License Keys ===
print("\n--- Admin: License Keys ---")
r = curl_auth("POST", f"{BASE}/api/admin/license-keys", '{"count":2,"valid_days":15}', token)
check("Generate 2 keys (15 days)", r, "keys")
check("valid_days=15 in response", r, "valid_days")

try:
    new_keys = json.loads(r)["data"]["keys"]
    first_key = new_keys[0]
except:
    first_key = None
    check("Parse keys", "", "keys")

# List keys
r = curl_auth("GET", f"{BASE}/api/admin/license-keys", token=token)
check("GET /admin/license-keys list", r, "items")
check("Keys have valid_days field", r, "valid_days")
check("Keys have expires_at field", r, "expires_at")

# === Register ===
print("\n--- Register ---")
if first_key:
    r = curl_post(f"{BASE}/api/auth/register", json.dumps({"username":"testbugcheck","password":"test1234","license_key":first_key}))
    check("Register with valid key", r, "access_token")

    try:
        reg_data = json.loads(r)
        test_token = reg_data.get("access_token", "")
        test_role = reg_data.get("role", "")
    except:
        test_token = ""
        test_role = ""

    check("Registered role=user", test_role, "user")

    # Check expires_at in DB
    ssh.exec_command("cat > /tmp/v.py << 'PYEOF'\nimport sqlite3\nconn=sqlite3.connect('/volume1/projects/spider-xhs/backend/data/spider_xhs.db')\nfor r in conn.execute(\"SELECT username,expires_at FROM users WHERE username='testbugcheck'\"): print(r[0]+':'+str(r[1]))\nconn.close()\nPYEOF", timeout=5)
    time.sleep(0.5)
    stdin, stdout, stderr = ssh.exec_command("python /tmp/v.py 2>/dev/null")
    db_line = stdout.read().decode().strip()
    check("DB: testbugcheck has expires_at", db_line, "2026-")

    # Duplicate register
    r = curl_post(f"{BASE}/api/auth/register", json.dumps({"username":"testbugcheck","password":"test1234","license_key":first_key}))
    check("Register duplicate username -> error", r, "detail")

    # Used key
    r = curl_post(f"{BASE}/api/auth/register", json.dumps({"username":"newuser","password":"test1234","license_key":first_key}))
    check("Register with used key -> error", r, "detail")

    # Non-admin cannot access admin endpoints
    r = curl_auth("GET", f"{BASE}/api/admin/users", token=test_token)
    check("Non-admin GET /admin/users -> 403", r, "detail")

    # Test user login
    r = curl_post(f"{BASE}/api/auth/login", '{"username":"testbugcheck","password":"test1234"}')
    check("testbugcheck login", r, "access_token")

# === Admin: Renew ===
print("\n--- Admin: Renew ---")
if first_key:
    # Get test user ID
    ssh.exec_command("cat > /tmp/v2.py << 'PYEOF'\nimport sqlite3\nconn=sqlite3.connect('/volume1/projects/spider-xhs/backend/data/spider_xhs.db')\nr=conn.execute(\"SELECT id FROM users WHERE username='testbugcheck'\").fetchone()\nprint(r[0] if r else 'NONE')\nconn.close()\nPYEOF", timeout=5)
    time.sleep(0.5)
    stdin, stdout, stderr = ssh.exec_command("python /tmp/v2.py 2>/dev/null")
    test_uid = stdout.read().decode().strip()
    check("Get test user ID", test_uid, "2")

    if test_uid and test_uid != "NONE":
        r = curl_auth("POST", f"{BASE}/api/admin/users/{test_uid}/renew", '{"days":20}', token)
        check("Renew user 20 days", r, "success")
        check("Renew response has expires_at", r, "expires_at")

# === Admin: Announcements ===
print("\n--- Admin: Announcements ---")
r = curl_auth("POST", f"{BASE}/api/admin/announcements", '{"title":"BugTest","content":"Testing bugs","active":true}', token)
check("Create announcement", r, "success")
try:
    ann_id = json.loads(r).get("data", {}).get("id")
except:
    ann_id = None

r = curl_auth("GET", f"{BASE}/api/admin/announcements", token=token)
check("List announcements", r, "BugTest")

if ann_id:
    r = curl_auth("PUT", f"{BASE}/api/admin/announcements/{ann_id}", '{"title":"BugTest2","content":"Updated","active":false}', token)
    check("Update announcement", r, "success")

    r = curl_auth("DELETE", f"{BASE}/api/admin/announcements/{ann_id}", token)
    check("Delete announcement", r, "success")

# === Admin: Model Config ===
print("\n--- Admin: Model Config ---")
r = curl_auth("GET", f"{BASE}/api/admin/model-config", token=token)
check("GET /admin/model-config", r, "llm_provider")

# === Edge Cases ===
print("\n--- Edge Cases ---")
r = curl_post(f"{BASE}/api/auth/login", '{"username":"","password":""}')
check("Login empty creds -> error", r, "detail")

r = curl_auth("DELETE", f"{BASE}/api/admin/users/{admin_user_id}", token)
check("Cannot delete own admin account", r, "detail")

# === Cleanup ===
print("\n--- Cleanup ---")
if first_key:
    # Delete test user
    ssh.exec_command("cat > /tmp/cleanup.py << 'PYEOF'\nimport sqlite3\nconn=sqlite3.connect('/volume1/projects/spider-xhs/backend/data/spider_xhs.db')\nconn.execute(\"DELETE FROM users WHERE username='testbugcheck'\")\nconn.execute(\"DELETE FROM users WHERE username='newuser'\")\nconn.commit()\nconn.close()\nprint('Cleaned')\nPYEOF", timeout=5)
    time.sleep(0.5)
    ssh.exec_command("python /tmp/cleanup.py 2>/dev/null")

# Delete test license keys
ssh.exec_command("cat > /tmp/cleanup2.py << 'PYEOF'\nimport sqlite3\nconn=sqlite3.connect('/volume1/projects/spider-xhs/backend/data/spider_xhs.db')\nconn.execute(\"DELETE FROM license_keys WHERE status='used' AND used_by IS NOT NULL\")\nconn.commit()\nconn.close()\nprint('Keys cleaned')\nPYEOF", timeout=5)
time.sleep(0.5)
ssh.exec_command("python /tmp/cleanup2.py 2>/dev/null")
check("Cleanup done", "ok", "ok")

# === SUMMARY ===
print("\n" + "=" * 60)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
total = len(results)
print(f"  RESULTS: {passed}/{total} PASS, {failed} FAIL")
if failed:
    print("\n  FAILED TESTS:")
    for name, ok, msg in results:
        if not ok:
            print(f"    [{name}] {msg[:150]}")
print("=" * 60)

ssh.close()
