export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 px-6 dark:bg-black">
      <main className="flex w-full max-w-2xl flex-col items-center gap-6 text-center">
        <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Duck
        </h1>
        <p className="max-w-md text-zinc-600 dark:text-zinc-400">
          The rubber duck that talks back. Connect a repo, then explain the bug like
          you&apos;re talking to a friend.
        </p>

        {/* Placeholder for the real chat/connect flow built in Phases 2-4.
            This textarea is the heart of the product and stays dictation-first. */}
        <textarea
          className="min-h-48 w-full resize-none rounded-2xl border border-zinc-200 bg-white p-6 text-lg text-zinc-900 shadow-sm outline-none placeholder:text-zinc-400 focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-50"
          placeholder="Hold your Wispr key and just talk."
          disabled
        />
      </main>
    </div>
  );
}
