"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArrowLeft, ExternalLink, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { ClipCard } from "@/components/clip-card";
import { ProjectProgress } from "@/components/project-progress";
import { StatusBadge } from "@/components/status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import { TERMINAL_STATUSES } from "@/lib/types";
import { useProjectEvents } from "@/lib/use-project-events";

export function ProjectView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const project = useQuery({
    queryKey: ["project", id],
    queryFn: () => api.getProject(id),
    // SSE delivers live progress; this slow refetch also catches stalls (no events at all)
    refetchInterval: (q) => (q.state.data && !TERMINAL_STATUSES.has(q.state.data.status) ? 60_000 : false),
  });
  const processing = project.data ? !TERMINAL_STATUSES.has(project.data.status) : false;
  const live = useProjectEvents(id, processing);

  const clips = useQuery({
    queryKey: ["clips", id],
    queryFn: () => api.listClips(id),
    enabled: project.data?.status === "ready",
    // refresh while any clip is re-rendering from the editor
    refetchInterval: (q) => (q.state.data?.some((c) => c.status === "rendering") ? 3000 : false),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteProject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project deleted");
      router.replace("/");
    },
    onError: (err) => toast.error(err.message),
  });

  if (project.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (project.error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{project.error.message}</AlertDescription>
      </Alert>
    );
  }

  const p = project.data;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <Link href="/" className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> All projects
        </Link>
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-semibold tracking-tight text-balance">
              {p.title || (p.source_type === "youtube" ? "YouTube video" : "Uploaded video")}
            </h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground [&>*+*]:before:mr-2 [&>*+*]:before:content-['·']">
              {p.duration != null && <span>{formatDuration(p.duration)}</span>}
              {p.language && <span>{p.language.toUpperCase()}</span>}
              {p.source_url && (
                <a href={p.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-foreground">
                  Source <ExternalLink className="size-3" />
                </a>
              )}
            </p>
            {p.instruction && <p className="mt-2 text-sm">Instruction: <span className="text-muted-foreground">“{p.instruction}”</span></p>}
          </div>
          <StatusBadge status={p.status} />
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Delete project"
            onClick={() => {
              if (confirm("Delete this project and all its clips? This can't be undone.")) remove.mutate();
            }}
          >
            <Trash2 />
          </Button>
        </div>
      </div>

      {p.status !== "ready" && <ProjectProgress project={p} live={live} />}

      {p.status === "ready" && (
        <section className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">
              {clips.data ? `${clips.data.length} clips` : "Clips"}{" "}
              <span className="text-sm font-normal text-muted-foreground">sorted by virality score</span>
            </h2>
            {clips.data && clips.data.some((c) => c.video_url) && (
              <a href={api.zipUrl(id)} className={buttonVariants({ variant: "outline", size: "sm" })}>
                <Archive /> Download all (.zip)
              </a>
            )}
          </div>
          {clips.isPending ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="aspect-[9/16] w-full" />
              ))}
            </div>
          ) : clips.error ? (
            <Alert variant="destructive">
              <AlertDescription>{clips.error.message}</AlertDescription>
            </Alert>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {clips.data.map((clip, i) => (
                <ClipCard key={clip.id} clip={clip} rank={i + 1} />
              ))}
            </div>
          )}
        </section>
      )}

    </div>
  );
}
