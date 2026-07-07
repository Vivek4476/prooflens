"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { ThemeProvider } from "next-themes";
import { useState, type ReactNode } from "react";

import { ToastProvider } from "@/components/ui/Toast";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 10_000, refetchOnWindowFocus: false },
        },
      }),
  );

  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false} disableTransitionOnChange>
      <MotionConfig reducedMotion="user">
        <QueryClientProvider client={client}>
          <ToastProvider>{children}</ToastProvider>
        </QueryClientProvider>
      </MotionConfig>
    </ThemeProvider>
  );
}
