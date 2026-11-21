/**
 * PUT a file straight to S3-compatible storage with a presigned URL. Uses XMLHttpRequest because
 * fetch() still can't report upload progress.
 */
export function uploadWithProgress(
  url: string,
  file: File,
  contentType: string,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    // Must match the Content-Type the URL was signed with
    xhr.setRequestHeader("Content-Type", contentType);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new Error(`Upload failed (HTTP ${xhr.status}). Check that storage is reachable.`));
    xhr.onerror = () => reject(new Error("Upload failed: couldn't reach storage. Is the s3 container running on port 9000?"));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    signal?.addEventListener("abort", () => xhr.abort());
    xhr.send(file);
  });
}

export const ACCEPTED_VIDEO = ".mp4,.mov,.mkv,.webm,.m4v,.avi,video/*";
