"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useBackendContext } from "@/services/backend/backendContext";
import {
  FileEntry,
  joinFilePath,
  listFiles,
  parentFilePath,
  uploadFileReplace,
} from "@/services/backend/fileServer";
import { useFilePicker } from "@/services/useFilePicker";
import { AlertDialog } from "@/widgets/alertDialog";
import {
  ChevronUp,
  File as FileIcon,
  Folder,
  FolderOpen,
  Home,
  Loader2,
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
          className="min-w-0 flex-1"
          disabled={disabled}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
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
          onClick={quickUploadPicker.open}
          disabled={disabled || uploading}
        >
          {uploading ? <Loader2 className="animate-spin" /> : <Upload />}
          Upload
        </Button>
        {value ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onChange("")}
            disabled={disabled}
            aria-label="Clear selected file"
          >
            <X />
          </Button>
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
                  <li key={entry.path}>
                    <button
                      type="button"
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-zinc-800"
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
                  </li>
                ))}
              </ul>
            )}
          </div>
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
