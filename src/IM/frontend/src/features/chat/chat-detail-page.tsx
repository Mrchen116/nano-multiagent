import { useParams } from "react-router-dom";

export function ChatDetailPage() {
  const { conversationId = "" } = useParams();

  return (
    <section className="im-card flex w-full flex-col p-6" aria-label="Chat detail page">
      <h1 className="im-title text-xl font-bold">Conversations</h1>
      <p className="mt-2 text-sm text-slate-500">Conversation: {conversationId}</p>
    </section>
  );
}
