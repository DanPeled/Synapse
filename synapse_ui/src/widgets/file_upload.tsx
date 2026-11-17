"use client";

import * as React from "react";
import { Upload, X } from "lucide-react";

type FileDropzoneProps = {
  value: File[];
  onChangeAction: (files: File[]) => void;

  maxFiles?: number;
  maxSize?: number; // bytes
  multiple?: boolean;

  className?: string;

  title?: string;
  description?: string;
};

export const FileDropzone: React.FC<FileDropzoneProps> = ({
  value,
  onChangeAction: onChange,
  maxFiles = 5,
  maxSize = undefined,
  multiple = true,
  className = "",
  title = "Drag & drop files here",
  description = "Click to browse",
}) => {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = React.useState(false);

  const validateFiles = (files: File[]) => {
    const valid: File[] = [];

    for (const file of files) {
      if (maxSize) {
        if (file.size > maxSize) continue;
      }
      if (value.length + valid.length >= maxFiles) break;
      valid.push(file);
    }

    return valid;
  };

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList) return;
    const incoming = Array.from(fileList);
    const valid = validateFiles(incoming);
    onChange([...value, ...valid]);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const removeFile = (index: number) => {
    const next = [...value];
    next.splice(index, 1);
    onChange(next);
  };

  return (
    <div className={`w-full max-w-md ${className}`}>
      {/* Dropzone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-xl border border-zinc-700 bg-zinc-900 p-6 text-center transition
          ${dragging ? "border-blue-500 bg-zinc-800" : "hover:bg-zinc-800"}
        `}
      >
        <div className="flex flex-col items-center gap-2">
          <div className="rounded-full border border-zinc-700 p-3">
            <Upload className="h-5 w-5 " color="#ff66c4" />
          </div>

          <p className="text-sm font-medium text-zinc-100">{title}</p>
          {maxSize && (
            <p className="text-xs text-zinc-400">
              {description} (max {maxFiles}, up to{" "}
              {Math.round(maxSize / 1024 / 1024)}MB)
            </p>
          )}
        </div>

        <input
          ref={inputRef}
          type="file"
          className="hidden"
          multiple={multiple}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* File list */}
      {value.length > 0 && (
        <div className="mt-4 space-y-2">
          {value.map((file, i) => (
            <div
              key={i}
              className="flex items-center justify-between rounded-lg bg-zinc-800 px-3 py-2"
            >
              <div className="flex items-center gap-3 overflow-hidden">
                <div className="h-8 w-8 flex-shrink-0 rounded bg-zinc-700 flex items-center justify-center text-xs text-zinc-300">
                  {file.type.startsWith("image") ? "IMG" : "FILE"}
                </div>

                <div className="truncate">
                  <p className="truncate text-sm text-zinc-200">{file.name}</p>
                  <p className="text-xs text-zinc-400">
                    {(file.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              </div>

              <button
                onClick={() => removeFile(i)}
                className="rounded-md p-1 text-zinc-400 hover:bg-zinc-700 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
