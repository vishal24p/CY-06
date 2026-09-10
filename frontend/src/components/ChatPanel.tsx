"use client";

import { FormEvent, useState } from "react";

import { sendChat } from "@/lib/api";
import type { ChatMessage, ChatToolCall } from "@/lib/types";

const greeting: ChatMessage = {
  role: "assistant",
  content: "Ask about locally imported identities, privilege paths, findings, or policy impact.",
};
const MAX_CHAT_MESSAGES = 20;
const MAX_CHAT_MESSAGE_CHARS = 4_000;

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([greeting]);
  const [draft, setDraft] = useState("");
  const [toolCalls, setToolCalls] = useState<ChatToolCall[]>([]);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || sending) return;
    if (content.length > MAX_CHAT_MESSAGE_CHARS) {
      setError("Question must be 4,000 characters or fewer.");
      return;
    }

    const conversation = [...messages, { role: "user" as const, content }].slice(-MAX_CHAT_MESSAGES);
    setMessages(conversation);
    setDraft("");
    setToolCalls([]);
    setError("");
    setStatus("");
    setSending(true);

    try {
      const response = await sendChat(conversation);
      setMessages([...conversation, { role: "assistant" as const, content: response.message }].slice(-MAX_CHAT_MESSAGES));
      setToolCalls(response.tool_calls);
      setStatus(response.message ? `Assistant reply: ${response.message}` : "Assistant reply received.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Chat request failed.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="rounded-xl border border-[#d4dfdc] bg-white p-5" aria-labelledby="chat-heading">
      <div className="border-b border-[#e3ebe7] pb-4">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#147d78]">Read-only assistant</p>
        <h2 id="chat-heading" className="mt-1 text-xl font-semibold text-[#17252f]">Ask about this analysis</h2>
      </div>

      <ol className="mt-4 space-y-3" aria-label="Conversation">
        {messages.map((message, index) => (
          <li key={`${message.role}-${index}`} className={message.role === "user" ? "rounded-lg bg-[#eef7f4] p-3" : "rounded-lg bg-[#f7faf7] p-3"}>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#60716e]">{message.role === "user" ? "You" : "Assistant"}</p>
            <p className="mt-1 break-words whitespace-pre-wrap text-sm leading-6 text-[#314842]">{message.content}</p>
          </li>
        ))}
      </ol>

      <div className="mt-4 min-h-5" aria-live="polite">
        {sending && <p className="text-sm text-[#147d78]">Checking read-only analysis data…</p>}
        {!sending && status && <p className="sr-only" role="status">{status}</p>}
        {error && <p className="break-words rounded-lg border border-[#e2b7b1] bg-[#fff3f1] p-3 text-sm leading-5 text-[#a33d34]" role="alert">{error}</p>}
      </div>

      {toolCalls.length > 0 && (
        <ul className="mt-4 space-y-2" aria-label="Read-only tools used">
          {toolCalls.map((tool, index) => <li key={`${tool.name}-${index}`} className="break-words rounded-md border border-[#dce5e1] bg-[#f7faf7] px-3 py-2 text-xs text-[#536562]">Read-only tool: <span className="break-words font-mono text-[#314842]">{tool.name}</span></li>)}
        </ul>
      )}

      <form className="mt-5" onSubmit={handleSubmit}>
        <label htmlFor="chat-draft" className="text-sm font-medium text-[#314842]">Question</label>
        <textarea id="chat-draft" className="mt-2 min-h-24 w-full resize-y rounded-lg border border-[#9db3ad] bg-white px-3 py-2 text-sm leading-6 text-[#17252f] outline-none placeholder:text-[#71817e] focus:border-[#147d78] focus:ring-2 focus:ring-[#147d78]/20 disabled:bg-[#f7faf7]" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="For example: Which identities can assume privileged roles?" disabled={sending} />
        <button type="submit" className="mt-3 rounded-md bg-[#147d78] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#106964] focus:outline-none focus:ring-2 focus:ring-[#147d78] focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#9db3ad]" disabled={!draft.trim() || sending}>
          {sending ? "Sending…" : "Send question"}
        </button>
      </form>
    </section>
  );
}
