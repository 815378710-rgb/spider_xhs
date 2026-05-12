import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.68.161", 22, "maomaoxia", "CongShaoYu102@", timeout=10)

def sudo(cmd, timeout=20):
    full = "echo 'CongShaoYu102@' | sudo -S " + cmd
    stdin, stdout, stderr = ssh.exec_command(full, timeout=timeout)
    return stdout.read().decode().strip()

DOCKER = "/volume1/@appstore/ContainerManager/usr/bin/docker"

# Write a helper script on the NAS host
helper = f'''#!/bin/bash
DOCKER="{DOCKER}"
echo "=== All containers ==="
$DOCKER ps -a --no-trunc=false 2>/dev/null | grep -E "NAME|potato"

echo ""
echo "=== Images with python ==="
$DOCKER images 2>/dev/null | grep -E "NAME|python"

echo ""
echo "=== potato-xhs inspect ==="
$DOCKER inspect potato-xhs 2>/dev/null | head -5 || echo "Container not found"

echo ""
echo "=== If potato-xhs missing, recreate ==="
if ! $DOCKER inspect potato-xhs >/dev/null 2>&1; then
    echo "Creating potato-xhs..."
    $DOCKER run -d \\
        --name potato-xhs \\
        --restart unless-stopped \\
        -p 5005:5005 \\
        -v /volume1/projects/spider-xhs/config:/app/config \\
        -v /volume1/projects/spider-xhs/frontend/dist:/app/frontend/dist \\
        -v /volume1/projects/spider-xhs/backend:/app/backend \\
        -w /app \\
        python:3.11-slim \\
        sh -c "pip install --no-cache-dir fastapi uvicorn sqlalchemy aiosqlite python-jose[cryptography] cryptography loguru httpx schedule pydantic aiofiles Pillow -q && python backend/main.py"
    echo "Created! Waiting..."
    sleep 30
    echo "=== New status ==="
    $DOCKER ps --filter name=potato-xhs
fi
'''

stdin, stdout, stderr = ssh.exec_command("cat > /tmp/fix_container.sh && chmod +x /tmp/fix_container.sh", timeout=5)
stdin.write(helper.encode())
stdin.channel.shutdown_write()
stdout.read()

time.sleep(0.5)

# Run it
stdin, stdout, stderr = ssh.exec_command(
    "echo 'CongShaoYu102@' | sudo -S bash /tmp/fix_container.sh 2>&1",
    timeout=180
)
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
