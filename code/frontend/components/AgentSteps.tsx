"use client";
import { Check, Loader2, Circle, Minus } from "lucide-react";
import type { AgentStep, StepKey } from "@/lib/types";
import { cn } from "@/lib/utils";

const LABELS: Record<StepKey, string> = {
  understand: "Compréhension",
  retrieve: "Recherche documentaire",
  synthesize: "Synthèse",
};

function StatusIcon({ status }: { status: AgentStep["status"] }) {
  if (status === "done") return <Check className="h-3.5 w-3.5 text-primary" />;
  if (status === "active") return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />;
  if (status === "skipped") return <Minus className="h-3.5 w-3.5 text-muted-foreground/50" />;
  return <Circle className="h-3.5 w-3.5 text-muted-foreground/40" />;
}

// Indicateur d'état des 3 agents (LangGraph), mis à jour en temps réel.
export function AgentSteps({ steps }: { steps: AgentStep[] }) {
  return (
    <div className="mb-3 flex flex-col gap-1 rounded-xl border bg-muted/30 p-3 sm:flex-row sm:items-center sm:gap-4">
      {steps.map((step, i) => (
        <div key={step.key} className="flex items-center gap-2">
          <span className="flex items-center gap-1.5">
            <StatusIcon status={step.status} />
            <span
              className={cn(
                "text-xs font-medium",
                step.status === "idle" || step.status === "skipped"
                  ? "text-muted-foreground/60"
                  : "text-foreground",
              )}
            >
              <span className="mr-1 text-muted-foreground/50">{i + 1}.</span>
              {LABELS[step.key]}
            </span>
          </span>
          {step.detail && (
            <span className="truncate text-[11px] text-muted-foreground">— {step.detail}</span>
          )}
          {i < steps.length - 1 && <span className="hidden text-muted-foreground/30 sm:inline">→</span>}
        </div>
      ))}
    </div>
  );
}
