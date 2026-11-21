"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, RotateCcw, X } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { PIPELINE_STEPS, STATUS_LABELS, stepState } from "@/lib/format";
import type { Project } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ProjectProgress({ project, live }: { project: Project; live: boolean }) {
  const queryClient = useQueryClient();
  const retry = useMutation({
    mutationFn: () => api.retryProject(project.id),
    onSuccess: (updated) => {
      queryClient.setQueryData(["project", project.id], updated);
      toast.success("Retrying. Finished steps will be skipped.");
    },
    onError: (err) => toast.error(err.message),
  });

  const failed = project.status === "failed";

  return (
    <Card>
      <CardContent className="flex flex-col gap-5">
        <ol className="grid grid-cols-5 gap-2">
          {PIPELINE_STEPS.map((step) => {
            const state = stepState(step, project.status, project.progress);
            return (
              <li key={step} className="flex flex-col items-center gap-2 text-center">
                <span
                  className={cn(
                    "grid size-8 place-items-center rounded-full border text-xs transition-colors",
                    state === "done" && "border-primary bg-primary text-primary-foreground",
                    state === "active" && "border-primary text-primary",
                    state === "failed" && "border-destructive bg-destructive/15 text-destructive",
                    state === "pending" && "border-border text-muted-foreground",
                  )}
                >
                  {state === "done" ? (
                    <Check className="size-4" />
                  ) : state === "active" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : state === "failed" ? (
                    <X className="size-4" />
                  ) : (
                    PIPELINE_STEPS.indexOf(step) + 1
                  )}
                </span>
                <span className={cn("text-xs", state === "pending" ? "text-muted-foreground" : "text-foreground")}>
                  {step === "ready" ? "Done" : STATUS_LABELS[step]}
                </span>
              </li>
            );
          })}
        </ol>

        {!failed && project.stalled && (
          <Alert>
            <AlertTitle>This looks stuck</AlertTitle>
            <AlertDescription>
              No progress for over 20 minutes. The worker may have restarted (for example after running out of memory).
              Retrying resumes from the last finished step.
            </AlertDescription>
            <AlertAction>
              <Button size="sm" variant="outline" onClick={() => retry.mutate()} disabled={retry.isPending}>
                {retry.isPending ? <Loader2 className="animate-spin" /> : <RotateCcw />} Retry
              </Button>
            </AlertAction>
          </Alert>
        )}

        {!failed && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{project.status_message || STATUS_LABELS[project.status]}</span>
              <span className="tabular-nums">{project.progress}%</span>
            </div>
            <Progress value={project.progress} />
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className={cn("size-1.5 rounded-full", live ? "bg-emerald-500" : "bg-muted-foreground")} />
              {live ? "Live updates" : "Connecting…"}
              {project.status === "transcribing" && " · Transcription runs locally on your machine and can take a while on CPU."}
            </p>
          </div>
        )}

        {failed && (
          <Alert variant="destructive">
            <AlertTitle>Processing failed</AlertTitle>
            <AlertDescription>{project.error || "Unknown error"}</AlertDescription>
            <AlertAction>
              <Button size="sm" variant="outline" onClick={() => retry.mutate()} disabled={retry.isPending}>
                {retry.isPending ? <Loader2 className="animate-spin" /> : <RotateCcw />} Retry
              </Button>
            </AlertAction>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
