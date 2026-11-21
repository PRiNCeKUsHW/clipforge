"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, Loader2, Send, XCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { ClipDetail, PublishJob } from "@/lib/types";
import { cn } from "@/lib/utils";

const PLATFORM_LABEL = { youtube: "YouTube Shorts", instagram: "Instagram Reels" } as const;

export function composeDescription(description: string | null, hashtags: string[]): string {
  const tags = hashtags.map((t) => `#${t}`).join(" ");
  return [description?.trim(), tags].filter(Boolean).join("\n\n");
}

function JobRow({ job }: { job: PublishJob }) {
  const busy = job.status === "queued" || job.status === "uploading";
  return (
    <li className="flex items-start gap-3 rounded-md border border-border p-3 text-sm">
      {busy ? (
        <Loader2 className="mt-0.5 size-4 animate-spin text-muted-foreground" />
      ) : job.status === "published" ? (
        <CheckCircle2 className="mt-0.5 size-4 text-emerald-500" />
      ) : (
        <XCircle className="mt-0.5 size-4 text-destructive" />
      )}
      <div className="min-w-0 flex-1">
        <p className="font-medium">
          {PLATFORM_LABEL[job.platform]} <span className="font-normal text-muted-foreground">· {job.status}</span>
          {job.privacy_status && job.platform === "youtube" && <Badge variant="outline" className="ml-2">{job.privacy_status}</Badge>}
        </p>
        <p className="truncate text-xs text-muted-foreground">{job.title}</p>
        {job.error && <p className="mt-1 text-xs text-destructive">{job.error}</p>}
      </div>
      {job.external_url && (
        <a href={job.external_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-xs text-primary hover:underline">
          View <ExternalLink className="size-3" />
        </a>
      )}
    </li>
  );
}

export function PublishPanel({ clip }: { clip: ClipDetail }) {
  const queryClient = useQueryClient();
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.listAccounts });
  const jobs = useQuery({
    queryKey: ["publish-jobs", clip.id],
    queryFn: () => api.listPublishJobs(clip.id),
    refetchInterval: (q) => (q.state.data?.some((j) => j.status === "queued" || j.status === "uploading") ? 3000 : false),
  });
  const [accountId, setAccountId] = useState<string | null>(null);
  const [title, setTitle] = useState(clip.hook_title);
  const [description, setDescription] = useState(composeDescription(clip.description, clip.hashtags));
  const [privacy, setPrivacy] = useState("private");

  const selected = accounts.data?.find((a) => a.id === (accountId ?? accounts.data?.[0]?.id));
  const publish = useMutation({
    mutationFn: () =>
      api.publishClip(clip.id, { social_account_id: selected!.id, title, description, privacy_status: privacy }),
    onSuccess: () => {
      toast.success(`Publishing to ${PLATFORM_LABEL[selected!.platform]}…`);
      queryClient.invalidateQueries({ queryKey: ["publish-jobs", clip.id] });
    },
    onError: (err) => toast.error(err.message),
  });

  if (clip.status !== "ready") {
    return <p className="text-sm text-muted-foreground">Render the clip first, then publish it here.</p>;
  }
  if (accounts.data && accounts.data.length === 0) {
    return (
      <Alert>
        <AlertDescription>
          No connected accounts yet.{" "}
          <Link href="/accounts" className="text-primary underline-offset-4 hover:underline">
            Connect YouTube or Instagram
          </Link>{" "}
          to publish directly.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-2">
        <Label>Account</Label>
        <div className="flex flex-wrap gap-2">
          {accounts.data?.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => setAccountId(a.id)}
              className={cn(
                "rounded-md border px-3 py-1.5 text-sm",
                selected?.id === a.id ? "border-primary bg-primary/10" : "border-border hover:border-primary/50",
              )}
            >
              {PLATFORM_LABEL[a.platform]} · {a.display_name}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="ptitle">Title</Label>
        <Input id="ptitle" value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} />
        {selected?.platform === "youtube" && <p className="text-xs text-muted-foreground">#Shorts is added automatically.</p>}
      </div>
      <div className="grid gap-2">
        <Label htmlFor="pdesc">{selected?.platform === "instagram" ? "Caption" : "Description"}</Label>
        <Textarea id="pdesc" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      {selected?.platform === "youtube" && (
        <div className="grid gap-2">
          <Label>Visibility</Label>
          <div className="flex gap-2">
            {["private", "unlisted", "public"].map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPrivacy(p)}
                className={cn(
                  "rounded-md border px-3 py-1 text-sm capitalize",
                  privacy === p ? "border-primary bg-primary/10" : "border-border hover:border-primary/50",
                )}
              >
                {p}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Unverified Google Cloud projects can only upload private videos until the app passes Google&apos;s audit.
          </p>
        </div>
      )}
      <Button className="self-start" onClick={() => publish.mutate()} disabled={!selected || !title.trim() || publish.isPending}>
        {publish.isPending ? <Loader2 className="animate-spin" /> : <Send />} Publish
      </Button>

      {jobs.data && jobs.data.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">History</h3>
          <ul className="flex flex-col gap-2">
            {jobs.data.map((j) => (
              <JobRow key={j.id} job={j} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
