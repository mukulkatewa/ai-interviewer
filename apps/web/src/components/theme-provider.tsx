"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

/** Light, dark, or follow the system. The choice is remembered by next-themes. */
export function ThemeProvider({ children, ...props }: React.ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
