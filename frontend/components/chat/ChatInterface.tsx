/**
 * Chat Interface Component
 */

import { useState } from 'react';
import { useChat } from '../../hooks';

export default function ChatInterface() {
  const [input, setInput] = useState('');
  const { messages, isLoading, sendMessage } = useChat();

  const handleSend = async () => {
    if (!input.trim()) return;
    await sendMessage(input);
    setInput('');
  };

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 border rounded">
        {/* TODO: Implement message list with streaming */}
        {messages.length === 0 && (
          <p className="text-gray-500 text-center">Ask me about your finances...</p>
        )}
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask about your spending..."
          disabled={isLoading}
          className="flex-1 p-2 border rounded"
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
        >
          {isLoading ? 'Loading...' : 'Send'}
        </button>
      </div>
    </div>
  );
}
