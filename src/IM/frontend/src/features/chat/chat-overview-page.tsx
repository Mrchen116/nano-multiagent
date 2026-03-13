export function ChatOverviewPage() {
  return (
    <section className="im-card flex w-full flex-col gap-3 p-6" aria-label="Chat overview page">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Chat workspace</p>
      <h1 className="im-title text-xl font-bold">Conversations</h1>
      <p className="max-w-2xl text-sm text-slate-500">
        Review active customer, teammate, and agent conversations from one workspace while the chat shell finishes loading.
      </p>
    </section>
  );
}
