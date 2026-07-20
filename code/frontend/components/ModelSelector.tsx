"use client";
import { useState } from "react";
import { Check, ChevronDown, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  models: string[];
  value: string | null;
  onChange: (model: string) => void;
  disabled?: boolean;
  label?: string; // libellé court affiché avant la valeur (ex. "Reformulation")
}

// Sélecteur de modèle LLM (dropdown léger, sans dépendance externe).
export function ModelSelector({ models, value, onChange, disabled, label }: Props) {
  const [open, setOpen] = useState(false);
  if (!models.length) return null;

  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled}
        title={label}
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
      >
        <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
        {label && <span className="text-muted-foreground">{label} :</span>}
        {value ?? "Modèle"}
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <>
          {/* Capture des clics extérieurs pour fermer le menu */}
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-1 min-w-[180px] overflow-hidden rounded-lg border bg-popover p-1 shadow-md">
            {models.map((m) => (
              <button
                key={m}
                onClick={() => {
                  onChange(m);
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-left text-sm hover:bg-accent"
              >
                <span>{m}</span>
                {m === value && <Check className="h-3.5 w-3.5 text-primary" />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
