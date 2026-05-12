import paramiko, time

NAS_HOST = "192.168.68.161"
NAS_USER = "maomaoxia"
NAS_PASS = "CongShaoYu102@"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_HOST, 22, NAS_USER, NAS_PASS, timeout=10)

def sudo(cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(f"echo 'CongShaoYu102@' | sudo -S {cmd}", timeout=timeout)
    return stdout.read().decode().strip()

def run(cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()

# Check container status
print("Container:", sudo("/volume1/@appstore/ContainerManager/usr/bin/docker ps --filter name=potato-xhs --format '{{.Status}}' 2>/dev/null"))

# Wait more and retry
for attempt in range(4):
    time.sleep(5)
    health = run("curl -s --connect-timeout 3 --max-time 5 http://127.0.0.1:5005/api/health")
    print(f"Attempt {attempt+1}: health={health}")
    if health and "ok" in health:
        break

# Login
login = run("""curl -s --connect-timeout 5 --max-time 10 -X POST http://127.0.0.1:5005/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}'""")
print(f"Login: {login[:400]}")

# Public access
status = run("curl -s --connect-timeout 5 --max-time 10 -o /dev/null -w '%{http_code}' http://xhs.maomaoxia.top/")
print(f"Public HTTP: {status}")

ssh.close()
