"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, Loader2, MonitorPlay, Plug, Unplug } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { PlatformId } from "@/lib/types";

const PLATFORMS: { id: PlatformId; name: string; icon: typeof Camera; note: string; setup: string }[] = [
  {
    id: "youtube",
    name: "YouTube Shorts",
    icon: MonitorPlay,
    note: "Uploads via the YouTube Data API. Unverified apps can only upload private videos; daily quota is limited.",
    setup: "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env (see docs/DEPLOYMENT.md).",
  },
  {
    id: "instagram",
    name: "Instagram Reels",
    icon: Camera,
    note: "Needs an Instagram Business/Creator account linked to a Facebook Page. Videos must be at a public URL.",
    setup: "Set META_APP_ID and META_APP_SECRET in .env (see docs/DEPLOYMENT.md).",
  },
];

export function AccountsView() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const params = useSearchParams();
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.providers });
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.listAccounts });

  // Result of the OAuth redirect (?connected=youtube or ?error=...)
  useEffect(() => {
    const connected = params.get("connected");
    const error = params.get("error");
    if (connected) toast.success(`${connected === "youtube" ? "YouTube" : "Instagram"} connected`);
    if (error) toast.error(error, { duration: 10000 });
    if (connected || error) {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      router.replace("/accounts");
    }
  }, [params, queryClient, router]);

  const disconnect = useMutation({
    mutationFn: api.disconnectAccount,
    onSuccess: () => {
      toast.success("Disconnected");
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
    onError: (err) => toast.error(err.message),
  });

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Connected accounts</h1>
        <p className="mt-1 text-muted-foreground">Connect your channels to publish clips straight from the editor.</p>
      </div>
      {PLATFORMS.map(({ id, name, icon: Icon, note, setup }) => {
        const connected = accounts.data?.filter((a) => a.platform === id) ?? [];
        const available = providers.data?.[id];
        return (
          <Card key={id}>
            <CardHeader className="grid-cols-[auto_1fr_auto] items-center gap-x-3">
              <Icon className="row-span-2 size-6 text-muted-foreground" />
              <CardTitle>{name}</CardTitle>
              {providers.isPending ? (
                <Skeleton className="row-span-2 h-8 w-24" />
              ) : available ? (
                <a href={api.connectUrl(id)} className={`row-span-2 ${buttonVariants({ variant: "outline", size: "sm" })}`}>
                  <Plug /> {connected.length ? "Add another" : "Connect"}
                </a>
              ) : (
                <Badge variant="outline" className="row-span-2">
                  Not configured
                </Badge>
              )}
              <CardDescription>{note}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {!providers.isPending && !available && <p className="text-xs text-muted-foreground">{setup}</p>}
              {connected.map((a) => (
                <div key={a.id} className="flex items-center gap-3 rounded-md border border-border px-3 py-2 text-sm">
                  <span className="size-2 rounded-full bg-emerald-500" />
                  <span className="flex-1 truncate font-medium">{a.display_name || a.external_account_id}</span>
                  {a.expires_at && id === "instagram" && (
                    <span className="text-xs text-muted-foreground">expires {new Date(a.expires_at).toLocaleDateString()}</span>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => disconnect.mutate(a.id)}
                    disabled={disconnect.isPending}
                    aria-label={`Disconnect ${a.display_name}`}
                  >
                    {disconnect.isPending ? <Loader2 className="animate-spin" /> : <Unplug />}
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
