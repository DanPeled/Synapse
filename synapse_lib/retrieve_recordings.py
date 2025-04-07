# import paramiko
# from scp import SCPClient
#
# HOST = "10.97.38.14"
# USERNAME = "orangepi"
# PASSWORD = "orangepi"
# REMOTE_DIR = "~/Synapse/logs"
# LOCAL_DIR = "./logs"
#
#
# # Function to create an SSH client
# def create_ssh_client(host, username, password):
#     client = paramiko.SSHClient()
#     client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#     client.connect(host, username=username, password=password)
#     return client
#
#
# # Function to get .avi files from the remote directory
# def fetch_avi_files():
#     ssh = create_ssh_client(HOST, USERNAME, PASSWORD)
#     transport = ssh.get_transport()
#     if transport is not None:
#         scp = SCPClient(transport)
#
#         # Ensure we are in the correct directory
#         stdin, stdout, stderr = ssh.exec_command(f"cd {REMOTE_DIR} && ls *.avi")
#         files = stdout.read().decode().split()
#
#         if not files:
#             print("No AVI files found.")
#         else:
#             for file in files:
#                 remote_path = f"{REMOTE_DIR}/{file}"
#                 local_path = f"{LOCAL_DIR}/{file}"
#                 print(f"Downloading {file}...")
#                 scp.get(remote_path, local_path)
#                 print(f"Downloaded {file} to {local_path}")
#
#         scp.close()
#         ssh.close()
#
#
# if __name__ == "__main__":
#     fetch_avi_files()
