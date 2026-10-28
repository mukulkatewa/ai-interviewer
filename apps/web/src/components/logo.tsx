import Link from "next/link";

/** Four bars of a voice waveform on a violet tile: the product is a conversation. */
export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="flex items-center gap-2.5 font-semibold tracking-tight">
      <span
        aria-hidden
        className="grid size-8 place-items-center rounded-[0.6rem] bg-gradient-to-br from-violet-500 to-primary shadow-sm shadow-primary/30"
      >
        <svg viewBox="0 0 20 20" className="size-4 text-white" fill="currentColor">
          <rect x="2" y="8" width="2.4" height="4" rx="1.2" />
          <rect x="6.5" y="4" width="2.4" height="12" rx="1.2" />
          <rect x="11" y="6.5" width="2.4" height="7" rx="1.2" />
          <rect x="15.5" y="9" width="2.4" height="2" rx="1" />
        </svg>
      </span>
      <span className="text-[1.05rem]">Interviewer</span>
    </Link>
  );
}
