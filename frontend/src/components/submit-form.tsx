"use client";

import { useQueryClient } from "@tanstack/react-query";
import { FileVideo, LayoutTemplate, Link2, Loader2, Sparkles, Upload, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, type DragEvent, type FormEvent } from "react";
import { toast } from "sonner";

import { CAPTION_STYLES, StylePicker } from "@/components/editor/style-picker";
import { CaptionsToggle, LayoutPicker } from "@/components/layout-picker";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { ACCEPTED_VIDEO, uploadWithProgress } from "@/lib/upload";
import type { LayoutId } from "@/lib/layouts";
import { isYouTubeUrl } from "@/lib/youtube";

const EXAMPLES = ["only funny moments", "clips about Python tips", "the most controversial takes"];

export function SubmitForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<"link" | "upload">("link");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [instruction, setInstruction] = useState("");
  const [layout, setLayout] = useState<LayoutId>("auto");
  const [captions, setCaptions] = useState(true);
  const [captionStyle, setCaptionStyle] = useState("bold");
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const urlInvalid = tab === "link" && url.trim() !== "" && !isYouTubeUrl(url);
  const canSubmit = !busy && (tab === "link" ? isYouTubeUrl(url) : file !== null);

  function pickFile(f: File | undefined | null) {
    if (!f) return;
    if (!f.type.startsWith("video/") && !/\.(mp4|mov|mkv|webm|m4v|avi)$/i.test(f.name)) {
      setError("That doesn't look like a video file.");
      return;
    }
    setError(null);
    setFile(f);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files?.[0]);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      let project;
      const extra = {
        ...(instruction.trim() ? { instruction: instruction.trim() } : {}),
        layout,
        caption_style: captions ? captionStyle : "none",
      };
      if (tab === "link") {
        project = await api.createProject({ source_type: "youtube", source_url: url.trim(), ...extra });
      } else {
        const f = file!;
        const presign = await api.presignUpload(f);
        setUploadProgress(0);
        await uploadWithProgress(presign.upload_url, f, presign.content_type, setUploadProgress);
        project = await api.createProject({ source_type: "upload", storage_key: presign.storage_key, ...extra });
      }
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project created. Processing has started.");
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setUploadProgress(null);
      setBusy(false);
    }
  }

  return (
    <Card className="rounded-[1.75rem] border-border/70 bg-card/95 py-5 shadow-[0_30px_70px_-34px_oklch(0.45_0.12_40/0.45)] sm:py-6">
      <CardContent className="sm:px-7">
        <form onSubmit={onSubmit} className="flex flex-col gap-5">
          <Tabs value={tab} onValueChange={(v) => setTab(v as "link" | "upload")}>
            <TabsList className="rounded-full p-1">
              <TabsTrigger value="link" className="rounded-full px-3">
                <Link2 /> YouTube link
              </TabsTrigger>
              <TabsTrigger value="upload" className="rounded-full px-3">
                <Upload /> Upload file
              </TabsTrigger>
            </TabsList>

            <TabsContent value="link" className="pt-3">
              <Label htmlFor="url" className="sr-only">
                YouTube URL
              </Label>
              <Input
                id="url"
                placeholder="https://www.youtube.com/watch?v=..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                aria-invalid={urlInvalid}
                className="h-13 rounded-2xl bg-background px-4 text-base md:text-base"
                autoFocus
              />
              {urlInvalid && <p className="mt-2 text-sm text-destructive">Paste a YouTube video link (watch, youtu.be or shorts).</p>}
            </TabsContent>

            <TabsContent value="upload" className="pt-3">
              <input
                ref={fileInput}
                type="file"
                accept={ACCEPTED_VIDEO}
                className="hidden"
                onChange={(e) => pickFile(e.target.files?.[0])}
              />
              {file ? (
                <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/40 p-3">
                  <FileVideo className="size-5 shrink-0 text-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{file.name}</p>
                    <p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p>
                  </div>
                  {!busy && (
                    <Button type="button" variant="ghost" size="icon-sm" onClick={() => setFile(null)} aria-label="Remove file">
                      <X />
                    </Button>
                  )}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => fileInput.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={onDrop}
                  className={`flex w-full flex-col items-center gap-2 rounded-2xl border-2 border-dashed bg-background px-4 py-10 text-sm text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground ${dragging ? "border-primary bg-primary/5 text-foreground" : "border-border"}`}
                >
                  <Upload className="size-6" />
                  <span>
                    <span className="font-medium text-foreground">Click to choose</span> or drag a video here
                  </span>
                  <span className="text-xs">MP4, MOV, MKV or WebM</span>
                </button>
              )}
              {uploadProgress !== null && (
                <div className="mt-3 flex items-center gap-3">
                  <Progress value={Math.round(uploadProgress * 100)} className="flex-1" />
                  <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">
                    {Math.round(uploadProgress * 100)}%
                  </span>
                </div>
              )}
            </TabsContent>
          </Tabs>

          <div className="grid gap-2">
            <Label htmlFor="instruction" className="flex items-center gap-1.5">
              <Sparkles className="size-3.5 text-primary" /> What should the clips be about? <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Textarea
              id="instruction"
              maxLength={500}
              rows={2}
              placeholder={`e.g. "${EXAMPLES[0]}"`}
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
            />
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => setInstruction(ex)}
                  className="rounded-full bg-secondary px-3 py-1 text-xs text-secondary-foreground transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-3 rounded-2xl bg-secondary/60 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Label className="flex items-center gap-1.5">
                <LayoutTemplate className="size-3.5 text-primary" /> Clip style
              </Label>
              <CaptionsToggle on={captions} onChange={setCaptions} />
            </div>
            <LayoutPicker value={layout} onChange={setLayout} compact />
            {captions && (
              <details className="group">
                <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                  Caption style: <span className="font-medium text-foreground">{CAPTION_STYLES.find((c) => c.id === captionStyle)?.label}</span> (change)
                </summary>
                <div className="pt-3">
                  <StylePicker hideNone value={captionStyle} onChange={setCaptionStyle} />
                </div>
              </details>
            )}
            <p className="text-xs text-muted-foreground">Applies to every clip. You can still change each clip later in the editor.</p>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Button type="submit" size="lg" className="h-13 rounded-full text-base font-semibold shadow-[0_10px_24px_-12px_oklch(0.6_0.15_55/0.8)]" disabled={!canSubmit}>
            {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}
            {busy ? (uploadProgress !== null && uploadProgress < 1 ? "Uploading…" : "Starting…") : "Generate clips"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
