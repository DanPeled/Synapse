import "./App.css";
import DeviceTable from "./device_table";
import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { DiscoveryResponse } from "./udp";
import { LoaderCircle, Search } from "lucide-react";

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
    scanDevices();

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
          className="text-xm text-[#ff66c4] font-bold w-45 ml-2 flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <LoaderCircle className="w-4 h-4 animate-spin" />
              Scanning...
            </>
          ) : (
            <>
              <Search className="w-4 h-4" />
              Find Devices
            </>
          )}
        </button>
      </div>

      <DeviceTable devices={devices} />
    </main>
  );
}

export default App;
