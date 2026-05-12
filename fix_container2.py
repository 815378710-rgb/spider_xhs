import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.68.161", 22, "maomaoxia", "CongShaoYu102@", timeout=10)

def sudo(cmd, timeout=20):
    full = "echo 'CongShaoYu102@' | sudo -S " + cmd
    stdin, stdout, stderr = ssh.exec_command(full, timeout=timeout)
    return stdout.read().decode().strip()

DOCKER = "/volume1/@appstore/ContainerManager/usr/bin/docker"

# Step 1: find what python images exist
stdin, stdout, stderr = ssh.exec_command(
    "echo 'CongShaoYu102@' | sudo -S /volume1/@appstore/ContainerManager/usr/bin/docker images --format '{{.Repository}}:{{.Tag}}'",
    timeout=15
)
# Can't use Go template with paramiko, try raw
stdin2, stdout2, stderr2 = ssh.exec_command(
    "echo 'CongShaoYu102@' | sudo -S /volume1/@appstore/ContainerManager/usr/bin/docker images 2>/dev/null | head -30",
    timeout=15
)
print("=== Available images ===")
print(stdout2.read().decode())

# Step 2: Check all containers (including stopped)
stdin3, stdout3, stderr3 = ssh.exec_command(
    "echo 'CongShaoYu102@' | sudo -S /volume1/@appstore/ContainerManager/usr/bin/docker ps -a 2>/dev/null | head -20",
    timeout=15
)
print("=== All containers ===")
print(stdout3.read().decode())

ssh.close()
