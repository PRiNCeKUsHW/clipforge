"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Upload } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { composeDescription } from "@/components/editor/publish-panel";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import type { Clip, PublishJob, SocialAccount } from "@/lib/types";
import { cn } from "@/lib/utils";

const PLATFORM_LABEL = { youtube: "YouTube Shorts", instagram: "Instagram Reels" } as const;
const VISIBILITY = [
  { id: "private", label: "Private" },
  { id: "unlisted", label: "Unlisted" },
  { id: "public", label: "Public" },
] as const;

/** A clip already has (or is getting) an upload on this account, so uploading again would duplicate it. */
export function alreadyUploaded(jobs: PublishJob[], accountId: string): boolean {
  return jobs.some((j) => j.social_account_id === accountId && j.status !== "failed");
}

const choice = (active: boolean) =>
  cn(
    "rounded-lg border px-3 py-1.5 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
    active ? "border-primary bg-primary/10" : "border-border hover:border-primary/50",
  );

/**
 * Upload one clip (from its card) or every ready clip (from the project page) to a connected account,
 * using each clip's own title, description and hashtags.
 */
export function UploadDialog({
  clips,
  open,
  onOpenChange,
}: {
  clips: Clip[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.listAccounts, enabled: open });
  const [accountId, setAccountId] = useState<string | null>(null);
  const [privacy, setPrivacy] = useState("private");

  const ready = clips.filter((c) => c.status === "ready" && c.video_url);
  const single = clips.length === 1;
  const account: SocialAccount | undefined = accounts.data?.find((a) => a.id === (accountId ?? accounts.data?.[0]?.id));

  const upload = useMutation({
    mutationFn: async () => {
      const acc = account!;
      let started = 0;
      let skipped = 0;
      const failed: string[] = [];
      for (const clip of ready) {
        try {
          // check per clip right before uploading, so a second click can't post duplicates
          const jobs = await api.listPublishJobs(clip.id);
          if (alreadyUploaded(jobs, acc.id)) {
            skipped++;
            continue;
          }
          await api.publishClip(clip.id, {
            social_account_id: acc.id,
            title: clip.hook_title,
            description: composeDescription(clip.description, clip.hashtags),
            privacy_status: privacy,
          });
          started++;
        } catch (err) {
          failed.push(`${clip.hook_title}: ${err instanceof Error ? err.message : "failed"}`);
        } finally {
          queryClient.invalidateQueries({ queryKey: ["publish-jobs", clip.id] });
        }
      }
      return { started, skipped, failed, platform: acc.platform };
    },
    onSuccess: ({ started, skipped, failed, platform }) => {
      if (started) toast.success(`Uploading ${started} clip${started > 1 ? "s" : ""} to ${PLATFORM_LABEL[platform]}…`);
      if (skipped) toast.info(`${skipped} clip${skipped > 1 ? "s were" : " was"} already uploaded to this account, skipped.`);
      failed.forEach((f) => toast.error(f));
      if (!failed.length) onOpenChange(false);
    },
  });

  const title = single ? "Upload clip" : `Upload all ${ready.length} clips`;
  const notReady = clips.length - ready.length;

  return (
    <Dialog open={open} onOpenChange={(o) => !upload.isPending && onOpenChange(o)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {single
              ? `“${clips[0]?.hook_title}” with its title, description and hashtags.`
              : "Each clip goes up with its own title, description and hashtags. Clips already uploaded to the account are skipped."}
            {notReady > 0 && !single && ` ${notReady} clip${notReady > 1 ? "s aren't" : " isn't"} rendered yet and won't be uploaded.`}
          </DialogDescription>
        </DialogHeader>

        {accounts.isPending ? (
          <p className="text-muted-foreground">Loading connected accounts…</p>
        ) : accounts.isError ? (
          <p className="text-destructive">Couldn&apos;t load your connected accounts ({accounts.error.message}).</p>
        ) : accounts.data.length === 0 ? (
          <p>
            No connected accounts yet.{" "}
            <Link href="/accounts" className="text-primary underline-offset-4 hover:underline">
              Connect YouTube or Instagram
            </Link>{" "}
            first.
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="grid gap-2">
              <Label>Account</Label>
              <div className="flex flex-wrap gap-2">
                {accounts.data.map((a) => (
                  <button key={a.id} type="button" onClick={() => setAccountId(a.id)} className={choice(account?.id === a.id)}>
                    {PLATFORM_LABEL[a.platform]} · {a.display_name}
                  </button>
                ))}
              </div>
            </div>
            {account?.platform === "youtube" && (
              <div className="grid gap-2">
                <Label>Visibility</Label>
                <div className="flex gap-2">
                  {VISIBILITY.map((v) => (
                    <button key={v.id} type="button" onClick={() => setPrivacy(v.id)} className={choice(privacy === v.id)}>
                      {v.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button
            onClick={() => upload.mutate()}
            disabled={!account || ready.length === 0 || upload.isPending}
            className="rounded-full font-semibold"
          >
            {upload.isPending ? <Loader2 className="animate-spin" /> : <Upload />}
            {single ? "Upload" : `Upload ${ready.length}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
