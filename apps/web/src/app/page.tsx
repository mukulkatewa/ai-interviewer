import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";

import { ButtonLink } from "@/components/button-link";
import { HeroDemo } from "@/components/hero-demo";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";

const STEPS = [
  {
    title: "Upload your resume",
    body: "A text-based PDF. We read your jobs, projects and skills, so there is nothing to fill in.",
  },
  {
    title: "Paste the job description",
    body: "You get a match score, the skills you are missing, and stronger bullets for your resume.",
  },
  {
    title: "Talk through the interview",
    body: "A voice interviewer asks about your own projects and this job's gaps, and follows up when an answer is vague.",
  },
  {
    title: "Read your report",
    body: "Scores for five skills, each backed by the exact words you said, plus a stronger answer for every question.",
  },
];

const PRINCIPLES = [
  {
    title: "Questions that fit you",
    body: "Built from your resume and the skills this job asks for that your resume does not show yet.",
  },
  {
    title: "Feedback you can check",
    body: "Every score points to a quote from your answers. If you did not say it, it is not in the report.",
  },
  {
    title: "Free, and yours",
    body: "No card, no trial. Your audio is never stored, and one button deletes everything else.",
  },
];

export default function LandingPage() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-5">
        <Logo />
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <ButtonLink href="/login" variant="ghost">
            Sign in
          </ButtonLink>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto grid w-full max-w-6xl items-center gap-14 px-5 pt-10 pb-24 lg:grid-cols-[1.05fr_1fr] lg:pt-20">
          <div>
            <h1 className="text-5xl leading-[1.02] font-semibold sm:text-6xl lg:text-7xl">
              Practice the interview for the job you actually want.
            </h1>
            <p className="mt-6 max-w-xl text-lg text-muted-foreground text-pretty">
              Upload your resume and paste a job description. You get a spoken interview built from both, then feedback
              that quotes your own answers.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <ButtonLink href="/login" size="lg" className="h-12 px-6 text-base">
                Start practicing free
                <ArrowRightIcon aria-hidden />
              </ButtonLink>
              <ButtonLink href="#how" variant="ghost" size="lg" className="h-12 px-5 text-base">
                See how it works
              </ButtonLink>
            </div>
          </div>
          <HeroDemo />
        </section>

        <section id="how" className="border-y bg-card/60">
          <div className="mx-auto grid w-full max-w-6xl gap-12 px-5 py-20 lg:grid-cols-[1fr_1.4fr]">
            <h2 className="text-3xl font-semibold sm:text-4xl lg:sticky lg:top-24 lg:self-start">
              From resume to report in about twenty minutes
            </h2>
            <ol className="relative space-y-9 border-l border-border pl-8">
              {STEPS.map((step, i) => (
                <li key={step.title} className="relative">
                  <span className="absolute top-0 -left-[2.9rem] grid size-8 place-items-center rounded-full border bg-background text-sm font-medium tabular-nums">
                    {i + 1}
                  </span>
                  <h3 className="text-xl font-semibold">{step.title}</h3>
                  <p className="mt-1 max-w-lg text-muted-foreground text-pretty">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="mx-auto w-full max-w-6xl px-5 py-20">
          <div className="grid gap-10 md:grid-cols-3">
            {PRINCIPLES.map((p) => (
              <div key={p.title}>
                <h3 className="text-xl font-semibold">{p.title}</h3>
                <p className="mt-2 text-muted-foreground text-pretty">{p.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-6xl px-5 pb-24">
          <div className="flex flex-col items-start justify-between gap-6 rounded-[1.75rem] bg-primary px-8 py-12 text-primary-foreground sm:flex-row sm:items-center sm:px-12">
            <h2 className="max-w-md text-3xl font-semibold sm:text-4xl">Your next interview is the one to practice for.</h2>
            <ButtonLink href="/login" variant="secondary" size="lg" className="h-12 px-6 text-base">
              Start practicing free
            </ButtonLink>
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-6 text-sm text-muted-foreground">
          <p>Built with Next.js, FastAPI, Groq and Kokoro.</p>
          <Link
            href="https://github.com/mukulkatewa/ai-interviewer"
            className="underline-offset-4 hover:text-foreground hover:underline"
          >
            Source on GitHub
          </Link>
        </div>
      </footer>
    </div>
  );
}
