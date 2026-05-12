import paramiko, time

NAS_HOST = "192.168.68.161"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_HOST, 22, "maomaoxia", "CongShaoYu102@", timeout=10)

def sudo(cmd, timeout=30):
    full = "echo 'CongShaoYu102@' | sudo -S " + cmd
    stdin, stdout, stderr = ssh.exec_command(full, timeout=timeout)
    return stdout.read().decode().strip(), stderr.read().decode().strip()

# Write docker logs to file (avoids paramiko hang)
out, err = sudo(
    "/volume1/@appstore/ContainerManager/usr/bin/docker logs potato-xhs "
    "> /volume1/projects/spider-xhs/backend/startup.log 2>&1",
    timeout=30
)
print("logs redirect:", out, err)
time.sleep(2)

# Read it
stdin, stdout, stderr = ssh.exec_command(
    "cat /volume1/projects/spider-xhs/backend/startup.log"
)
logs = stdout.read().decode()
print(f"=== Log length: {len(logs)} chars ===")
print(logs[-3000:] if len(logs) > 3000 else logs)

ssh.close()
