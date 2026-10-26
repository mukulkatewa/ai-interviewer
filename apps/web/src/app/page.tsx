import Link from "next/link";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";

const STEPS = [
  {
    title: "Upload your resume",
    body: "We read your experience, projects and skills: no forms to fill.",
  },
  {
    title: "Paste the job description",
    body: "Get a match score, the skills you're missing, and stronger resume bullets.",
  },
  {
    title: "Practice the interview",
    body: "A voice interviewer asks about your resume and this role, then shows exactly where to improve.",
  },
];

export default function LandingPage() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-4 py-5">
        <Logo />
        <Button variant="ghost" nativeButton={false} render={<Link href="/login" />}>
          Sign in
        </Button>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-4">
        <section className="py-16 sm:py-24">
          <p className="text-sm font-medium text-primary">Free · No credit card</p>
          <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-6xl">
            Practice the interview for the job you actually want.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-muted-foreground text-pretty">
            Questions built from your resume and the job description, and feedback that quotes your own answers.
          </p>
          <div className="mt-8 flex gap-3">
            <Button size="lg" className="h-11 px-5" nativeButton={false} render={<Link href="/login" />}>
              Get started
            </Button>
          </div>
        </section>

        <section className="grid gap-4 pb-24 sm:grid-cols-3" aria-label="How it works">
          {STEPS.map((step, i) => (
            <div key={step.title} className="rounded-xl border bg-card p-5">
              <span className="font-mono text-sm text-muted-foreground">0{i + 1}</span>
              <h2 className="mt-2 font-medium">{step.title}</h2>
              <p className="mt-1.5 text-sm text-muted-foreground">{step.body}</p>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
