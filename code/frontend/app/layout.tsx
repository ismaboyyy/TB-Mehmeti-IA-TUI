import "./globals.css";
import type { Metadata } from "next";
import { ChatProvider } from "@/lib/chat-context";

export const metadata: Metadata = {
  title: "Assistant TUI",
  description: "Assistant IA pour l'aide à la conception d'interfaces tangibles",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="h-full">
        <ChatProvider>{children}</ChatProvider>
      </body>
    </html>
  );
}
