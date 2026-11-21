import { Suspense } from "react";

import { AccountsView } from "@/components/accounts-view";
import { RequireAuth } from "@/components/require-auth";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata = { title: "Connected accounts · ClipForge" };

export default function AccountsPage() {
  return (
    <RequireAuth>
      {/* reads ?connected / ?error from the OAuth redirect: search params need a Suspense boundary */}
      <Suspense fallback={<Skeleton className="mx-auto h-80 w-full max-w-2xl" />}>
        <AccountsView />
      </Suspense>
    </RequireAuth>
  );
}
