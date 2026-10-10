import { useEffect, useState } from 'react';
import {
  ArrowRight,
  Database,
  FileText,
  Lock,
  MessageSquare,
  Server,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { RoleBadge } from '../components/Badges';
import { api, type AdminStats } from '../services/api';
import type { TabKey } from '../components/Sidebar';

export function DashboardView({ onSelectTab }: { onSelectTab: (tab: TabKey) => void }) {
  const { user } = useAuth();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [health, setHealth] = useState<{ status: string; database: string } | null>(null);

  useEffect(() => {
    api.health.check().then(setHealth).catch(() => setHealth(null));
    if (user?.role === 'ADMIN') {
      api.admin.getStats().then(setStats).catch(() => setStats(null));
    }
  }, [user]);

  const permittedLevels =
    user?.role === 'ADMIN'
      ? ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL']
      : user?.role === 'FACULTY'
      ? ['PUBLIC', 'INTERNAL']
      : ['PUBLIC'];

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Welcome Banner */}
      <div className="p-8 rounded-2xl bg-gradient-to-r from-[#0d1e35] to-[#0a1526] border border-white/10 shadow-2xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-cyan-400/5 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <span className="text-xs font-semibold tracking-wider text-cyan-300 uppercase">
                Zero-Leakage Document Intelligence
              </span>
              {user && <RoleBadge role={user.role} />}
            </div>
            <h1 className="text-3xl font-extrabold text-white">
              Welcome back, {user?.name || 'Researcher'}
            </h1>
            <p className="mt-2 text-sm text-slate-300 max-w-xl">
              VaultRAG strictly pre-filters vector search before LLM generation. You can only retrieve
              knowledge within your permitted security classification.
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={() => onSelectTab('chat')}
              className="px-5 py-3 rounded-xl bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-semibold text-sm flex items-center gap-2 shadow-lg shadow-cyan-400/10 transition"
            >
              <MessageSquare size={16} />
              <span>Open Secure Chat</span>
              <ArrowRight size={16} />
            </button>
            <button
              onClick={() => onSelectTab('documents')}
              className="px-4 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-slate-200 border border-white/10 text-sm font-medium transition"
            >
              Browse Documents
            </button>
          </div>
        </div>
      </div>

      {/* Permissions & Security Posture */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="p-6 rounded-xl bg-[#0d1a2b] border border-white/10 shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Your Access Level</span>
            <Lock size={18} className="text-cyan-300" />
          </div>
          <div className="text-2xl font-bold text-white mb-2">{user?.role}</div>
          <p className="text-xs text-slate-400 mb-4">Permitted document security tiers:</p>
          <div className="flex flex-wrap gap-1.5">
            {permittedLevels.map((lvl) => (
              <span
                key={lvl}
                className="px-2.5 py-1 rounded text-xs font-semibold bg-cyan-400/10 text-cyan-300 border border-cyan-400/20"
              >
                {lvl}
              </span>
            ))}
          </div>
        </div>

        <div className="p-6 rounded-xl bg-[#0d1a2b] border border-white/10 shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">System Readiness</span>
            <Server size={18} className="text-emerald-400" />
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400 flex items-center gap-2">
                <Zap size={14} className="text-emerald-400" /> API Gateway
              </span>
              <span className="text-emerald-400 font-semibold">{health ? 'Operational' : 'Connecting…'}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400 flex items-center gap-2">
                <Database size={14} className="text-emerald-400" /> SQLite Metadata
              </span>
              <span className="text-emerald-400 font-semibold">{health?.database === 'ok' ? 'Connected' : 'Checking…'}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400 flex items-center gap-2">
                <ShieldCheck size={14} className="text-emerald-400" /> FAISS Vector Store
              </span>
              <span className="text-emerald-400 font-semibold">Ready</span>
            </div>
          </div>
        </div>

        <div className="p-6 rounded-xl bg-[#0d1a2b] border border-white/10 shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Access Policy Matrix</span>
            <ShieldAlert size={18} className="text-purple-300" />
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between items-center py-1 border-b border-white/5">
              <span className="text-cyan-300 font-semibold">STUDENT</span>
              <span className="text-slate-300">PUBLIC</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-white/5">
              <span className="text-purple-300 font-semibold">FACULTY</span>
              <span className="text-slate-300">PUBLIC + INTERNAL</span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-amber-300 font-semibold">ADMIN</span>
              <span className="text-slate-300">ALL CLASSIFICATIONS</span>
            </div>
          </div>
        </div>
      </div>

      {/* Admin Quick Metrics if logged in as Admin */}
      {user?.role === 'ADMIN' && stats && (
        <div className="p-6 rounded-2xl bg-[#0d1a2b] border border-white/10 shadow-lg space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Admin Security Overview</h2>
            <button
              onClick={() => onSelectTab('admin')}
              className="text-xs text-cyan-300 hover:underline flex items-center gap-1"
            >
              Full Governance Console <ArrowRight size={12} />
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2">
            <div className="p-4 rounded-xl bg-[#07111f] border border-white/5">
              <span className="text-xs text-slate-400">Total Users</span>
              <p className="text-2xl font-bold text-white mt-1">{stats.total_users}</p>
            </div>
            <div className="p-4 rounded-xl bg-[#07111f] border border-white/5">
              <span className="text-xs text-slate-400">Total Documents</span>
              <p className="text-2xl font-bold text-white mt-1">{stats.total_documents}</p>
            </div>
            <div className="p-4 rounded-xl bg-[#07111f] border border-white/5">
              <span className="text-xs text-slate-400">Successful Queries</span>
              <p className="text-2xl font-bold text-emerald-400 mt-1">{stats.successful_accesses}</p>
            </div>
            <div className="p-4 rounded-xl bg-[#07111f] border border-white/5">
              <span className="text-xs text-slate-400">Denied Queries</span>
              <p className="text-2xl font-bold text-rose-400 mt-1">{stats.denied_accesses}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
