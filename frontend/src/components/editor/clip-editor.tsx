"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, Loader2, RefreshCw, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { DetailsPanel } from "@/components/editor/details-panel";
import { CaptionsToggle, LayoutPicker } from "@/components/layout-picker";
import { PublishPanel } from "@/components/editor/publish-panel";
import { StylePicker } from "@/components/editor/style-picker";
import { TrimPanel } from "@/components/editor/trim-panel";
import { WordEditor } from "@/components/editor/word-editor";
import { Alert, AlertAction, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import { captionsOn, layoutLabel } from "@/lib/layouts";
import type { ClipDetail, ClipUpdate } from "@/lib/types";


export function ClipEditor() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [needsRender, setNeedsRender] = useState(false);

  const clip = useQuery({
    queryKey: ["clip", id],
    queryFn: () => api.getClip(id),
    refetchInterval: (q) => (q.state.data?.status === "rendering" ? 2000 : false),
  });

  const setClip = (data: ClipDetail) => {
    queryClient.setQueryData(["clip", id], data);
    queryClient.invalidateQueries({ queryKey: ["clips", data.project_id] });
  };

  const save = useMutation({
    mutationFn: (u: ClipUpdate) => api.updateClip(id, u),
    onSuccess: (data) => {
      setClip(data);
      setNeedsRender(true);
      toast.success("Saved. Re-render to update the video.");
    },
    onError: (err) => toast.error(err.message),
  });

  const render = useMutation({
    mutationFn: () => api.renderClip(id),
    onSuccess: (data) => {
      setClip(data);
      setNeedsRender(false);
    },
    onError: (err) => toast.error(err.message),
  });

  async function download() {
    try {
      window.location.assign((await api.downloadClip(id)).url);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Download failed");
    }
  }

  if (clip.isPending) return <Skeleton className="h-[600px] w-full" />;
  if (clip.error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{clip.error.message}</AlertDescription>
      </Alert>
    );
  }

  const c = clip.data;
  const rendering = c.status === "rendering";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link href={`/projects/${c.project_id}`} className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> {c.project_title || "Back to project"}
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{c.hook_title}</h1>
          <Badge variant="secondary">Score {c.virality_score}</Badge>
          <Badge variant="outline">{layoutLabel(c.layout)}</Badge>
          {!captionsOn(c.caption_style) && <Badge variant="outline">No captions</Badge>}
        </div>
        <p className="text-sm text-muted-foreground">
          {formatDuration(c.start)} – {formatDuration(c.end)} in source · {c.duration.toFixed(1)}s
        </p>
      </div>

      {needsRender && !rendering && (
        <Alert>
          <AlertDescription>Your changes are saved. Re-render to see them in the video.</AlertDescription>
          <AlertAction>
            <Button size="sm" onClick={() => render.mutate()} disabled={render.isPending}>
              <RefreshCw /> Re-render
            </Button>
          </AlertAction>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,340px)_1fr]">
        {/* Preview */}
        <div className="flex flex-col gap-3">
          <div className="relative mx-auto aspect-[9/16] w-full max-w-[340px] overflow-hidden rounded-xl bg-black">
            {c.video_url && !rendering ? (
              <video key={c.updated_at} src={c.video_url} poster={c.thumbnail_url ?? undefined} controls playsInline className="size-full object-contain" />
            ) : (
              <div className="grid size-full place-items-center p-6 text-center text-sm text-muted-foreground">
                {rendering ? (
                  <div className="flex w-full flex-col items-center gap-3">
                    <Loader2 className="size-6 animate-spin" />
                    <span>Rendering… {c.progress}%</span>
                    <Progress value={c.progress} className="w-full" />
                  </div>
                ) : c.status === "failed" ? (
                  <span className="flex flex-col items-center gap-2 text-destructive">
                    <TriangleAlert className="size-5" /> {c.error || "Render failed"}
                  </span>
                ) : (
                  "Not rendered yet"
                )}
              </div>
            )}
          </div>
          <div className="mx-auto flex w-full max-w-[340px] gap-2">
            <Button className="flex-1" onClick={() => render.mutate()} disabled={rendering || render.isPending}>
              {rendering || render.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />} Re-render
            </Button>
            <Button variant="outline" onClick={download} disabled={!c.video_url || rendering}>
              <Download /> MP4
            </Button>
          </div>
        </div>

        {/* Controls */}
        <Card>
          <CardContent>
            <Tabs defaultValue="layout">
              <TabsList>
                <TabsTrigger value="layout">Layout</TabsTrigger>
                <TabsTrigger value="captions">Captions</TabsTrigger>
                <TabsTrigger value="trim">Trim</TabsTrigger>
                <TabsTrigger value="details">Details</TabsTrigger>
                <TabsTrigger value="publish">Publish</TabsTrigger>
              </TabsList>

              <TabsContent value="layout" className="flex flex-col gap-6 pt-4">
                <section className="flex flex-col gap-2">
                  <h3 className="text-sm font-medium">Clip layout</h3>
                  <LayoutPicker
                    value={c.layout}
                    onChange={(layout) => layout !== c.layout && save.mutate({ layout })}
                  />
                </section>
                <section className="flex flex-col gap-2">
                  <h3 className="text-sm font-medium">Captions</h3>
                  <CaptionsToggle
                    on={captionsOn(c.caption_style)}
                    onChange={(on) => save.mutate({ caption_style: on ? "bold" : "none" })}
                  />
                </section>
              </TabsContent>

              <TabsContent value="captions" className="flex flex-col gap-6 pt-4">
                {captionsOn(c.caption_style) ? (
                  <section className="flex flex-col gap-2">
                    <h3 className="text-sm font-medium">Caption style</h3>
                    <StylePicker
                      hideNone
                      value={c.caption_style}
                      onChange={(style) => style !== c.caption_style && save.mutate({ caption_style: style })}
                    />
                  </section>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Captions are off for this clip. Turn them on in the Layout tab to choose a style.
                  </p>
                )}
                <section className="flex flex-col gap-2">
                  <h3 className="text-sm font-medium">Caption text</h3>
                  {/* key: reset local edits when the server copy changes (e.g. after a trim) */}
                  <WordEditor
                    key={c.updated_at}
                    words={c.transcript_words}
                    clipStart={c.start}
                    saving={save.isPending}
                    onSave={(texts) => save.mutate({ word_texts: texts })}
                  />
                </section>
              </TabsContent>

              <TabsContent value="trim" className="pt-4">
                <TrimPanel
                  key={`${c.start}-${c.end}`}
                  sourceUrl={c.source_url}
                  start={c.start}
                  end={c.end}
                  maxDuration={c.project_duration}
                  saving={save.isPending}
                  onSave={(start, end) => save.mutate({ start, end })}
                />
              </TabsContent>

              <TabsContent value="details" className="pt-4">
                <DetailsPanel key={c.updated_at} clip={c} saving={save.isPending} onSave={(u) => save.mutate(u)} />
              </TabsContent>

              <TabsContent value="publish" className="pt-4">
                <PublishPanel clip={c} />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
