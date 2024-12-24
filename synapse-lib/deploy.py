import os
import paramiko
import tarfile

if __name__ == "__main__":
    hostname = "192.168.1.158"
    port = 22
    username = "orangepi"
    password = "orangepi"

    current_folder = os.getcwd()

    remote_path = "~/Synapse/"

    tarball_path = "/tmp/deploy.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(current_folder, arcname=os.path.basename(current_folder))

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(hostname, port, username, password)

    ssh.exec_command(f"mkdir -p {remote_path}")

    sftp = ssh.open_sftp()
    sftp.put(tarball_path, "/tmp/deploy.tar.gz")

    ssh.exec_command(f"tar -xzf /tmp/deploy.tar.gz -C {remote_path}")

    ssh.exec_command("rm /tmp/deploy.tar.gz")

    sftp.close()
    ssh.close()

    print(f"Deployment to {hostname}:{remote_path} complete.")
