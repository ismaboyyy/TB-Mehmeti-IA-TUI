"use client";
import { Sparkles } from "lucide-react";

// Écran d'accueil simple : l'utilisateur saisit librement sa question.
export function EmptyState() {
  return (
    <div className="mx-auto flex h-full w-full max-w-3xl flex-col items-center justify-center px-4 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
        <Sparkles className="h-6 w-6" />
      </div>
      <h1 className="text-2xl font-semibold">Assistant à la conception d&apos;interfaces tangibles</h1>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        Décris ton besoin de conception. Je cherche dans la littérature scientifique, je synthétise
        et je cite mes sources. Si une précision est nécessaire, je te pose la question.
      </p>
    </div>
  );
}
