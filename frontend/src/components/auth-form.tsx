"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LogoMark } from "@/components/app-header";
import { api } from "@/lib/api";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (!isLogin) await api.register(email, password);
      await api.login(email, password);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="hero-glow flex flex-1 flex-col items-center justify-center gap-6 px-4 py-16">
      <LogoMark className="size-14" />
      <Card className="w-full max-w-sm rounded-[1.75rem] border-border/70 py-7 shadow-[0_30px_70px_-34px_oklch(0.45_0.12_40/0.45)]">
        <CardHeader className="px-7">
          <CardTitle className="font-heading text-3xl font-extrabold tracking-tight">{isLogin ? "Welcome back" : "Create your account"}</CardTitle>
          <CardDescription>
            {isLogin ? "Log in to turn long videos into Shorts." : "Runs on your own computer. Free, no card needed."}
          </CardDescription>
        </CardHeader>
        <CardContent className="px-7">
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input className="h-11 rounded-xl" id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                className="h-11 rounded-xl"
                type="password"
                autoComplete={isLogin ? "current-password" : "new-password"}
                minLength={8}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              {!isLogin && <p className="text-xs text-muted-foreground">At least 8 characters.</p>}
            </div>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <Button type="submit" size="lg" className="h-12 rounded-full text-base font-semibold" disabled={busy}>
              {busy && <Loader2 className="animate-spin" />}
              {isLogin ? "Log in" : "Sign up"}
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              {isLogin ? "No account yet? " : "Already have an account? "}
              <Link href={isLogin ? "/register" : "/login"} className="text-primary underline-offset-4 hover:underline">
                {isLogin ? "Sign up" : "Log in"}
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
