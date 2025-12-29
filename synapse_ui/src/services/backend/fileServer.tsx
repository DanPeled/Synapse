import { DeviceInfoProto } from "@/proto/v1/device";
import JSZip from "jszip";

export const FILE_SERVER_PORT = 8080;
export const FILE_SERVER_URL = (deviceInfo: DeviceInfoProto) => {
  return `http://${deviceInfo.ip}:${FILE_SERVER_PORT}`;
};

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
  const res = await fetch(`${FILE_SERVER_URL(device)}/${targetPath}`, {
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
