import { useCallback, useState } from "react";
import type { Attachment } from "../api/types";

export const ACCEPT = ".txt,.md,.markdown,.rst,.csv,.tsv,.json,.yaml,.yml,.xml,.html,.puml,.plantuml,.py,.js,.ts,.tsx,.java,.sql,.toml,.pdf,.docx";
export const MAX_BYTES = 5 * 1024 * 1024; // same limit as the backend (orchestrator.MAX_ATTACHMENT_BYTES)

export interface PendingFile {
  key: string;
  name: string;
  size: number;
  status: "uploading" | "ready" | "error";
  attachment?: Attachment;
  error?: string;
}

export const formatSize = (bytes: number) =>
  bytes < 1024 ? `${bytes} B` : bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

let counter = 0;

/** Files attached to the next message: uploaded right away (like a chat app), sent as ids with the message. */
export function usePendingFiles(upload: (file: File) => Promise<Attachment>) {
  const [files, setFiles] = useState<PendingFile[]>([]);

  const add = useCallback(
    (list: File[]) => {
      for (const file of list) {
        const key = `f${++counter}`;
        const base = { key, name: file.name, size: file.size };
        if (file.size > MAX_BYTES) {
          setFiles((fs) => [...fs, { ...base, status: "error", error: "larger than 5 MB" }]);
          continue;
        }
        setFiles((fs) => [...fs, { ...base, status: "uploading" }]);
        upload(file).then(
          (attachment) => setFiles((fs) => fs.map((f) => (f.key === key ? { ...f, status: "ready", attachment } : f))),
          (err: unknown) =>
            setFiles((fs) => fs.map((f) => (f.key === key ? { ...f, status: "error", error: err instanceof Error ? err.message : String(err) } : f))),
        );
      }
    },
    [upload],
  );

  const remove = (key: string) => setFiles((fs) => fs.filter((f) => f.key !== key));
  const clear = () => setFiles([]);
  const ids = files.filter((f) => f.status === "ready").map((f) => f.attachment!.id);
  const uploading = files.some((f) => f.status === "uploading");
  return { files, add, remove, clear, ids, uploading };
}
