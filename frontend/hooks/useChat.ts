/**
 * useChat hook for chat/RAG interface
 */

import { useCallback, useState } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export const useChat = () => {
  const [messages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = useCallback(async (_question: string) => {
    setIsLoading(true);
    try {
      // TODO: Implement chat API call with streaming
      // const response = await fetch('/api/chat', {
      //   method: 'POST',
      //   body: JSON.stringify({ question: _question }),
      // });
    } catch (error) {
      console.error('Chat error:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    messages,
    isLoading,
    sendMessage,
  };
};
