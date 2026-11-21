"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useState } from "react";

// The selected ward is shared by every page (header picker, map click).
const WardContext = createContext<{ ward: string; setWard: (w: string) => void }>({ ward: "L", setWard: () => {} });
export const useWard = () => useContext(WardContext);

export default function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 5 * 60_000, retry: 1, refetchOnWindowFocus: false } } }),
  );
  const [ward, setWard] = useState("L");
  return (
    <QueryClientProvider client={client}>
      <WardContext.Provider value={{ ward, setWard }}>{children}</WardContext.Provider>
    </QueryClientProvider>
  );
}
