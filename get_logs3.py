import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.68.161", 22, "maomaoxia", "CongShaoYu102@", timeout=10)

def sudo(cmd, timeout=10):
    stdin, stdout, stderr = ssh.exec_command(
        "echo 'CongShaoYu102@' | sudo -S " + cmd, timeout=timeout
    )
    return stdout.read().decode().strip()

# Stop, clear logs, start fresh
sudo("/volume1/@appstore/ContainerManager/usr/bin/docker stop potato-xhs 2>/dev/null", timeout=15)
time.sleep(2)
sudo("/volume1/@appstore/ContainerManager/usr/bin/docker rm -f potato-xhs 2>/dev/null", timeout=10)
# Actually let's just restart, not remove - check if it still exists
print("status:", sudo("/volume1/@appstore/ContainerManager/usr/bin/docker ps -a --filter name=potato-xhs --format '{{.Names}} {{.Status}}' 2>/dev/null"))

# OK let's try running main.py manually in the container
# to see startup errors
print("\n=== Running main.py startup test ===")
# Write a test script that imports everything like main.py does
test_script = r'''
import sys, traceback
sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app")
try:
    from main import app, _init_admin_and_keys
    import asyncio
    print("App loaded OK, version:", app.version)
    print("Running _init_admin_and_keys...")
    asyncio.run(_init_admin_and_keys())
    print("Admin init OK!")
except Exception as e:
    traceback.print_exc()
    print("ERROR:", e)
'''
stdin, stdout, stderr = ssh.exec_command("cat > /tmp/startup_test.py", timeout=5)
stdin.write(test_script.encode())
stdin.channel.shutdown_write()
stdout.read()

# Copy to container via running cat on host then docker cp... 
# Actually, easier: docker exec python with a file
# But we need to get the file into the container first.
# Let's use volume mount - write to the NAS backend dir
stdin, stdout, stderr = ssh.exec_command(
    "cat > /volume1/projects/spider-xhs/backend/startup_diag.py", timeout=5
)
stdin.write(test_script.encode())
stdin.channel.shutdown_write()
stdout.read()

# Now run it in container
out = sudo(
    "/volume1/@appstore/ContainerManager/usr/bin/docker exec "
    "-w /app/backend potato-xhs python startup_diag.py 2>&1",
    timeout=20
)
print(out)

# Also get the actual container logs now
# Try a different approach: docker logs --since (last 60 seconds)
out2 = sudo(
    "/volume1/@appstore/ContainerManager/usr/bin/docker logs --since 5m potato-xhs 2>&1 | tail -50",
    timeout=20
)
print("\n=== Docker logs (last 50 lines) ===")
print(out2)

ssh.close()
