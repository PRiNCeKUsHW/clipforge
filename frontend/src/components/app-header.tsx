"use client";

import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useMe } from "@/lib/use-me";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "New project" },
  { href: "/accounts", label: "Connected accounts" },
];

/** A vertical 9:16 frame with a play notch: the thing ClipForge makes. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" aria-hidden className={className}>
      <rect x="7" y="2" width="14" height="24" rx="4" fill="var(--marigold)" />
      <rect x="2" y="7" width="7" height="14" rx="3" fill="var(--rose)" opacity="0.9" />
      <path d="M12.5 10.5v7l5.5-3.5z" fill="var(--plum)" />
    </svg>
  );
}

export function AppHeader() {
  const { user } = useMe();
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();

  async function logout() {
    await api.logout().catch(() => undefined);
    queryClient.clear();
    router.replace("/login");
  }

  return (
    <header className="sticky top-0 z-30 bg-background/75 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-6 px-4">
        <Link href="/" className="flex items-center gap-2 font-heading text-lg font-bold tracking-tight">
          <LogoMark className="size-7" />
          ClipForge
        </Link>
        {user && (
          <nav className="hidden items-center gap-1 rounded-full bg-secondary/80 p-1 text-sm sm:flex">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-full px-3.5 py-1.5 text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                  pathname === item.href && "bg-card text-foreground shadow-[0_1px_2px_oklch(0.24_0.06_320/0.08)]",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        )}
        <div className="ml-auto flex items-center gap-2 text-sm">
          {user && (
            <>
              <span className="hidden text-muted-foreground md:inline">{user.email}</span>
              <Button variant="ghost" size="sm" onClick={logout} className="rounded-full">
                <LogOut /> Log out
              </Button>
            </>
          )}
        </div>
      </div>
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />
    </header>
  );
}
