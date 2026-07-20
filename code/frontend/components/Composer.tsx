"use client";
import { useRef, useEffect } from "react";
import { ArrowUp } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}

export function Composer({ value, onChange, onSubmit, disabled }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  // Auto-resize de la zone de texte
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl">
      <div className="flex items-end gap-2 rounded-3xl border bg-background p-2 pl-4 shadow-sm focus-within:border-primary/50">
        <Textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Décris ton besoin de conception d'interface tangible…"
          className="max-h-[200px] flex-1"
        />
        <Button
          size="icon"
          className="h-9 w-9 shrink-0 rounded-full"
          onClick={onSubmit}
          disabled={disabled || !value.trim()}
          aria-label="Envoyer"
        >
          <ArrowUp className="h-5 w-5" />
        </Button>
      </div>
      <p className="mt-2 text-center text-xs text-muted-foreground">
        L&apos;assistant s&apos;appuie sur le corpus scientifique indexé et cite ses sources.
      </p>
    </div>
  );
}
