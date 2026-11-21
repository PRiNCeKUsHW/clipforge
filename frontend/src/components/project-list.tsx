"use client";

import { useQuery } from "@tanstack/react-query";
import { Film, MonitorPlay } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import { TERMINAL_STATUSES } from "@/lib/types";

export function ProjectList() {
  const { data, isPending, error } = useQuery({
    queryKey: ["projects"],
    queryFn: api.listProjects,
    // light polling while anything is still processing (each project page also has live SSE)
    refetchInterval: (q) => (q.state.data?.some((p) => !TERMINAL_STATUSES.has(p.status)) ? 5000 : false),
  });

  if (isPending) {
    return (
      <div className="grid gap-2">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }
  if (error) return <p className="text-sm text-destructive">{error.message}</p>;
  if (data.length === 0) {
    return <p className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">No projects yet. Paste a link above to get started.</p>;
  }

  return (
    <ul className="grid gap-2">
      {data.map((p) => {
        const busy = !TERMINAL_STATUSES.has(p.status);
        return (
          <li key={p.id}>
            <Link
              href={`/projects/${p.id}`}
              className="flex items-center gap-4 rounded-lg border border-border bg-card px-4 py-3 transition-colors hover:border-primary/50"
            >
              {p.source_type === "youtube" ? (
                <MonitorPlay className="size-5 shrink-0 text-muted-foreground" />
              ) : (
                <Film className="size-5 shrink-0 text-muted-foreground" />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{p.title || p.source_url || "Untitled video"}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(p.created_at).toLocaleString()} · {formatDuration(p.duration)}
                  {p.status === "ready" && ` · ${p.clip_count} clips`}
                </p>
                {busy && <Progress value={p.progress} className="mt-2 max-w-xs" />}
              </div>
              <StatusBadge status={p.status} />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
