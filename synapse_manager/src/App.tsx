import "./App.css";
import DeviceTable from "./device_table";
import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { DiscoveryResponse } from "./udp";

function App() {
  const [devices, setDevices] = useState<DiscoveryResponse[]>([]);
  const [loading, setLoading] = useState(false);

  async function scanDevices() {
    setLoading(true);

    try {
      const res = await invoke<{ devices: DiscoveryResponse[] }>(
        "scan_devices",
      );
      setDevices(res.devices);
    } catch (err) {
      console.error("scan failed", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    scanDevices(); // initial run

    const id = setInterval(() => {
      scanDevices();
    }, 5000);

    return () => clearInterval(id);
  }, []);

  return (
    <main className="container">
      <div className="row flex items-center gap-4">
        <button
          onClick={scanDevices}
          className="text-xm text-[#ff66c4] font-bold w-40 ml-2"
        >
          {loading ? "Scanning..." : "Find Devices"}
        </button>

        <p className="text-sm m-0 text-gray-200">
          Click on any hostname or IP address to navigate to the web interface
          of the corresponding device
        </p>
      </div>

      <DeviceTable devices={devices} />
    </main>
  );
}

export default App;
