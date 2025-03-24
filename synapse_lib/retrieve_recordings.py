import os
import paramiko
import cv2
from scp import SCPClient

HOST = "10.97.38.14"
USERNAME = "orangepi"
PASSWORD = "orangepi"
REMOTE_DIR = "~/Synapse/logs"
LOCAL_DIR = "./logs"

# Ensure the local directory exists
os.makedirs(LOCAL_DIR, exist_ok=True)


# Function to create an SSH client
def create_ssh_client(host, username, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=username, password=password)
    return client


# Function to get .avi files from the remote directory
def fetch_avi_files():
    ssh = create_ssh_client(HOST, USERNAME, PASSWORD)
    transport = ssh.get_transport()
    latest_file = None

    if transport is not None:
        scp = SCPClient(transport)

        # Ensure we are in the correct directory
        stdin, stdout, stderr = ssh.exec_command(f"cd {REMOTE_DIR} && ls -t *.avi")
        files = stdout.read().decode().split()

        if not files:
            print("No AVI files found.")
        else:
            latest_file = files[0]  # Get the most recent file
            remote_path = f"{REMOTE_DIR}/{latest_file}"
            local_path = os.path.join(LOCAL_DIR, latest_file)

            print(f"Downloading {latest_file}...")
            scp.get(remote_path, local_path)
            print(f"Downloaded {latest_file} to {local_path}")

        scp.close()
        ssh.close()

    return latest_file


# Function to play the video
def play_video(video_path):
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"Error: Unable to open video file {video_path}")
        return

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow("Video Playback", frame)

        if cv2.waitKey(30) & 0xFF == ord("q"):  # Press 'q' to exit
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    latest_video = fetch_avi_files()
    if latest_video:
        local_video_path = os.path.join(LOCAL_DIR, latest_video)
        play_video(local_video_path)
