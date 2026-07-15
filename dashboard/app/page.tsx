export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6 py-16">
      <h1 className="font-mono text-3xl font-bold tracking-tight">BP2UIP</h1>
      <p className="text-neutral-300">
        A migration compiler for RPA estates: Blue Prism in, modernized
        UiPath out, with the reasoning shown. This dashboard reads the
        pipeline&apos;s JSON artifacts. It is a shell for now; the pipeline
        comes first.
      </p>
      <p className="text-sm text-neutral-500">
        Progress and design decisions are logged in the repository:{" "}
        <a
          className="underline hover:text-neutral-300"
          href="https://github.com/ChriferW/BP2UIP"
        >
          github.com/ChriferW/BP2UIP
        </a>
      </p>
    </main>
  );
}
