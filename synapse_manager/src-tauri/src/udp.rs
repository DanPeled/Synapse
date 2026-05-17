use serde::Deserialize;
use serde::Serialize;
use std::net::UdpSocket;
use std::time::{Duration, Instant};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveryResponse {
    pub ip: String,
    pub hostname: String,
    pub nickname: String,
    pub team_number: u32,
    pub version: String,
}

const PORT: u16 = 45454;
const PING: &str = "PING_DISCOVERY";

#[derive(Serialize)]
pub struct ScanResult {
    pub devices: Vec<DiscoveryResponse>,
}

fn discover_devices() -> Vec<DiscoveryResponse> {
    // ephemeral socket for receiving replies
    let socket = UdpSocket::bind("0.0.0.0:0").expect("failed to bind socket");

    socket.set_broadcast(true).ok();
    socket
        .set_read_timeout(Some(Duration::from_millis(500)))
        .ok();

    // send ping
    let target = format!("255.255.255.255:{PORT}");
    socket
        .send_to(PING.as_bytes(), &target)
        .expect("failed to send ping");

    let mut buf = [0u8; 2048];
    let mut results = Vec::new();

    let start = Instant::now();

    // collect replies for ~2 seconds
    while start.elapsed() < Duration::from_secs(2) {
        match socket.recv_from(&mut buf) {
            Ok((size, _addr)) => {
                let msg = String::from_utf8_lossy(&buf[..size]);

                if let Ok(device) = serde_json::from_str::<DiscoveryResponse>(&msg) {
                    results.push(device);
                }
            }
            Err(_) => {
                // timeout -> just continue until window ends
            }
        }
    }

    results
}

#[tauri::command]
pub async fn scan_devices() -> ScanResult {
    tauri::async_runtime::spawn_blocking(|| ScanResult {
        devices: discover_devices(),
    })
    .await
    .unwrap()
}
