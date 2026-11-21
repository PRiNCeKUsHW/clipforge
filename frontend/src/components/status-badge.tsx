import { Badge } from "@/components/ui/badge";
import { STATUS_LABELS } from "@/lib/format";
import type { ProjectStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export function StatusBadge({ status }: { status: ProjectStatus }) {
  const working = status !== "ready" && status !== "failed";
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1.5 rounded-full border-transparent px-2.5",
        status === "ready" && "bg-[color-mix(in_oklch,var(--marigold)_28%,transparent)] text-foreground",
        status === "failed" && "bg-destructive/12 text-destructive",
        working && "bg-secondary text-secondary-foreground",
      )}
    >
      {working && <span className="size-1.5 animate-pulse rounded-full bg-rose" />}
      {STATUS_LABELS[status]}
    </Badge>
  );
}
