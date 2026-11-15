import { DeviceInfoProto } from "@/generated/messages/v1/device";
import JSZip from "jszip";

export const FILE_SERVER_PORT = 8080;
export const FILE_SERVER_URL = (deviceInfo: DeviceInfoProto) => {
  return `http://${deviceInfo.ip}:${FILE_SERVER_PORT}`;
};

export interface FileEntry {
  name: string;
  path: string;
  isDir: boolean;
  size: number;
}

export interface FilePreview {
  path: string;
  name: string;
  size: number;
  isText: boolean;
  content: string | null;
  truncated: boolean;
  maxBytes: number;
}

interface FileEntryResponse {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
}

interface FilePreviewResponse {
  path: string;
  name: string;
  size: number;
  is_text: boolean;
  content: string | null;
  truncated: boolean;
  max_bytes: number;
}

function normalizeRelativePath(path: string): string {
  return path.replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
}

export function joinFilePath(basePath: string, name: string): string {
  const base = normalizeRelativePath(basePath);
  const child = normalizeRelativePath(name);
  return base ? `${base}/${child}` : child;
}

export function parentFilePath(path: string): string {
  const normalized = normalizeRelativePath(path);
  const index = normalized.lastIndexOf("/");
  return index === -1 ? "" : normalized.slice(0, index);
}

export async function listFiles(
  device: DeviceInfoProto,
  path = "",
): Promise<FileEntry[]> {
  const normalized = normalizeRelativePath(path);
  const query = normalized ? `?path=${encodeURIComponent(normalized)}` : "";

  const res = await fetch(`${FILE_SERVER_URL(device)}/list${query}`);
  if (!res.ok) {
    throw new Error(await res.text());
  }

  const data = (await res.json()) as {
    path: string;
    entries: FileEntryResponse[];
  };
  return data.entries.map((entry) => ({
    name: entry.name,
    path: entry.path,
    isDir: entry.is_dir,
    size: entry.size,
  }));
}

export async function readFile(
  device: DeviceInfoProto,
  path: string,
): Promise<FilePreview> {
  const normalized = normalizeRelativePath(path);
  const query = `?path=${encodeURIComponent(normalized)}`;

  const res = await fetch(`${FILE_SERVER_URL(device)}/read${query}`);
  if (!res.ok) {
    throw new Error(await res.text());
  }

  const data = (await res.json()) as FilePreviewResponse;
  return {
    path: data.path,
    name: data.name,
    size: data.size,
    isText: data.is_text,
    content: data.content,
    truncated: data.truncated,
    maxBytes: data.max_bytes,
  };
}

async function fetchFolder(
  baseUrl: string,
  folderPath = "",
  zip?: JSZip,
): Promise<JSZip> {
  if (!zip) zip = new JSZip(); // initialize if undefined

  const url = `${baseUrl}${folderPath}`.replace(/\/+$/, "/");
  const html = await fetch(url).then((res) => res.text());
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, "text/html");

  const links = Array.from(doc.querySelectorAll("a"))
    .map((a) => a.getAttribute("href"))
    .filter(Boolean) as string[];

  for (const link of links) {
    if (link === "../") continue;

    if (link.endsWith("/")) {
      await fetchFolder(
        baseUrl,
        folderPath + link,
        zip.folder(link.slice(0, -1)) as JSZip,
      );
    } else {
      const fileUrl = url + link;
      const blob = await fetch(fileUrl).then((r) => r.blob());
      zip.file(link, blob);
    }
  }

  return zip;
}

// Download button handler
export async function downloadHttpDirectoryAsZip(
  baseUrl: string,
  fileName: string,
) {
  const zip = await fetchFolder(baseUrl);
  const zipBlob = await zip.generateAsync({ type: "blob" });

  const a = document.createElement("a");
  a.href = URL.createObjectURL(zipBlob);
  a.download = `${fileName}.zip`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export async function uploadFileReplace(
  device: DeviceInfoProto,
  file: File,
  targetPath: string,
) {
  const encodedPath = targetPath
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");

  const res = await fetch(`${FILE_SERVER_URL(device)}/${encodedPath}`, {
    method: "PUT",
    body: file,
  });

  if (!res.ok) {
    throw new Error(await res.text());
  }
}

export async function uploadZipReplaceFolder(
  device: DeviceInfoProto,
  zipFile: File,
  targetFolder: string,
) {
  const form = new FormData();
  form.append("file", zipFile);

  const res = await fetch(
    `${FILE_SERVER_URL(device)}/extract?target=${encodeURIComponent(
      targetFolder,
    )}&replace=true`,
    {
      method: "POST",
      body: form,
    },
  );

  if (!res.ok) {
    throw new Error(await res.text());
  }
}
