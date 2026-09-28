import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAuthStore } from '../../store/authStore';
import type { ChatMessage } from '../../types';
import {
  Send,
  Square,
  Bot,
  User,
  Sparkles,
  RefreshCw,
} from 'lucide-react';

export const ChatPage: React.FC = () => {
  const { token, user } = useAuthStore();
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const isRecruiter = user?.role === 'recruiter' || user?.role === 'hiring_manager';

  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: 'welcome',
      sender: 'agent',
      text: isRecruiter
        ? `Hello **${user?.name || 'Recruiter'}**! I am your Recruitment Operations AI Assistant. I can help you evaluate candidate referrals, check recruitment funnel metrics, review pending approvals, and schedule interviews.`
        : `Hello **${user?.name || 'Employee'}**! I am your Employee Referral Assistant. I can help you track the status of candidates you have referred, check your earned reward points, and explore matching open roles.`,
      timestamp: new Date(),
    },
  ]);

  const employeeSuggestions = [
    'What is my referral points balance?',
    'What is the status of my referred candidate?',
    'How do I submit a new candidate referral?',
    'What are the open engineering roles right now?',
  ];

  const recruiterSuggestions = [
    'Show candidates currently pending referral review',
    'Summarize our referral recruitment dashboard metrics',
    'Which referrals have been pending for more than 5 days?',
    'What is our conversion rate from referral to interview?',
    'Who are the top referrals for Senior Python Engineer?',
  ];

  const suggestions = isRecruiter ? recruiterSuggestions : employeeSuggestions;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  const handleSend = async (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query || isStreaming) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: query,
      timestamp: new Date(),
    };

    const agentMsgId = `agent-${Date.now()}`;
    const agentMsgPlaceholder: ChatMessage = {
      id: agentMsgId,
      sender: 'agent',
      text: '',
      timestamp: new Date(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, agentMsgPlaceholder]);
    setInput('');
    setIsStreaming(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

    try {
      const response = await fetch(`${backendUrl}/api/v1/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          message: query,
          conversation_id: conversationId,
        }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`Chat request failed with status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body stream is unavailable.');

      const decoder = new TextDecoder('utf-8');
      let accumulatedText = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            if (dataStr === '[DONE]') {
              break;
            }
            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.delta) {
                accumulatedText += parsed.delta;
              } else if (parsed.content) {
                accumulatedText += parsed.content;
              }
              if (parsed.conversation_id) {
                setConversationId(parsed.conversation_id);
              }
            } catch {
              accumulatedText += dataStr;
            }

            // Update agent message content in real time
            setMessages((prev) =>
              prev.map((m) =>
                m.id === agentMsgId ? { ...m, text: accumulatedText, isStreaming: true } : m
              )
            );
          }
        }
      }

      setMessages((prev) =>
        prev.map((m) => (m.id === agentMsgId ? { ...m, isStreaming: false } : m))
      );
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === agentMsgId
              ? { ...m, text: m.text + '\n\n*(Generation stopped)*', isStreaming: false }
              : m
          )
        );
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === agentMsgId
              ? {
                  ...m,
                  text: 'Sorry, I encountered an issue processing your request. Please ensure the backend is running and try again.',
                  isStreaming: false,
                  error: true,
                }
              : m
          )
        );
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 h-[calc(100vh-4.5rem)] flex flex-col">
      {/* Chat Container Card */}
      <div className="flex-1 bg-white rounded-3xl border border-slate-200/80 shadow-md flex flex-col overflow-hidden">
        {/* Chat Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-brand-600 text-white flex items-center justify-center shadow-xs">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                {isRecruiter ? 'Recruitment Operations AI' : 'Referral Companion AI'}
              </h2>
              <p className="text-[11px] text-emerald-600 font-medium flex items-center space-x-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block animate-pulse" />
                <span>Connected &bull; Active Zoho Session</span>
              </p>
            </div>
          </div>

          <button
            onClick={() => {
              setMessages([]);
              setConversationId(null);
            }}
            title="Clear Chat Session"
            className="p-2 text-slate-400 hover:text-slate-600 rounded-xl hover:bg-slate-100 transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Message Stream Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start space-x-3 ${
                msg.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''
              }`}
            >
              {/* Avatar */}
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-white text-xs shadow-xs ${
                  msg.sender === 'user'
                    ? 'bg-slate-800'
                    : 'bg-gradient-to-tr from-brand-600 to-indigo-500'
                }`}
              >
                {msg.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {/* Message Bubble */}
              <div
                className={`max-w-2xl rounded-2xl px-5 py-3.5 text-sm leading-relaxed ${
                  msg.sender === 'user'
                    ? 'bg-brand-600 text-white shadow-xs'
                    : 'bg-slate-50 border border-slate-200/80 text-slate-800'
                }`}
              >
                {msg.sender === 'user' ? (
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                ) : (
                  <div className="prose prose-slate prose-sm max-w-none prose-p:leading-relaxed prose-headings:font-bold prose-headings:text-slate-900 prose-table:border-collapse prose-th:border prose-th:border-slate-200 prose-th:p-2 prose-td:border prose-td:border-slate-200 prose-td:p-2">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.text || (msg.isStreaming ? 'Thinking...' : '')}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Thinking Spinner */}
          {isStreaming && (
            <div className="flex items-center space-x-2 text-xs text-slate-400 pl-11">
              <span className="w-2 h-2 rounded-full bg-brand-500 animate-bounce" />
              <span className="w-2 h-2 rounded-full bg-brand-500 animate-bounce [animation-delay:0.2s]" />
              <span className="w-2 h-2 rounded-full bg-brand-500 animate-bounce [animation-delay:0.4s]" />
              <span className="ml-1">Synthesizing live response...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggested Prompts Bar */}
        {messages.length <= 2 && (
          <div className="px-6 py-2.5 bg-slate-50/60 border-t border-slate-100 flex items-center space-x-2 overflow-x-auto scrollbar-none">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider shrink-0 flex items-center space-x-1">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              <span>Suggested:</span>
            </span>
            {suggestions.map((prompt, i) => (
              <button
                key={i}
                onClick={() => handleSend(prompt)}
                className="shrink-0 px-3 py-1 bg-white hover:bg-brand-50 hover:text-brand-700 hover:border-brand-200 border border-slate-200/80 rounded-full text-xs text-slate-600 transition"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {/* Input Form Bar */}
        <div className="p-4 border-t border-slate-100 bg-white">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center space-x-2"
          >
            <input
              type="text"
              placeholder={
                isRecruiter
                  ? 'Ask about pending approvals, conversion funnel, or match candidates...'
                  : 'Ask about your referral status, points balance, or matching jobs...'
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isStreaming}
              className="flex-1 px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-sm placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 focus:bg-white transition"
            />

            {isStreaming ? (
              <button
                type="button"
                onClick={handleStop}
                className="p-3 bg-rose-600 hover:bg-rose-700 text-white rounded-2xl shadow-xs transition"
                title="Stop Response Generation"
              >
                <Square className="w-4 h-4 fill-current" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="p-3 bg-brand-600 hover:bg-brand-700 text-white rounded-2xl shadow-xs transition disabled:opacity-40"
                title="Send Message"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
};
