import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { BackendContextProvider } from "@/services/backend/backendContext";
import { Sidebar } from "@/widgets/sidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Synapse Client",
  description: "",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
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
