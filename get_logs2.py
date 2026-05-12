import paramiko, time

NAS_HOST = "192.168.68.161"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_HOST, 22, "maomaoxia", "CongShaoYu102@", timeout=10)

# Step 1: get docker logs to file
cmd1 = "echo 'CongShaoYu102@' | sudo -S /volume1/@appstore/ContainerManager/usr/bin/docker logs potato-xhs > /tmp/potato_logs.txt 2>&1"
stdin, stdout, stderr = ssh.exec_command(cmd1, timeout=20)
stdout.read()
stderr.read()
time.sleep(1)

# Step 2: read it
stdin, stdout, stderr = ssh.exec_command("cat /tmp/potato_logs.txt 2>/dev/null || echo EMPTY")
logs = stdout.read().decode()
print(f"Length: {len(logs)}")
print(logs[-2000:] if logs else "EMPTY")

ssh.close()
