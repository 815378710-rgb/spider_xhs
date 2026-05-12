import paramiko, time, json

NAS = "192.168.68.161"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS, 22, "maomaoxia", "CongShaoYu102@", timeout=10)

def curl(url):
    stdin, stdout, stderr = ssh.exec_command(f"curl -s --connect-timeout 5 --max-time 10 {url}")
    return stdout.read().decode().strip()

def curl_post(url, data, extra_headers=""):
    cmd = f"""curl -s --connect-timeout 5 --max-time 10 -X POST {url} -H 'Content-Type: application/json' {extra_headers} -d '{data}'"""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode().strip()

def curl_get_auth(url, token):
    cmd = f"""curl -s --connect-timeout 5 --max-time 10 {url} -H 'Authorization: Bearer {token}'"""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode().strip()

def curl_post_auth(url, data, token):
    cmd = f"""curl -s --connect-timeout 5 --max-time 10 -X POST {url} -H 'Content-Type: application/json' -H 'Authorization: Bearer {token}' -d '{data}'"""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode().strip()

def curl_put_auth(url, data, token):
    cmd = f"""curl -s --connect-timeout 5 --max-time 10 -X PUT {url} -H 'Content-Type: application/json' -H 'Authorization: Bearer {token}' -d '{data}'"""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode().strip()

def curl_del_auth(url, token):
    cmd = f"""curl -s --connect-timeout 5 --max-time 10 -X DELETE {url} -H 'Authorization: Bearer {token}'"""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode().strip()

results = []

def test(name, result, expect_key=None, expect_val=None):
    ok = True
    msg = ""
    if not result:
        ok = False
        msg = "EMPTY RESPONSE"
    elif expect_key:
        try:
            data = json.loads(result)
            if expect_key not in str(data):
                ok = False
                msg = f"Missing {expect_key}: {result[:200]}"
        except:
            if expect_key not in result:
                ok = False
                msg = f"Missing {expect_key}: {result[:200]}"
    status = "PASS" if ok else "FAIL"
    results.append((name, status, msg or result[:150]))
    print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    if not ok:
        print(f"        {msg[:200]}")

print("========== FULL API TEST ==========\n")

# 1. Health
print("--- 1. Health ---")
r = curl("http://127.0.0.1:5005/api/health")
test("GET /api/health", r, "status", "ok")

# 2. Announcement
print("\n--- 2. Announcement ---")
r = curl("http://127.0.0.1:5005/api/auth/announcement")
test("GET /api/auth/announcement", r, "success")

# 3. Login (valid)
print("\n--- 3. Login ---")
r = curl_post("http://127.0.0.1:5005/api/auth/login", '{"username":"admin","password":"admin123"}')
test("POST /api/auth/login (valid)", r, "access_token")
try:
    token = json.loads(r)["access_token"]
except:
    token = ""
    test("Token extraction", "", "access_token")

# 4. Login (invalid password)
print("\n--- 4. Login Invalid ---")
r = curl_post("http://127.0.0.1:5005/api/auth/login", '{"username":"admin","password":"wrongpass"}')
test("POST /api/auth/login (wrong pass)", r, "detail")

# 5. Login (nonexistent user)
r = curl_post("http://127.0.0.1:5005/api/auth/login", '{"username":"nonexistent","password":"test"}')
test("POST /api/auth/login (no user)", r, "detail")

# 6. Auth /me
print("\n--- 6. Auth Me ---")
if token:
    r = curl_get_auth("http://127.0.0.1:5005/api/auth/me", token)
    test("GET /api/auth/me", r, "username")

    # 7. No token
    r = curl("http://127.0.0.1:5005/api/auth/me")
    test("GET /api/auth/me (no token)", r, "detail")

    # 8. Admin: List users
    print("\n--- 8. Admin: Users ---")
    r = curl_get_auth("http://127.0.0.1:5005/api/admin/users", token)
    test("GET /api/admin/users", r, "items")

    # 9. Admin: Generate license keys (with valid_days)
    print("\n--- 9. Admin: License Keys ---")
    r = curl_post_auth("http://127.0.0.1:5005/api/admin/license-keys", '{"count":2,"valid_days":7}', token)
    test("POST /api/admin/license-keys (2 keys, 7 days)", r, "keys")
    try:
        keys_data = json.loads(r)
        test_keys = keys_data.get("data", {}).get("keys", [])
        test("valid_days in response", r, "valid_days")
    except:
        test_keys = []

    # 10. List license keys
    r = curl_get_auth("http://127.0.0.1:5005/api/admin/license-keys", token)
    test("GET /api/admin/license-keys", r, "items")

    # 11. Register with license key
    print("\n--- 11. Register ---")
    if test_keys:
        test_key = test_keys[0]
        r = curl_post("http://127.0.0.1:5005/api/auth/register",
                       json.dumps({"username":"testuser","password":"test1234","license_key":test_key}))
        test("POST /api/auth/register (new user)", r, "access_token")
        try:
            reg_data = json.loads(r)
            test_user_token = reg_data.get("access_token", "")
        except:
            test_user_token = ""

        # 12. Check user expires_at in DB
        ssh.exec_command("cat > /tmp/check_expire.py << 'PYEOF'\nimport sqlite3\nconn = sqlite3.connect('/volume1/projects/spider-xhs/backend/data/spider_xhs.db')\nfor r in conn.execute('SELECT id, username, expires_at FROM users'):\n    print(f'{r[0]}:{r[1]}:{r[2]}')\nconn.close()\nPYEOF", timeout=5)
        time.sleep(0.5)
        stdin, stdout, stderr = ssh.exec_command("python /tmp/check_expire.py 2>/dev/null")
        db_out = stdout.read().decode().strip()
        print(f"  DB users: {db_out}")
        test("DB shows expires_at for testuser", "testuser" in db_out and "2026-" in db_out)

        # 13. Duplicate register
        r = curl_post("http://127.0.0.1:5005/api/auth/register",
                       json.dumps({"username":"testuser","password":"test1234","license_key":test_key}))
        test("POST /api/auth/register (duplicate)", r, "detail")

        # 14. Used key register
        r = curl_post("http://127.0.0.1:5005/api/auth/register",
                       json.dumps({"username":"user2","password":"test1234","license_key":test_key}))
        test("POST /api/auth/register (used key)", r, "detail")

        # 15. Test user can login
        r = curl_post("http://127.0.0.1:5005/api/auth/login", '{"username":"testuser","password":"test1234"}')
        test("POST /api/auth/login (testuser)", r, "access_token")

        # 16. Test user renewal
        if test_user_token:
            # Get user ID from /me
            r = curl_get_auth("http://127.0.0.1:5005/api/auth/me", test_user_token)
            try:
                user_id = json.loads(r).get("user_id")
            except:
                user_id = None
            if user_id:
                r = curl_post_auth(f"http://127.0.0.1:5005/api/admin/users/{user_id}/renew", '{"days":15}', token)
                test("POST /api/admin/users/{id}/renew", r, "success")

    # 17. Admin: Announcements
    print("\n--- 17. Announcements ---")
    r = curl_post_auth("http://127.0.0.1:5005/api/admin/announcements",
                       '{"title":"Test","content":"Content","active":true}', token)
    test("POST /api/admin/announcements (create)", r, "success")
    try:
        ann_id = json.loads(r).get("data", {}).get("id")
    except:
        ann_id = None

    r = curl_get_auth("http://127.0.0.1:5005/api/admin/announcements", token)
    test("GET /api/admin/announcements", r, "items" if "items" in r else "success")

    if ann_id:
        r = curl_put_auth(f"http://127.0.0.1:5005/api/admin/announcements/{ann_id}",
                          '{"title":"Updated","content":"Updated content","active":true}', token)
        test("PUT /api/admin/announcements", r, "success")

        r = curl_del_auth(f"http://127.0.0.1:5005/api/admin/announcements/{ann_id}", token)
        test("DELETE /api/admin/announcements", r, "success")

    # 18. Model config
    print("\n--- 18. Model Config ---")
    r = curl_get_auth("http://127.0.0.1:5005/api/admin/model-config", token)
    test("GET /api/admin/model-config", r, "llm_provider")

    # 19. Non-admin access to admin endpoint
    print("\n--- 19. Non-admin Access ---")
    if test_user_token:
        r = curl_get_auth("http://127.0.0.1:5005/api/admin/users", test_user_token)
        test("GET /api/admin/users (non-admin)", r, "detail")

    # 20. Frontend SPA
    print("\n--- 20. Frontend ---")
    r = curl("http://127.0.0.1:5005/")
    test("GET / (SPA)", r, "html")
    r = curl("http://xhs.maomaoxia.top/")
    test("GET xhs.maomaoxia.top/", r, "html")

    # Cleanup: delete test user
    print("\n--- Cleanup ---")
    if test_user_token:
        try:
            user_id_clean = json.loads(curl_get_auth("http://127.0.0.1:5005/api/auth/me", test_user_token)).get("user_id")
            if user_id_clean:
                r = curl_del_auth(f"http://127.0.0.1:5005/api/admin/users/{user_id_clean}", token)
                test("DELETE test user", r, "success")
        except:
            pass

else:
    print("\n  SKIP: No token, skipping auth tests")

# Summary
print("\n\n========== SUMMARY ==========")
pass_count = sum(1 for _, s, _ in results if s == "PASS")
fail_count = sum(1 for _, s, _ in results if s == "FAIL")
print(f"  PASS: {pass_count}")
print(f"  FAIL: {fail_count}")
if fail_count:
    print("\n  Failed tests:")
    for name, status, msg in results:
        if status == "FAIL":
            print(f"    - {name}: {msg[:150]}")

ssh.close()
