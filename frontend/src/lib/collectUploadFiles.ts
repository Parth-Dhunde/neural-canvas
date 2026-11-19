import { MAX_UPLOAD_FILES } from "@/lib/uploadLimits";
import { isSupportedImageFile } from "@/lib/uploadValidation";

/** Collect image files from drag-and-drop, including folder trees when supported. */
export async function collectFilesFromDataTransfer(dataTransfer: DataTransfer): Promise<File[]> {
  const items = dataTransfer.items;
  if (items && items.length > 0) {
    const entries: FileSystemEntry[] = [];
    for (const item of Array.from(items)) {
      const entry = item.webkitGetAsEntry?.();
      if (entry) {
        entries.push(entry);
      }
    }
    if (entries.length > 0) {
      const collected: File[] = [];
      for (const entry of entries) {
        await walkEntry(entry, collected);
        if (collected.length >= MAX_UPLOAD_FILES) {
          break;
        }
      }
      return collected.slice(0, MAX_UPLOAD_FILES);
    }
  }

  return Array.from(dataTransfer.files).slice(0, MAX_UPLOAD_FILES);
}

async function walkEntry(entry: FileSystemEntry, output: File[]): Promise<void> {
  if (output.length >= MAX_UPLOAD_FILES) {
    return;
  }

  if (entry.isFile) {
    const file = await readFileEntry(entry as FileSystemFileEntry);
    if (file && isSupportedImageFile(file)) {
      output.push(file);
    }
    return;
  }

  if (!entry.isDirectory) {
    return;
  }

  const directory = entry as FileSystemDirectoryEntry;
  const children = await readDirectoryEntries(directory);
  for (const child of children) {
    await walkEntry(child, output);
    if (output.length >= MAX_UPLOAD_FILES) {
      return;
    }
  }
}

function readFileEntry(entry: FileSystemFileEntry): Promise<File | null> {
  return new Promise((resolve) => {
    entry.file(
      (file) => resolve(file),
      () => resolve(null),
    );
  });
}

function readDirectoryEntries(directory: FileSystemDirectoryEntry): Promise<FileSystemEntry[]> {
  return new Promise((resolve) => {
    const reader = directory.createReader();
    const entries: FileSystemEntry[] = [];

    const readBatch = () => {
      reader.readEntries(
        (batch) => {
          if (batch.length === 0) {
            resolve(entries);
            return;
          }
          entries.push(...batch);
          readBatch();
        },
        () => resolve(entries),
      );
    };

    readBatch();
  });
}
