import type { VariantProps } from "class-variance-authority";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Navigation styled as a button. A real <a> (via next/link), so screen readers
 * announce a link and client navigation and prefetching work. A Base UI <Button>
 * rendered as a link gets role="button", which is wrong for navigation.
 */
export function ButtonLink({
  className,
  variant,
  size,
  ...props
}: React.ComponentProps<typeof Link> & VariantProps<typeof buttonVariants>) {
  return <Link className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
