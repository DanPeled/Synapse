import "./globals.css";
import { BackendContextProvider } from "@/services/backend/backendContext";
import { Sidebar } from "@/widgets/sidebar";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`font-mono`}>
        <BackendContextProvider>
          <div
            className="flex min-h-screen"
            style={{ backgroundColor: "#8a1e60" }}
          >
            <Sidebar compact={true} />
            <div className="flex-1" style={{ marginLeft: "3.75rem" }}>
              {children}
            </div>
          </div>
        </BackendContextProvider>
      </body>
    </html>
  );
}
