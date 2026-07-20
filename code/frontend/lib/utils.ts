import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// Helper shadcn : fusionne les classes Tailwind sans conflits.
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
