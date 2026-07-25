import { useCallback, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api';
import { supabase } from '@/lib/supabase';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export const useChat = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
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

      if (!response.ok) throw new Error('Chat request failed');

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

      // Buffer partial reads: a single network read is not guaranteed to align to
      // SSE line boundaries, so accumulate and only consume completed lines.
      let buffer = '';
      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? ''; // keep the trailing (possibly partial) line

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            assistantContent += line.slice(6);
            applyContent();
          }
        }
      }

      // Flush any complete line left in the buffer at stream end.
      if (buffer.startsWith('data: ')) {
        assistantContent += buffer.slice(6);
        applyContent();
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
      const errorMessage: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [queryClient]);

  return {
    messages,
    isLoading,
    sendMessage,
  };
};
