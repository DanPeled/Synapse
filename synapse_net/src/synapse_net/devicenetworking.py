import shutil
import subprocess
from typing import Optional

from synapse.log import err, log


def setStaticIP(ip: str, interface: str, gateway: str, prefix_length: int = 24) -> None:
    # BUG: doesnt work correctly at the moment, unsure why
    try:
        # Add IP with correct prefix length
        subprocess.run(
            ["sudo", "ip", "addr", "add", f"{ip}/{prefix_length}", "dev", interface],
            check=True,
        )

        # Bring interface up
        subprocess.run(["sudo", "ip", "link", "set", interface, "up"], check=True)

        # Delete any existing default route
        subprocess.run(["sudo", "ip", "route", "del", "default"], check=False)

        # Add default gateway explicitly specifying interface
        subprocess.run(
            ["sudo", "ip", "route", "add", "default", "via", gateway, "dev", interface],
            check=True,
        )

        log(
            f"Static IP {ip}/{prefix_length} set on interface {interface} with gateway {gateway}"
        )
    except Exception as e:
        err(f"Failed to set static IP: {e}")


def setHostname(hostname: str) -> None:
    try:
        # Set temporary hostname
        subprocess.run(["sudo", "hostname", hostname], check=True)

        # Persistently set hostname
        if shutil.which("hostnamectl"):
            subprocess.run(
                ["sudo", "hostnamectl", "set-hostname", hostname], check=True
            )
        else:
            subprocess.run(
                ["sudo", "sh", "-c", f"echo '{hostname}' > /etc/hostname"], check=True
            )

        updateHostsFile(hostname)

        log(f"Hostname successfully set to '{hostname}'")
    except Exception as e:
        err(f"Failed to set hostname: {e}")


def updateHostsFile(new_hostname):
    try:
        # Read /etc/hosts using sudo
        result = subprocess.run(
            ["sudo", "cat", "/etc/hosts"], check=True, capture_output=True, text=True
        )
        lines = result.stdout.splitlines()

        new_lines = []
        replaced = False
        for line in lines:
            if line.startswith("127.0.1.1"):
                new_lines.append(f"127.0.1.1\t{new_hostname}")
                replaced = True
            else:
                new_lines.append(line)

        if not replaced:
            new_lines.append(f"127.0.1.1\t{new_hostname}")

        # Write back using tee and sudo
        content = "\n".join(new_lines) + "\n"
        subprocess.run(
            ["sudo", "tee", "/etc/hosts"], input=content, text=True, check=True
        )

    except Exception as e:
        err(f"Failed to update /etc/hosts: {e}")


def getDefaultGateway() -> Optional[str]:
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Example output: "default via 192.168.1.1 dev eth0 proto dhcp metric 100"
        for line in result.stdout.splitlines():
            parts = line.split(" ")
            if "default" in parts and "via" in parts:
                gatewayIndex = parts.index("via") + 1
                return parts[gatewayIndex]
    except Exception as e:
        err(f"Failed to get default gateway: {e}")
    return None
