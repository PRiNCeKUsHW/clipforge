"use client";

import { useQuery } from "@tanstack/react-query";

import { api, ApiError } from "./api";

export function useMe() {
  const query = useQuery({ queryKey: ["me"], queryFn: api.me, staleTime: 60_000 });
  const unauthenticated = query.error instanceof ApiError && query.error.status === 401;
  return { ...query, user: query.data ?? null, unauthenticated };
}
