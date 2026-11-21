"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Flame, LogOut } from "lucide-react";
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
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-6 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground">
            <Flame className="size-4" />
          </span>
          ClipForge
        </Link>
        {user && (
          <nav className="hidden items-center gap-1 text-sm sm:flex">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:text-foreground",
                  pathname === item.href && "bg-muted text-foreground",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        )}
        <div className="ml-auto flex items-center gap-3 text-sm">
          {user && (
            <>
              <span className="hidden text-muted-foreground md:inline">{user.email}</span>
              <Button variant="ghost" size="sm" onClick={logout}>
                <LogOut /> Log out
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
