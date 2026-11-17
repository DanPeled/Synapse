import { useRef } from "react";

export function useFilePicker(onPick: (file: File) => void, accept?: string) {
  const ref = useRef<HTMLInputElement>(null);

  const open = () => ref.current?.click();

  const input = (
    <input
      ref={ref}
      type="file"
      hidden
      accept={accept}
      onChange={(e) => {
        const file = e.target.files?.[0];
        if (file) onPick(file);
        e.currentTarget.value = "";
      }}
    />
  );

  return { open, input };
}
