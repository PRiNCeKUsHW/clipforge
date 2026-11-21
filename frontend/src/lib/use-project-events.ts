"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "./api";
import { parseProgressEvent } from "./format";
import { TERMINAL_STATUSES, type Project } from "./types";

/**
 * Subscribe to a project's Server-Sent Events and merge each update into the
 * TanStack Query cache, so every component showing the project re-renders live.
 */
export function useProjectEvents(projectId: string, enabled: boolean) {
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    // EventSource is the browser's built-in SSE client; withCredentials sends the auth cookie.
    const source = new EventSource(api.eventsUrl(projectId), { withCredentials: true });
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false); // EventSource retries automatically

    source.addEventListener("progress", (e) => {
      const event = parseProgressEvent((e as MessageEvent<string>).data);
      if (!event) return;
      queryClient.setQueryData<Project>(["project", projectId], (old) =>
        old ? { ...old, status: event.status, progress: event.progress, status_message: event.status_message, error: event.error } : old,
      );
      if (TERMINAL_STATUSES.has(event.status)) {
        source.close();
        setConnected(false);
        queryClient.invalidateQueries({ queryKey: ["project", projectId] });
        queryClient.invalidateQueries({ queryKey: ["clips", projectId] });
        queryClient.invalidateQueries({ queryKey: ["projects"] });
      }
    });

    return () => source.close();
  }, [projectId, enabled, queryClient]);

  return connected;
}
