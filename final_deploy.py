import paramiko, time

NAS = "192.168.68.161"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS, 22, "maomaoxia", "CongShaoYu102@", timeout=10)

DOCKER = "/volume1/@appstore/ContainerManager/usr/bin/docker"
REMOTE = "/volume1/projects/spider-xhs/backend"
LOCAL = "C:/Users/81537/WorkBuddy/2026-05-11-task-19/spider_xhs/backend"

def sudo(cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command("echo 'CongShaoYu102@' | sudo -S " + cmd, timeout=timeout)
    return stdout.read().decode().strip()

def upload(rel):
    with open(f"{LOCAL}/{rel}", "rb") as f:
        data = f.read()
    stdin, stdout, stderr = ssh.exec_command(f"cat > {REMOTE}/{rel}", timeout=30)
    stdin.write(data)
    stdin.channel.shutdown_write()
    stdout.read()
    print(f"  {rel} -> {len(data)} bytes")

def curl_get(url):
    stdin, stdout, stderr = ssh.exec_command(f"curl -s --connect-timeout 5 --max-time 10 {url}")
    return stdout.read().decode().strip()

def curl_post(url, data):
    cmd = f"""curl -s --connect-timeout 5 --max-time 10 -X POST {url} -H 'Content-Type: application/json' -d '{data}'"""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode().strip()

# Step 1: Upload files
print("=== 1. Upload files ===")
for f in ["main.py", "models/user.py", "routers/auth.py", "routers/admin.py", "core/deps.py"]:
    upload(f)

# Step 2: Clear DB + pycache
print("\n=== 2. Clear DB + pycache ===")
sudo("rm -f /volume1/projects/spider-xhs/backend/data/spider_xhs.db")
sudo("find /volume1/projects/spider-xhs/backend -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null")
print("  Done")

# Step 3: Restart container
print("\n=== 3. Restart container ===")
sudo(f"{DOCKER} kill potato-xhs 2>/dev/null")
time.sleep(2)
sudo(f"{DOCKER} start potato-xhs 2>/dev/null")
print("  Waiting 18s for startup...")
time.sleep(18)

# Step 4: Verify
print("\n=== 4. Verify ===")

print("Health:", curl_get("http://127.0.0.1:5005/api/health"))
print("Login:", curl_post("http://127.0.0.1:5005/api/auth/login", '{"username":"admin","password":"admin123"}'))

# DB check
ssh.exec_command("cat > /tmp/v.py << 'PYEOF'\nimport sqlite3\nconn = sqlite3.connect('/volume1/projects/spider-xhs/backend/data/spider_xhs.db')\nfor r in conn.execute('SELECT id, username, role, expires_at FROM users'):\n    print(f'User {r[0]}: {r[1]} role={r[2]} expires={r[3]}')\nfor r in conn.execute('SELECT id, key, valid_days, status FROM license_keys LIMIT 3'):\n    print(f'Key {r[0]}: {r[1]} days={r[2]} status={r[3]}')\nconn.close()\nPYEOF", timeout=5)
time.sleep(0.5)
stdin, stdout, stderr = ssh.exec_command("python /tmp/v.py 2>/dev/null")
print(f"\nDB:\n{stdout.read().decode()}")

ssh.close()
print("=== DONE ===")
