import { useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  ChevronDown,
  ChevronUp,
  FileText,
  Lock,
  Send,
  Shield,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { RoleBadge, SecurityLevelBadge } from '../components/Badges';
import { api, type Citation, type RAGResponse } from '../services/api';

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  citations?: Citation[];
  hasContext?: boolean;
  allowedLevels?: string[];
}

export function ChatView() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: `Hello ${user?.name || ''}. I am your secure RAG assistant. Ask any question regarding institutional documents. Retrieval is strictly restricted to your permitted classification level (${user?.role === 'ADMIN' ? 'PUBLIC, INTERNAL, CONFIDENTIAL' : user?.role === 'FACULTY' ? 'PUBLIC, INTERNAL' : 'PUBLIC'}).`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [expandedCitations, setExpandedCitations] = useState<Record<string, boolean>>({});

  const sampleQuestions = (() => {
    if (user?.role === 'ADMIN') {
      return [
        'What documents are shared in the system?',
        'What is the emergency reserve fund endowment allocation in the executive financial plan?',
        'Who must approve faculty sabbatical leave applications?',
        'Analyze shared documents and governance policies',
      ];
    }
    if (user?.role === 'FACULTY') {
      return [
        'What documents are accessible to faculty?',
        'Who must approve faculty sabbatical leave applications?',
        'What is the undergraduate student attendance requirement?',
        'What are the faculty research and teaching guidelines?',
      ];
    }
    // Default STUDENT / INTERN
    return [
      'What documents are shared with students?',
      'What is the student attendance and medical leave policy?',
      'What are the admission eligibility requirements and process?',
      'What scholarships and financial assistance are available?',
      'What can a student get in VaultRAG?',
    ];
  })();

  const handleSend = async (queryText?: string) => {
    const q = queryText || input;
    if (!q.trim() || loading) return;

    const userMsg: Message = {
      id: String(Date.now()),
      sender: 'user',
      text: q.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryText) setInput('');
    setLoading(true);

    try {
      const history = messages
        .filter((m) => m.id !== 'welcome')
        .slice(-6)
        .map((m) => ({
          role: m.sender === 'user' ? 'user' : 'assistant',
          content: m.text,
        }));
      const res: RAGResponse = await api.rag.query(q.trim(), 4, history);
      const assistantMsg: Message = {
        id: String(Date.now() + 1),
        sender: 'assistant',
        text: res.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: res.citations,
        hasContext: res.has_sufficient_context,
        allowedLevels: res.allowed_security_levels,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const errorMsg: Message = {
        id: String(Date.now() + 1),
        sender: 'assistant',
        text: `Error: ${err instanceof Error ? err.message : 'Failed to query RAG service.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const toggleCitation = (msgId: string) => {
    setExpandedCitations((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-5xl mx-auto">
      {/* Security Context Header */}
      <div className="p-4 mb-4 rounded-xl bg-[#0d1a2b] border border-white/10 shadow-md flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="size-8 rounded-lg bg-cyan-400/10 border border-cyan-400/20 text-cyan-300 grid place-items-center">
            <Lock size={16} />
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-200">Active Security Policy</div>
            <div className="text-[11px] text-slate-400">
              Filtering vector search before context construction
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {user && <RoleBadge role={user.role} />}
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((m) => {
          const isUser = m.sender === 'user';
          return (
            <div key={m.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-2xl rounded-2xl p-4 shadow-lg border ${
                  isUser
                    ? 'bg-cyan-500/15 border-cyan-400/30 text-white rounded-br-sm'
                    : 'bg-[#0d1a2b] border-white/10 text-slate-100 rounded-bl-sm'
                }`}
              >
                <div className="flex items-center justify-between gap-4 mb-1.5">
                  <span className="text-[11px] font-semibold tracking-wide text-slate-400">
                    {isUser ? 'You' : 'VaultRAG Intelligence'}
                  </span>
                  <span className="text-[10px] text-slate-500">{m.timestamp}</span>
                </div>

                <p className="text-sm leading-relaxed whitespace-pre-wrap">{m.text}</p>

                {/* Anti-hallucination / Access Restricted Banner */}
                {m.hasContext === false && (
                  <div className="mt-3 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center gap-2 text-xs text-amber-300">
                    <AlertCircle size={15} className="shrink-0" />
                    <span>Access Denied or No Authorized Content Found</span>
                  </div>
                )}

                {/* Citations Card Section */}
                {m.citations && m.citations.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-white/10">
                    <button
                      onClick={() => toggleCitation(m.id)}
                      className="w-full flex items-center justify-between text-xs font-semibold text-cyan-300 hover:text-cyan-200 transition"
                    >
                      <span className="flex items-center gap-1.5">
                        <BookOpen size={14} />
                        Verified Citations ({m.citations.length})
                      </span>
                      {expandedCitations[m.id] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>

                    {(expandedCitations[m.id] ?? true) && (
                      <div className="mt-3 space-y-2">
                        {m.citations.map((c) => (
                          <div
                            key={c.chunk_id + c.source_number}
                            className="p-3 rounded-lg bg-[#07111f] border border-white/10 text-xs space-y-1.5"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                                <FileText size={12} className="text-cyan-400" />
                                [Source {c.source_number}] {c.document_title} (Page {c.page_number})
                              </span>
                              <SecurityLevelBadge level={c.security_level} />
                            </div>
                            <blockquote className="italic text-slate-400 pl-2 border-l-2 border-cyan-400/40 text-[11px]">
                              "{c.quote_excerpt}"
                            </blockquote>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-[#0d1a2b] border border-white/10 rounded-2xl p-4 text-xs text-slate-400 flex items-center gap-2">
              <span className="size-2 rounded-full bg-cyan-400 animate-ping" />
              <span>Verifying authorization & synthesizing grounded response…</span>
            </div>
          </div>
        )}
      </div>

      {/* Sample Query Prompts */}
      <div className="pt-3 pb-2 flex flex-wrap gap-2">
        {sampleQuestions.map((sq) => (
          <button
            key={sq}
            onClick={() => handleSend(sq)}
            disabled={loading}
            className="text-[11px] px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 transition truncate max-w-xs flex items-center gap-1.5 disabled:opacity-50"
          >
            <Sparkles size={11} className="text-cyan-300" />
            <span className="truncate">{sq}</span>
          </button>
        ))}
      </div>

      {/* Input Form */}
      <div className="pt-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="relative"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            placeholder="Ask a question about uploaded documents…"
            className="w-full bg-[#0d1a2b] border border-white/15 rounded-xl pl-4 pr-12 py-3.5 text-sm text-white placeholder-slate-400 focus:outline-none focus:border-cyan-400 shadow-xl"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="absolute right-2 top-2 p-2 rounded-lg bg-cyan-400 hover:bg-cyan-300 text-slate-950 transition disabled:opacity-40"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}
