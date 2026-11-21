import { Suspense } from "react";

import { ProjectView } from "@/components/project-view";
import { RequireAuth } from "@/components/require-auth";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProjectPage() {
  return (
    <RequireAuth>
      {/* With cacheComponents, reading the dynamic [id] param must happen inside a Suspense boundary */}
      <Suspense fallback={<Skeleton className="h-40 w-full" />}>
        <ProjectView />
      </Suspense>
    </RequireAuth>
  );
}
