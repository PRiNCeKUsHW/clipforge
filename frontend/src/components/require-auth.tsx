"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useMe } from "@/lib/use-me";

/** Client-side gate: the API is the real security boundary, this just routes logged-out users to /login. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { user, isPending, unauthenticated, error } = useMe();

  useEffect(() => {
    if (unauthenticated) router.replace("/login");
  }, [unauthenticated, router]);

  if (user) return <>{children}</>;
  if (error && !unauthenticated) {
    return (
      <Alert variant="destructive" className="mx-auto mt-10 max-w-lg">
        <AlertTitle>Can&apos;t load your account</AlertTitle>
        <AlertDescription>{error.message}</AlertDescription>
      </Alert>
    );
  }
  return (
    <div className="flex flex-1 items-center justify-center py-24 text-muted-foreground" aria-busy={isPending}>
      <Loader2 className="size-5 animate-spin" />
    </div>
  );
}
