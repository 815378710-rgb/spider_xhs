import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.68.161", 22, "maomaoxia", "CongShaoYu102@", timeout=10)

def sudo(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(
        "echo 'CongShaoYu102@' | sudo -S " + cmd, timeout=timeout
    )
    return stdout.read().decode().strip()

DOCKER = "/volume1/@appstore/ContainerManager/usr/bin/docker"

# First try: just create from the existing image potato-xhs:latest
# The image already has all dependencies baked in
create_cmd = (
    f"{DOCKER} create "
    f"--name potato-xhs "
    f"--restart unless-stopped "
    f"-p 5005:5005 "
    f"-v /volume1/projects/spider-xhs/config:/app/config "
    f"-v /volume1/projects/spider-xhs/frontend/dist:/app/frontend/dist "
    f"-v /volume1/projects/spider-xhs/backend:/app/backend "
    f"-w /app "
    f"potato-xhs:latest "
    f"python backend/main.py"
)

print("Creating container...")
result = sudo(create_cmd)
print(f"Create: {result}")

# Start it
print("Starting...")
result = sudo(f"{DOCKER} start potato-xhs")
print(f"Start: {result}")

# Wait for startup
print("Waiting 15s...")
time.sleep(15)

# Check status
status = sudo(f"{DOCKER} ps --filter name=potato-xhs 2>/dev/null")
print(f"\nRunning:\n{status}")

# Health check
stdin, stdout, stderr = ssh.exec_command("curl -s --connect-timeout 5 --max-time 10 http://127.0.0.1:5005/api/health")
health = stdout.read().decode().strip()
print(f"\nHealth: {health}")

# Login test
stdin, stdout, stderr = ssh.exec_command("""curl -s --connect-timeout 5 --max-time 10 -X POST http://127.0.0.1:5005/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}'""")
login = stdout.read().decode().strip()
print(f"Login: {login[:400]}")

# Public access
stdin, stdout, stderr = ssh.exec_command("curl -s --connect-timeout 5 --max-time 10 -o /dev/null -w '%{http_code}' http://xhs.maomaoxia.top/")
print(f"Public: {stdout.read().decode().strip()}")

# Check logs via tail
logs = sudo(f"{DOCKER} logs potato-xhs 2>&1 | tail -30", timeout=20)
print(f"\n=== Logs ===\n{logs}")

ssh.close()
print("\n=== DONE ===")
