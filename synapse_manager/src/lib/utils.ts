import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { WebviewWindow } from "@tauri-apps/api/webviewWindow";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export async function openWindow({
  label,
  url = undefined,
}: {
  label: string;
  url?: string;
}) {
  console.log("openWindow called:", label);

  const existing = await WebviewWindow.getByLabel(label);

  console.log("existing:", existing);

  if (existing) {
    await existing.setFocus();
    return;
  }

  const win = new WebviewWindow(label, {
    title: label,
    url: url ?? `/#/${label}`,
    width: 1920 / 1.5,
    height: 1080 / 1.5,
  });

  win.once("tauri://created", () => {
    console.log("window created");
  });

  win.once("tauri://error", (e) => {
    console.error("window error", e);
  });
}
