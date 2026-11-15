"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useBackendContext } from "@/services/backend/backendContext";
import {
  FileEntry,
  FilePreview,
  joinFilePath,
  listFiles,
  parentFilePath,
  readFile,
  uploadFileReplace,
} from "@/services/backend/fileServer";
import { borderColor, teamColor } from "@/services/style";
import { useFilePicker } from "@/services/useFilePicker";
import { AlertDialog } from "@/widgets/alertDialog";
import {
  ChevronUp,
  Eye,
  File as FileIcon,
  Folder,
  FolderOpen,
  Home,
  Loader2,
  RefreshCw,
  Upload,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Column, Row } from "./containers";

interface FileSettingControlProps {
  value: string;
  onChange: (value: string) => void;
  basePath?: string;
  fileTypes?: string[];
  disabled?: boolean;
}

const buttonClass =
  "cursor-pointer rounded-md border bg-zinc-800 hover:bg-zinc-700";
const buttonStyle = { borderColor, color: teamColor };

function normalizePath(path: string): string {
  return path.replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
}

function normalizeFileTypes(fileTypes: string[]): string[] {
  return fileTypes
    .map((fileType) => fileType.trim().toLowerCase())
    .filter(Boolean)
    .map((fileType) => (fileType.startsWith(".") ? fileType : `.${fileType}`));
}

function matchesFileType(name: string, fileTypes: string[]): boolean {
  if (fileTypes.length === 0) return true;
  const lowerName = name.toLowerCase();
  return fileTypes.some((fileType) => lowerName.endsWith(fileType));
}

function fileNameFromPath(path: string): string {
  const normalized = normalizePath(path);
  const index = normalized.lastIndexOf("/");
  return index === -1 ? normalized : normalized.slice(index + 1);
}

function formatPreviewContent(preview: FilePreview): string {
  const content = preview.content ?? "";
  if (preview.name.toLowerCase().endsWith(".json")) {
    try {
      return JSON.stringify(JSON.parse(content), null, 2);
    } catch {
      return content;
    }
  }
  return content;
}

export function FileSettingControl({
  value,
  onChange,
  basePath = "",
  fileTypes = [],
  disabled = false,
}: FileSettingControlProps) {
  const { deviceinfo } = useBackendContext();
  const normalizedFileTypes = useMemo(
    () => normalizeFileTypes(fileTypes),
    [fileTypes],
  );
  const normalizedBasePath = useMemo(() => normalizePath(basePath), [basePath]);

  const [browserOpen, setBrowserOpen] = useState(false);
  const [currentPath, setCurrentPath] = useState(normalizedBasePath);
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewPath, setPreviewPath] = useState("");
  const [preview, setPreview] = useState<FilePreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const loadDirectory = useCallback(
    async (path: string) => {
      setLoading(true);
      setError(null);
      try {
        const result = await listFiles(deviceinfo, path);
        setEntries(result);
      } catch (e) {
        setEntries([]);
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [deviceinfo],
  );

  const uploadTo = useCallback(
    async (file: File, directory: string): Promise<string | undefined> => {
      const targetPath = joinFilePath(directory, file.name);
      setUploading(true);
      try {
        await uploadFileReplace(deviceinfo, file, targetPath);
        toast.success(`Uploaded ${file.name}`);
        return targetPath;
      } catch (e) {
        toast.error(
          `Failed to upload ${file.name}: ${
            e instanceof Error ? e.message : String(e)
          }`,
        );
        return undefined;
      } finally {
        setUploading(false);
      }
    },
    [deviceinfo],
  );

  const loadPreview = useCallback(
    async (path: string) => {
      if (!path) return;
      setPreviewLoading(true);
      setPreviewError(null);
      try {
        setPreview(await readFile(deviceinfo, path));
      } catch (e) {
        setPreview(null);
        setPreviewError(e instanceof Error ? e.message : String(e));
      } finally {
        setPreviewLoading(false);
      }
    },
    [deviceinfo],
  );

  const openPreview = useCallback((path: string) => {
    if (!path) return;
    setPreviewPath(path);
    setPreview(null);
    setPreviewError(null);
    setPreviewOpen(true);
  }, []);

  const closePreview = useCallback(() => {
    setPreviewOpen(false);
  }, []);

  const acceptExtension = normalizedFileTypes.join(",") || undefined;

  const openBrowser = useCallback(() => {
    setCurrentPath(normalizedBasePath);
    setError(null);
    setBrowserOpen(true);
  }, [normalizedBasePath]);

  const closeBrowser = useCallback(() => {
    setBrowserOpen(false);
  }, []);

  const quickUploadPicker = useFilePicker(async (file) => {
    const targetPath = await uploadTo(file, normalizedBasePath);
    if (targetPath) onChange(targetPath);
  }, acceptExtension);

  const dialogUploadPicker = useFilePicker(async (file) => {
    const targetPath = await uploadTo(file, currentPath);
    if (targetPath) {
      onChange(targetPath);
      closeBrowser();
    }
  }, acceptExtension);

  useEffect(() => {
    if (browserOpen) {
      loadDirectory(currentPath);
    }
  }, [browserOpen, currentPath, loadDirectory]);

  useEffect(() => {
    if (previewOpen) {
      loadPreview(previewPath);
    }
  }, [previewOpen, previewPath, loadPreview]);

  const chooseFile = useCallback(
    (entry: FileEntry) => {
      onChange(entry.path);
      closeBrowser();
    },
    [closeBrowser, onChange],
  );

  const visibleEntries = entries.filter(
    (entry) => entry.isDir || matchesFileType(entry.name, normalizedFileTypes),
  );

  const canGoUp = normalizePath(currentPath) !== "";

  return (
    <div className="flex w-full flex-col gap-2">
      <Row className="w-full items-center" gap="gap-2">
        <Input
          value={value}
          readOnly
          placeholder="No file selected"
          className="min-w-0 flex-1 border-zinc-700 bg-zinc-800 font-mono text-sm"
          disabled={disabled}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={buttonClass}
          style={buttonStyle}
          onClick={openBrowser}
          disabled={disabled}
        >
          <FolderOpen />
          Browse
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={buttonClass}
          style={buttonStyle}
          onClick={quickUploadPicker.open}
          disabled={disabled || uploading}
        >
          {uploading ? <Loader2 className="animate-spin" /> : <Upload />}
          Upload
        </Button>
        {value ? (
          <>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={buttonClass}
              style={buttonStyle}
              onClick={() => openPreview(value)}
              disabled={disabled}
              aria-label="Preview selected file"
            >
              <Eye />
              View
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={buttonClass}
              style={buttonStyle}
              onClick={() => onChange("")}
              disabled={disabled}
              aria-label="Clear selected file"
            >
              <X />
            </Button>
          </>
        ) : null}
        {quickUploadPicker.input}
      </Row>

      <AlertDialog
        visible={browserOpen}
        onClose={closeBrowser}
        className="w-full max-w-2xl"
      >
        <Column gap="gap-3">
          <Row className="items-center justify-between" gap="gap-2">
            <div>
              <div className="text-lg font-semibold">Select a file</div>
              <div className="text-xs text-zinc-400 break-all">
                {currentPath || "/"}
              </div>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={buttonClass}
              style={buttonStyle}
              onClick={closeBrowser}
            >
              Cancel
            </Button>
          </Row>

          <Row className="items-center" gap="gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={buttonClass}
              style={buttonStyle}
              disabled={!canGoUp || loading}
              onClick={() => setCurrentPath(parentFilePath(currentPath))}
              aria-label="Go to parent directory"
            >
              <ChevronUp />
              Up
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={buttonClass}
              style={buttonStyle}
              disabled={loading}
              onClick={() => setCurrentPath(normalizedBasePath)}
            >
              <Home />
              Start folder
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={buttonClass}
              style={buttonStyle}
              disabled={uploading}
              onClick={dialogUploadPicker.open}
            >
              {uploading ? <Loader2 className="animate-spin" /> : <Upload />}
              Upload here
            </Button>
            {dialogUploadPicker.input}
          </Row>

          <div className="min-h-48 max-h-96 overflow-y-auto rounded-md border border-zinc-700">
            {loading ? (
              <div className="flex items-center justify-center gap-2 p-6 text-zinc-400">
                <Loader2 className="animate-spin" />
                Loading files...
              </div>
            ) : error ? (
              <div className="p-4 text-sm text-red-400">{error}</div>
            ) : visibleEntries.length === 0 ? (
              <div className="p-4 text-sm text-zinc-400">
                No matching files in this folder.
              </div>
            ) : (
              <ul className="divide-y divide-zinc-800">
                {visibleEntries.map((entry) => (
                  <li
                    key={entry.path}
                    className="flex items-center transition-colors hover:bg-zinc-800"
                  >
                    <button
                      type="button"
                      className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 px-3 py-2 text-left text-sm"
                      onClick={() => {
                        if (entry.isDir) {
                          setCurrentPath(entry.path);
                        } else {
                          chooseFile(entry);
                        }
                      }}
                    >
                      {entry.isDir ? (
                        <Folder className="text-amber-400" />
                      ) : (
                        <FileIcon className="text-zinc-400" />
                      )}
                      <span className="min-w-0 flex-1 truncate">
                        {entry.name}
                      </span>
                      {!entry.isDir ? (
                        <span className="shrink-0 text-xs text-zinc-500">
                          {formatFileSize(entry.size)}
                        </span>
                      ) : null}
                    </button>
                    {!entry.isDir ? (
                      <button
                        type="button"
                        className="mr-2 cursor-pointer rounded p-1 text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-white"
                        onClick={() => openPreview(entry.path)}
                        aria-label={`Preview ${entry.name}`}
                        title="Preview"
                      >
                        <Eye className="size-4" />
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Column>
      </AlertDialog>

      <AlertDialog
        visible={previewOpen}
        onClose={closePreview}
        className="w-full max-w-3xl"
      >
        <Column gap="gap-3">
          <Row className="items-center justify-between" gap="gap-2">
            <div className="min-w-0">
              <div className="truncate text-lg font-semibold">
                {preview?.name ?? fileNameFromPath(previewPath)}
              </div>
              <div className="text-xs text-zinc-400 break-all">
                {previewPath}
              </div>
            </div>
            <Row className="shrink-0 items-center" gap="gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className={buttonClass}
                style={buttonStyle}
                onClick={() => loadPreview(previewPath)}
                disabled={previewLoading}
              >
                <RefreshCw className={previewLoading ? "animate-spin" : ""} />
                Reload
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className={buttonClass}
                style={buttonStyle}
                onClick={closePreview}
              >
                Close
              </Button>
            </Row>
          </Row>

          <div className="flex min-h-48 max-h-[60vh] flex-col overflow-hidden rounded-md border border-zinc-700 bg-zinc-950">
            {previewLoading ? (
              <div className="flex flex-1 items-center justify-center gap-2 p-6 text-zinc-400">
                <Loader2 className="animate-spin" />
                Loading file...
              </div>
            ) : previewError ? (
              <div className="flex-1 overflow-auto whitespace-pre-wrap p-4 text-sm text-red-400">
                {previewError}
              </div>
            ) : !preview ? null : !preview.isText ? (
              <div className="flex flex-1 items-center justify-center p-6 text-sm text-zinc-400">
                This file is not text, so it can&apos;t be previewed.
              </div>
            ) : preview.content === "" ? (
              <div className="flex flex-1 items-center justify-center p-6 text-sm text-zinc-400">
                This file is empty.
              </div>
            ) : (
              <pre className="flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed whitespace-pre">
                {formatPreviewContent(preview)}
              </pre>
            )}
          </div>

          {preview ? (
            <div className="text-xs text-zinc-500">
              {formatFileSize(preview.size)}
              {preview.truncated
                ? ` — preview limited to the first ${formatFileSize(
                    preview.maxBytes,
                  )}`
                : ""}
            </div>
          ) : null}
        </Column>
      </AlertDialog>
    </div>
  );
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default FileSettingControl;
