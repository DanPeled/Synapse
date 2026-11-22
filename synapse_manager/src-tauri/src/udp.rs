use serde::{Deserialize, Serialize};
use std::net::UdpSocket;
use std::time::{Duration, Instant};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DiscoveryResponse {
    pub ip: String,
    pub hostname: String,
    pub nickname: String,
    pub team_number: u32,
    pub version: String,
    pub username: String,
    #[serde(default)]
    pub addresses: Vec<String>,
    #[serde(default, rename = "directLink")]
    pub direct_link: bool,
}

const PORT: u16 = 45454;
const PING: &str = "PING_DISCOVERY";
// Address for IPv4 link-local subnets, used by USB gadget direct connections.
const LINK_LOCAL_BROADCAST: &str = "169.254.255.255";

#[derive(Serialize)]
pub struct ScanResult {
    pub devices: Vec<DiscoveryResponse>,
}

fn discover_devices_with_socket(socket: &UdpSocket) -> Vec<DiscoveryResponse> {
    socket.set_broadcast(true).ok();
    socket
        .set_read_timeout(Some(Duration::from_millis(100)))
        .ok();

    // Both the global broadcast (router/robot network) and the link-local
    // broadcast (USB gadget direct connection) are covered. Sending to an
    // unused broadcast address is harmless.
    let targets = [
        format!("255.255.255.255:{PORT}"),
        format!("{LINK_LOCAL_BROADCAST}:{PORT}"),
    ];

    for target in &targets {
        socket.send_to(PING.as_bytes(), target).ok();
    }

    let mut buf = [0u8; 2048];
    let mut results = Vec::new();

    let start = Instant::now();

    while start.elapsed() < Duration::from_millis(500) {
        match socket.recv_from(&mut buf) {
            Ok((size, _)) => {
                let msg = String::from_utf8_lossy(&buf[..size]);

                if let Ok(device) = serde_json::from_str::<DiscoveryResponse>(&msg) {
                    results.push(device);
                }
            }
            Err(_) => {}
        }
    }

    results
}

fn discover_devices() -> Vec<DiscoveryResponse> {
    let socket = UdpSocket::bind("0.0.0.0:0").expect("failed to bind socket");

    discover_devices_with_socket(&socket)
}

#[tauri::command]
pub async fn scan_devices() -> ScanResult {
    tauri::async_runtime::spawn_blocking(|| ScanResult {
        devices: discover_devices(),
    })
    .await
    .unwrap()
}
