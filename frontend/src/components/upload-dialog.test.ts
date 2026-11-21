import { describe, expect, it } from "vitest";

import { alreadyUploaded } from "@/components/upload-dialog";
import type { PublishJob } from "@/lib/types";

const job = (account: string, status: PublishJob["status"]): PublishJob => ({
  id: crypto.randomUUID(),
  clip_id: "c1",
  social_account_id: account,
  platform: "youtube",
  status,
  title: null,
  privacy_status: "private",
  external_id: null,
  external_url: null,
  error: null,
  published_at: null,
  created_at: "2026-11-22T00:00:00Z",
});

describe("alreadyUploaded", () => {
  it("counts published and in-progress uploads on the same account", () => {
    expect(alreadyUploaded([job("a", "published")], "a")).toBe(true);
    expect(alreadyUploaded([job("a", "queued")], "a")).toBe(true);
    expect(alreadyUploaded([job("a", "uploading")], "a")).toBe(true);
  });
  it("lets failed uploads and other accounts be uploaded again", () => {
    expect(alreadyUploaded([job("a", "failed")], "a")).toBe(false);
    expect(alreadyUploaded([job("b", "published")], "a")).toBe(false);
    expect(alreadyUploaded([], "a")).toBe(false);
  });
});
