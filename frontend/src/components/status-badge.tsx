import { Badge } from "@/components/ui/badge";
import { STATUS_LABELS } from "@/lib/format";
import type { ProjectStatus } from "@/lib/types";

export function StatusBadge({ status }: { status: ProjectStatus }) {
  const variant = status === "failed" ? "destructive" : status === "ready" ? "default" : "secondary";
  return (
    <Badge variant={variant} className="gap-1.5">
      {status !== "ready" && status !== "failed" && <span className="size-1.5 animate-pulse rounded-full bg-primary" />}
      {STATUS_LABELS[status]}
    </Badge>
  );
}
