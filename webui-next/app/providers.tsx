/**
 * Client-side providers for the application
 * Wraps the app with TanStack Query and other context providers
 */

"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  // Create a client instance per request to avoid sharing state between users
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Default options for all queries
            staleTime: 5000, // Data is fresh for 5 seconds
            gcTime: 1000 * 60 * 5, // Garbage collect after 5 minutes (formerly cacheTime)
            retry: 2, // Retry failed requests twice
            refetchOnWindowFocus: true, // Refetch when window regains focus
            refetchOnReconnect: true, // Refetch when reconnecting
          },
          mutations: {
            // Default options for all mutations
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* Show React Query DevTools in development */}
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} position="bottom" />
      )}
    </QueryClientProvider>
  );
}

