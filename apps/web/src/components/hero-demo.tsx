const BARS = [0.4, 0.8, 0.55, 1, 0.65, 0.9, 0.45, 0.75, 0.5, 0.95, 0.6, 0.85, 0.4, 0.7];

/**
 * A static picture of the product, built in HTML so it stays sharp and costs no image download.
 * The sample answer and feedback are illustrative, not a real user's.
 */
export function HeroDemo() {
  return (
    <div className="relative mx-auto w-full max-w-4xl text-left">
      <div className="bg-dots absolute -inset-6 -z-10 rounded-[2rem] [mask-image:radial-gradient(closest-side,black,transparent)]" />
      <div className="overflow-hidden rounded-2xl border border-white/10 bg-[oklch(0.19_0.03_281)] text-white shadow-2xl shadow-primary/20">
        <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
          <span className="size-2.5 rounded-full bg-white/20" />
          <span className="size-2.5 rounded-full bg-white/20" />
          <span className="size-2.5 rounded-full bg-white/20" />
          <p className="ml-3 text-xs text-white/50">Backend Engineer · mock interview</p>
          <span className="ml-auto rounded-full bg-emerald-400/15 px-2.5 py-0.5 text-xs text-emerald-300">Live</span>
        </div>

        <div className="grid md:grid-cols-[1.25fr_1fr]">
          <div className="space-y-5 p-6 sm:p-8">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-primary text-xs font-semibold">
                AI
              </span>
              <p className="text-balance rounded-2xl rounded-tl-sm bg-white/[0.07] px-4 py-3 text-[0.95rem] leading-relaxed">
                You cut checkout latency on your payments project. How did you find the bottleneck, and what did you
                change?
              </p>
            </div>
            <div className="flex items-start justify-end gap-3">
              <p className="max-w-[85%] text-balance rounded-2xl rounded-tr-sm bg-primary/90 px-4 py-3 text-[0.95rem] leading-relaxed">
                I profiled the slow endpoint, found an N+1 query, and added a compound index. p95 dropped by thirty
                percent.
              </p>
            </div>
            <div className="flex items-center gap-3 pl-11" aria-hidden>
              <div className="flex h-8 items-center gap-1">
                {BARS.map((h, i) => (
                  <span
                    key={i}
                    className="wave-bar w-1 rounded-full bg-violet-300"
                    style={{ height: `${h * 100}%`, animationDelay: `${i * 90}ms` }}
                  />
                ))}
              </div>
              <span className="text-xs text-white/50">Listening…</span>
            </div>
          </div>

          <div className="border-t border-white/10 bg-white/[0.03] p-6 sm:p-8 md:border-t-0 md:border-l">
            <div className="flex items-baseline justify-between">
              <p className="text-sm text-white/60">Feedback on this answer</p>
              <p className="text-sm font-semibold text-amber-300">3 / 5</p>
            </div>
            <ul className="mt-4 space-y-3 text-sm leading-relaxed">
              <li className="rounded-xl bg-emerald-400/10 p-3">
                <span className="block text-xs font-medium text-emerald-300">Went well</span>
                You named the cause (an N+1 query) and the fix.
              </li>
              <li className="rounded-xl bg-amber-400/10 p-3">
                <span className="block text-xs font-medium text-amber-300">Missing</span>
                No before-and-after numbers, and no mention of how you checked nothing else slowed down.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
