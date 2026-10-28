import {
  BarChart3Icon,
  BriefcaseIcon,
  FileTextIcon,
  LockKeyholeIcon,
  MicIcon,
  QuoteIcon,
} from "lucide-react";

import { ButtonLink } from "@/components/button-link";
import { HeroDemo } from "@/components/hero-demo";
import { Logo } from "@/components/logo";

const STEPS = [
  {
    title: "Upload your resume",
    body: "A text-based PDF. We read your projects, roles and skills, so you never fill in a form.",
  },
  {
    title: "Add a job, or skip it",
    body: "Paste a job description to practice for that role and see your match. No job in mind? Start straight away.",
  },
  {
    title: "Talk it through",
    body: "A voice interviewer asks about your own work, follows up, and ends with a report you can act on.",
  },
];

const FEATURES = [
  {
    icon: MicIcon,
    title: "A real conversation",
    body: "Speak your answers and hear the next question right away. It follows up when an answer is thin.",
  },
  {
    icon: FileTextIcon,
    title: "Questions from your resume",
    body: "It asks about the projects and decisions on your resume by name, not a generic question bank.",
  },
  {
    icon: QuoteIcon,
    title: "Feedback that quotes you",
    body: "Every score points to words you actually said, and every gap comes with a stronger answer to learn from.",
  },
  {
    icon: BriefcaseIcon,
    title: "Match a job, if you want",
    body: "Paste a job description to see which required skills you show, which you are missing, and better resume bullets.",
  },
  {
    icon: BarChart3Icon,
    title: "Honest scoring",
    body: "A high score needs proof in the transcript. Vague answers score low, and the report says why.",
  },
  {
    icon: LockKeyholeIcon,
    title: "Private by default",
    body: "Your PDF is not stored. Your data is only visible to you, and you can delete all of it in one click.",
  },
];

const FAQ = [
  {
    q: "Do I need a job description?",
    a: "No. Upload your resume and start. If you add a job description, the questions focus on that role and you also get a match report.",
  },
  {
    q: "Is it really free?",
    a: "Yes. There is a daily limit on interviews so the free service stays up for everyone.",
  },
  {
    q: "How long is an interview?",
    a: "About 15 minutes: a warm-up, questions about your resume, role skills, and two behavioral questions. You can stop at any time, by clicking End or just saying so.",
  },
  {
    q: "What do I need?",
    a: "A computer with a microphone and a recent browser. Headphones help, so the microphone does not hear the interviewer.",
  },
  {
    q: "Which languages are supported?",
    a: "English for now.",
  },
];

export default function LandingPage() {
  return (
    <div className="flex flex-1 flex-col">
      <div className="bg-glow">
        <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-5">
          <Logo />
          <nav className="hidden items-center gap-8 text-sm text-muted-foreground md:flex" aria-label="Sections">
            <a href="#how" className="transition-colors hover:text-foreground">
              How it works
            </a>
            <a href="#features" className="transition-colors hover:text-foreground">
              Features
            </a>
            <a href="#faq" className="transition-colors hover:text-foreground">
              FAQ
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <ButtonLink variant="ghost" href="/login">
              Log in
            </ButtonLink>
            <ButtonLink href="/login" className="rounded-full px-4">
              Get started
            </ButtonLink>
          </div>
        </header>

        <section className="mx-auto w-full max-w-6xl px-5 pb-20 pt-14 text-center sm:pt-20">
          <p className="mx-auto w-fit rounded-full border bg-card/70 px-3.5 py-1 text-sm text-muted-foreground backdrop-blur">
            Free. No credit card. Your resume is all you need.
          </p>
          <h1 className="mx-auto mt-6 max-w-3xl text-balance text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
            Practice your interview out loud, with feedback that is not vague.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg text-muted-foreground">
            An AI interviewer reads your resume, asks about your real projects, and tells you exactly what to fix, with
            your own words as proof.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <ButtonLink size="lg" href="/login" className="h-12 rounded-full px-7 text-base">
              Start your first interview
            </ButtonLink>
            <ButtonLink size="lg" variant="outline" href="#how" className="h-12 rounded-full bg-card/70 px-6 text-base">
              See how it works
            </ButtonLink>
          </div>
          <p className="mt-4 text-sm text-muted-foreground">Job description optional.</p>

          <div className="mt-16">
            <HeroDemo />
          </div>
        </section>
      </div>

      <main className="mx-auto flex w-full max-w-6xl flex-col gap-28 px-5 py-24">
        <section id="how" className="scroll-mt-20">
          <h2 className="max-w-xl text-balance text-3xl font-bold sm:text-4xl">From PDF to practice in a minute</h2>
          <ol className="mt-10 grid gap-5 md:grid-cols-3">
            {STEPS.map((step, i) => (
              <li key={step.title} className="rounded-2xl border bg-card p-6 shadow-sm">
                <span className="grid size-9 place-items-center rounded-full bg-accent text-sm font-semibold text-accent-foreground">
                  {i + 1}
                </span>
                <h3 className="mt-4 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-pretty text-muted-foreground">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="features" className="scroll-mt-20">
          <h2 className="max-w-xl text-balance text-3xl font-bold sm:text-4xl">Built to make you better, not to flatter you</h2>
          <ul className="mt-10 grid gap-x-10 gap-y-9 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <li key={title}>
                <span className="grid size-10 place-items-center rounded-xl bg-accent text-accent-foreground">
                  <Icon className="size-5" aria-hidden />
                </span>
                <h3 className="mt-4 font-semibold">{title}</h3>
                <p className="mt-1.5 text-pretty text-muted-foreground">{body}</p>
              </li>
            ))}
          </ul>
        </section>

        <section id="faq" className="mx-auto w-full max-w-3xl scroll-mt-20">
          <h2 className="text-center text-3xl font-bold sm:text-4xl">Questions</h2>
          <div className="mt-10 divide-y rounded-2xl border bg-card">
            {FAQ.map(({ q, a }) => (
              <details key={q} className="group p-5 [&_summary::-webkit-details-marker]:hidden">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
                  {q}
                  <span aria-hidden className="text-xl text-muted-foreground transition-transform group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="mt-3 text-pretty text-muted-foreground">{a}</p>
              </details>
            ))}
          </div>
        </section>

        <section className="overflow-hidden rounded-3xl bg-[oklch(0.19_0.03_281)] px-6 py-16 text-center text-white">
          <h2 className="mx-auto max-w-xl text-balance text-3xl font-bold sm:text-4xl">
            Your next interview is better after one practice round
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-pretty text-white/70">
            Upload a resume and answer eight questions out loud. The report is ready about a minute later.
          </p>
          <ButtonLink
            size="lg"
            href="/login"
            className="mt-8 h-12 rounded-full bg-white px-7 text-base text-[oklch(0.19_0.03_281)] hover:bg-white/90"
          >
            Start free
          </ButtonLink>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-3 px-5 py-8 text-sm text-muted-foreground sm:flex-row">
          <Logo />
          <p>Practice interviews, free. English only.</p>
        </div>
      </footer>
    </div>
  );
}
