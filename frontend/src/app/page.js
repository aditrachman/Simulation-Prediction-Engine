import Link from "next/link";

const features = [
  {
    title: "Predict Collective Reactions",
    desc: "Model public response from diverse agent archetypes before the real event unfolds.",
  },
  {
    title: "Map Sentiment Dynamics",
    desc: "Track support, resistance, and uncertainty through structured simulation outputs.",
  },
  {
    title: "Generate Actionable Insight",
    desc: "Turn complex narratives into concise risk signals and strategic recommendations.",
  },
];

const docItems = [
  {
    title: "Quickstart",
    desc: "Run backend and frontend locally, connect API, and test your first simulation in minutes.",
    href: "https://github.com/aditrachman/Simulation-Prediction-Engine#installation",
  },
  {
    title: "API Guide",
    desc: "Learn available endpoints and payload formats to automate simulation and prediction workflows.",
    href: "https://github.com/aditrachman/Simulation-Prediction-Engine#api-endpoints",
  },
  {
    title: "Configuration",
    desc: "Set model, environment variables, and deployment settings for your own use case.",
    href: "https://github.com/aditrachman/Simulation-Prediction-Engine#configuration",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-[#05070F] text-white">
      <section className="mx-auto flex max-w-6xl flex-col px-6 pt-8 pb-16 md:px-10 md:pt-10 md:pb-20">
        <div className="mb-10 flex items-center justify-between md:mb-12">
          <h1 className="text-2xl font-black tracking-widest uppercase">
            VoxSwarm
          </h1>
          <Link
            href="/demo"
            className="rounded-full border border-white/30 px-5 py-2 text-xs font-semibold tracking-widest uppercase transition hover:border-indigo-300 hover:bg-indigo-500/20"
          >
            Try Live Demo
          </Link>
        </div>

        <div className="grid gap-10 lg:grid-cols-2 lg:items-start">
          <div>
            <p className="mb-4 text-xs tracking-[0.35em] text-indigo-300 uppercase">
              Predict Anything
            </p>
            <h2 className="mb-6 text-4xl leading-tight font-black tracking-tight md:text-6xl">
              Social Intelligence
              <span className="block text-indigo-300">for high-stakes decisions</span>
            </h2>
            <p className="mb-10 max-w-xl text-sm leading-7 text-slate-300 md:text-base">
              VoxSwarm helps teams simulate crowd behavior, stress-test policy
              narratives, and identify potential instability early using
              multi-agent analysis.
            </p>

            <div className="flex flex-wrap gap-4">
              <Link
                href="/demo"
                className="rounded-full bg-indigo-500 px-7 py-3 text-sm font-bold tracking-wide uppercase transition hover:bg-indigo-400"
              >
                Try Live Demo
              </Link>
              <a
                href="https://mirofish-demo.pages.dev/"
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-white/25 px-7 py-3 text-sm font-bold tracking-wide uppercase transition hover:border-white/60"
              >
                View Reference
              </a>
            </div>
          </div>

          <div className="rounded-3xl border border-white/10 bg-gradient-to-b from-indigo-500/20 to-transparent p-8">
            <div className="mb-8 grid grid-cols-2 gap-4">
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="text-xs text-slate-300 uppercase">Scenario Accuracy</p>
                <p className="mt-2 text-2xl font-black">91%</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="text-xs text-slate-300 uppercase">Agent Nodes</p>
                <p className="mt-2 text-2xl font-black">24+</p>
              </div>
            </div>
            <div className="rounded-2xl border border-indigo-300/20 bg-black/30 p-5">
              <p className="text-xs tracking-widest text-indigo-300 uppercase">
                Live Insight
              </p>
              <p className="mt-3 text-sm leading-7 text-slate-300">
                "Policy X may trigger moderate backlash in urban communities,
                while rural clusters remain neutral with low escalation risk."
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-white/10 bg-[#080B16]">
        <div className="mx-auto grid max-w-6xl gap-4 px-6 py-14 md:grid-cols-3 md:px-10">
          {features.map((feature) => (
            <article
              key={feature.title}
              className="rounded-2xl border border-white/10 bg-white/5 p-6"
            >
              <h3 className="mb-2 text-sm font-bold tracking-wide uppercase">
                {feature.title}
              </h3>
              <p className="text-sm leading-6 text-slate-300">{feature.desc}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-t border-white/10 bg-[#070912]">
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-14 md:grid-cols-2 md:px-10">
          <article className="rounded-2xl border border-indigo-300/20 bg-indigo-400/5 p-7">
            <p className="mb-3 text-xs font-semibold tracking-[0.24em] text-indigo-300 uppercase">
              Star The Repository
            </p>
            <h3 className="mb-3 text-2xl font-black">Support VoxSwarm on GitHub</h3>
            <p className="mb-6 text-sm leading-7 text-slate-300">
              If this project helps you, drop a star to support development and
              future improvements. Every star helps visibility.
            </p>
            <a
              href="https://github.com/aditrachman/Simulation-Prediction-Engine"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center rounded-full bg-indigo-500 px-6 py-3 text-xs font-bold tracking-widest uppercase transition hover:bg-indigo-400"
            >
              Star on GitHub
            </a>
          </article>

          <article className="rounded-2xl border border-white/10 bg-white/5 p-7">
            <p className="mb-3 text-xs font-semibold tracking-[0.24em] text-indigo-300 uppercase">
              About Me
            </p>
            <h3 className="mb-3 text-2xl font-black">Built by Adit Rachman</h3>
            <p className="text-sm leading-7 text-slate-300">
              I am building VoxSwarm to turn AI simulation into practical
              decision intelligence. My focus is creating products that are
              visually clean, fast to run, and useful in real scenarios.
            </p>
          </article>
        </div>
      </section>

      <section className="border-t border-white/10 bg-[#05070F]">
        <div className="mx-auto max-w-6xl px-6 py-14 md:px-10">
          <div className="mb-8">
            <p className="mb-2 text-xs font-semibold tracking-[0.24em] text-indigo-300 uppercase">
              Documentation
            </p>
            <h3 className="text-3xl font-black">Everything You Need to Launch</h3>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {docItems.map((item) => (
              <a
                key={item.title}
                href={item.href}
                target="_blank"
                rel="noreferrer"
                className="rounded-2xl border border-white/10 bg-white/5 p-6 transition hover:border-indigo-300/40 hover:bg-indigo-400/5"
              >
                <h4 className="mb-2 text-sm font-bold tracking-wide uppercase">
                  {item.title}
                </h4>
                <p className="text-sm leading-6 text-slate-300">{item.desc}</p>
              </a>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
