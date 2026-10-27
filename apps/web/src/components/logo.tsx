import Link from "next/link";

/** The mark is a small version of the interview room's ring, so the brand and the product match. */
export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="flex items-center gap-2.5 font-heading text-lg font-semibold tracking-tight">
      <span aria-hidden className="relative grid size-7 place-items-center">
        <span className="absolute inset-0 rounded-full border-2 border-primary/35" />
        <span className="size-3.5 rounded-full bg-primary" />
      </span>
      Interviewer
    </Link>
  );
}
