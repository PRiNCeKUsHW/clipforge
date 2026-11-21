"use client";

import { Loader2, Save } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ClipDetail, ClipUpdate } from "@/lib/types";

export const parseHashtags = (raw: string) =>
  raw
    .split(/[\s,]+/)
    .map((t) => t.replace(/^#+/, "").trim())
    .filter(Boolean);

export function DetailsPanel({ clip, saving, onSave }: { clip: ClipDetail; saving: boolean; onSave: (u: ClipUpdate) => void }) {
  const [title, setTitle] = useState(clip.hook_title);
  const [description, setDescription] = useState(clip.description ?? "");
  const [tags, setTags] = useState(clip.hashtags.map((t) => `#${t}`).join(" "));

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-2">
        <Label htmlFor="title">Hook title</Label>
        <Input id="title" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
        <p className="text-xs text-muted-foreground">Used as the post title when publishing.</p>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="desc">Description</Label>
        <Textarea id="desc" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="tags">Hashtags</Label>
        <Input id="tags" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="#shorts #python" />
      </div>
      <Button
        className="self-start"
        disabled={saving || !title.trim()}
        onClick={() => onSave({ hook_title: title, description, hashtags: parseHashtags(tags) })}
      >
        {saving ? <Loader2 className="animate-spin" /> : <Save />} Save details
      </Button>
    </div>
  );
}
