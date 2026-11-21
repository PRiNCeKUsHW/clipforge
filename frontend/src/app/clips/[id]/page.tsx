import { Suspense } from "react";

import { ClipEditor } from "@/components/editor/clip-editor";
import { RequireAuth } from "@/components/require-auth";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata = { title: "Edit clip · ClipForge" };

export default function ClipPage() {
  return (
    <RequireAuth>
      <Suspense fallback={<Skeleton className="h-[600px] w-full" />}>
        <ClipEditor />
      </Suspense>
    </RequireAuth>
  );
}
