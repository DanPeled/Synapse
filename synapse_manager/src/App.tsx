import "./App.css";
import DeviceTable from "./device_table";

function App() {
  return (
    <main className="container">
      <div className="row flex items-center gap-4">
        <button className="text-xm text-[#ff66c4] font-bold w-40 ml-2">
          Find Devices
        </button>

        <p className="text-sm m-0 text-[#bd3a8a]">
          Click on any hostname or IP address to navigate to the web interface
          of the corresponding device
        </p>
      </div>
      <DeviceTable />
    </main>
  );
}

export default App;
