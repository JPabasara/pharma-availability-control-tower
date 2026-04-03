"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { getEngineRuns } from "@/lib/api";
import type { EngineType, RunContext } from "@/lib/types";

const STORAGE_KEY = "pharma-control-tower.run-context";

const EMPTY_CONTEXT: RunContext = {
  m1RunId: null,
  m2RunId: null,
  m3RunId: null,
  generatedAt: null,
};

type RunContextValue = {
  runContext: RunContext | null;
  isReady: boolean;
  setRunContext: (
    next: RunContext | ((current: RunContext | null) => RunContext | null) | null
  ) => void;
  clearRunContext: () => void;
};

const PlannerRunContext = createContext<RunContextValue | null>(null);

function sanitizeRunContext(value: unknown): RunContext | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const source = value as Record<string, unknown>;
  return {
    m1RunId: typeof source.m1RunId === "number" ? source.m1RunId : null,
    m2RunId: typeof source.m2RunId === "number" ? source.m2RunId : null,
    m3RunId: typeof source.m3RunId === "number" ? source.m3RunId : null,
    generatedAt: typeof source.generatedAt === "string" ? source.generatedAt : null,
    m1GeneratedAt: typeof source.m1GeneratedAt === "string" ? source.m1GeneratedAt : null,
    m2GeneratedAt: typeof source.m2GeneratedAt === "string" ? source.m2GeneratedAt : null,
  };
}

function readStoredRunContext() {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? sanitizeRunContext(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

function persistRunContext(value: RunContext | null) {
  if (typeof window === "undefined") {
    return;
  }

  if (!value) {
    window.localStorage.removeItem(STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
}

function sameContext(left: RunContext | null, right: RunContext | null) {
  if (left === right) {
    return true;
  }

  if (!left || !right) {
    return false;
  }

  return (
    left.m1RunId === right.m1RunId &&
    left.m2RunId === right.m2RunId &&
    left.m3RunId === right.m3RunId &&
    left.generatedAt === right.generatedAt &&
    left.m1GeneratedAt === right.m1GeneratedAt &&
    left.m2GeneratedAt === right.m2GeneratedAt
  );
}

export function RunContextProvider({ children }: { children: React.ReactNode }) {
  const [runContext, setRunContextState] = useState<RunContext | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    setRunContextState(readStoredRunContext());
    setIsReady(true);
  }, []);

  const setRunContext = useCallback(
    (next: RunContext | ((current: RunContext | null) => RunContext | null) | null) => {
      setRunContextState((current) => {
        const resolved = typeof next === "function" ? next(current) : next;
        if (sameContext(current, resolved)) {
          return current;
        }
        persistRunContext(resolved);
        return resolved;
      });
    },
    []
  );

  const clearRunContext = useCallback(() => {
    persistRunContext(null);
    setRunContextState(null);
  }, []);

  const value = useMemo(
    () => ({
      runContext,
      isReady,
      setRunContext,
      clearRunContext,
    }),
    [clearRunContext, isReady, runContext, setRunContext]
  );

  return <PlannerRunContext.Provider value={value}>{children}</PlannerRunContext.Provider>;
}

export function usePlannerRunContext() {
  const value = useContext(PlannerRunContext);
  if (!value) {
    throw new Error("usePlannerRunContext must be used within RunContextProvider.");
  }
  return value;
}

const ENGINE_TO_KEY = {
  m1: "m1RunId",
  m2: "m2RunId",
  m3: "m3RunId",
} as const;

function parseRunId(value: string | null) {
  if (!value) {
    return null;
  }

  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

export function useResolvedRunId(engineType: EngineType) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const paramsString = searchParams.toString();
  const { runContext, setRunContext, isReady } = usePlannerRunContext();

  const [runId, setRunId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function resolve() {
      if (!isReady) {
        return;
      }

      setLoading(true);
      setError(null);

      const key = ENGINE_TO_KEY[engineType];
      const fromParams = parseRunId(searchParams.get(key));
      const fromContext = runContext?.[key] ?? null;

      const applyResolvedId = (
        resolvedId: number,
        source: "params" | "context" | "latest"
      ) => {
        if (ignore) {
          return;
        }

        setRunId(resolvedId);
        setLoading(false);

        setRunContext((current) => ({
          ...(current ?? EMPTY_CONTEXT),
          [key]: resolvedId,
          generatedAt: current?.generatedAt ?? null,
        }));

        if (source !== "params") {
          const nextParams = new URLSearchParams(paramsString);
          nextParams.set(key, String(resolvedId));
          const nextQuery = nextParams.toString();
          router.replace(nextQuery ? `${pathname}?${nextQuery}` : pathname, { scroll: false });
        }
      };

      if (fromParams) {
        applyResolvedId(fromParams, "params");
        return;
      }

      if (fromContext) {
        applyResolvedId(fromContext, "context");
        return;
      }

      try {
        const latest = await getEngineRuns(engineType, 1);
        const latestId = latest.runs[0]?.id ?? null;
        if (!latestId) {
          if (!ignore) {
            setRunId(null);
            setLoading(false);
          }
          return;
        }
        applyResolvedId(latestId, "latest");
      } catch (cause) {
        if (!ignore) {
          setRunId(null);
          setLoading(false);
          setError(
            cause instanceof Error ? cause.message : "Unable to resolve the active run."
          );
        }
      }
    }

    void resolve();

    return () => {
      ignore = true;
    };
  }, [engineType, isReady, paramsString, pathname, router, runContext, searchParams, setRunContext]);

  return { runId, loading, error };
}
