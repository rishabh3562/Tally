import { useCallback, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api';
import { supabase } from '@/lib/supabase';
import type { ChatTrace } from '@/types';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  /** Provenance for this answer — which tools ran and what they returned. Only
   *  present for answers produced in this session (the trace is fetched right
   *  after the stream ends); reloaded history has none. */
  trace?: ChatTrace;
}

export const useChat = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  /** What the assistant is doing right now, streamed as `event: status`. Null
   *  once the answer starts arriving (or when nothing is in flight). */
  const [status, setStatus] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Load saved history once on mount so the conversation survives a reload.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiClient.get('/api/chat/messages');
        const rows = (res.data?.data ?? []) as {
          id: string;
          role: 'user' | 'assistant';
          content: string;
          created_at: string;
        }[];
        if (!cancelled && rows.length) {
          setMessages(
            rows.map((m) => ({
              id: m.id,
              role: m.role,
              content: m.content,
              timestamp: new Date(m.created_at),
            }))
          );
        }
      } catch {
        // History is best-effort; ignore load failures.
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const sendMessage = useCallback(async (question: string) => {
    if (!question.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ question }),
      });

      // Say WHY it failed. A generic "I encountered an error" is what made the
      // chat feel broken with no way to tell a stale login from a dead backend —
      // and a request that never reaches the server records no trace either.
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Your session expired — please sign in again.');
        }
        throw new Error(`The server rejected the request (HTTP ${response.status}).`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      let assistantContent = '';
      const assistantId = Date.now().toString();

      const applyContent = () => {
        setMessages((prev) => {
          const existing = prev.find((m) => m.id === assistantId);
          if (existing) {
            return prev.map((m) =>
              m.id === assistantId ? { ...m, content: assistantContent } : m
            );
          }
          return [
            ...prev,
            {
              id: assistantId,
              role: 'assistant',
              content: assistantContent,
              timestamp: new Date(),
            },
          ];
        });
      };

      // A raw newline can't travel inside an SSE data line, so the server sends
      // line breaks as the two-character escape `\n` (see chat_service._sse_pack).
      const decodeChunk = (chunk: string) => chunk.replace(/\\n/g, '\n');

      // The stream carries two kinds of event: progress (`event: status`) and the
      // answer itself (plain `data:`). Track the current event name so a status
      // line is shown as progress instead of being appended to the answer.
      let eventName = '';
      const consume = (line: string) => {
        if (line.startsWith('event: ')) {
          eventName = line.slice(7).trim();
          return;
        }
        if (!line.startsWith('data: ')) {
          if (line === '') eventName = ''; // blank line ends the event
          return;
        }
        const payload = line.slice(6);
        if (eventName === 'status') {
          setStatus(payload);
          return;
        }
        assistantContent += decodeChunk(payload);
        setStatus(null); // the answer has started; stop showing progress
        applyContent();
      };

      // Buffer partial reads: a single network read is not guaranteed to align to
      // SSE line boundaries, so accumulate and only consume completed lines.
      let buffer = '';
      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? ''; // keep the trailing (possibly partial) line

        for (const line of lines) consume(line);
      }

      // Flush any complete line left in the buffer at stream end.
      consume(buffer);

      // Provenance: the backend recorded this turn to chat_traces before the
      // stream ended, so the newest trace is ours. Attach it so the answer can
      // show WHICH tools produced it — best-effort, and only if the question
      // matches (a concurrent turn from another tab must not mislabel it).
      try {
        const res = await apiClient.get('/api/chat/traces', { params: { limit: 1 } });
        const trace = (res.data?.data ?? [])[0] as ChatTrace | undefined;
        if (trace && trace.question === question) {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, trace } : m))
          );
        }
      } catch {
        // Provenance is a bonus; never let it break the answer.
      }

      // The chat can now MUTATE data (categorize a merchant, create a category),
      // so refresh the views that would otherwise show stale numbers. These
      // queries aren't active on the chat page, so this just marks them stale
      // and they refetch when the user next opens those pages — cheap.
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['triage'] });
      queryClient.invalidateQueries({ queryKey: ['categories'] });
    } catch (error) {
      console.error('Chat error:', error);
      const detail =
        error instanceof TypeError
          ? "I couldn't reach the server — check that the backend is running."
          : error instanceof Error
            ? error.message
            : 'Something went wrong.';
      const errorMessage: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Sorry — ${detail}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setStatus(null);
    }
  }, [queryClient]);

  // Start a fresh conversation: delete persisted history (scoped server-side to
  // the caller) and clear the view. Best-effort — clear the view even if the
  // delete fails, so the user isn't stuck staring at old messages.
  const clearConversation = useCallback(async () => {
    try {
      await apiClient.delete('/api/chat/messages');
    } catch {
      // ignore; still clear locally
    }
    setMessages([]);
  }, []);

  return {
    messages,
    isLoading,
    status,
    historyLoading,
    sendMessage,
    clearConversation,
  };
};
