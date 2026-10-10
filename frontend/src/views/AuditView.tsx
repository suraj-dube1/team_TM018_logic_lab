import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Filter,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import { api, type AuditLogItem } from '../services/api';

export function AuditView() {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [actionFilter, setActionFilter] = useState<string>('');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await api.admin.getAuditLogs(
        100,
        actionFilter || undefined,
        statusFilter || undefined
      );
      setLogs(data);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to fetch audit logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [statusFilter, actionFilter]);

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <ShieldAlert className="text-rose-400" size={24} />
            <span>Immutable Compliance & Security Audit Trail</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time forensic ledger of authentications, authorization events, document operations, and access denials
          </p>
        </div>
        <button
          onClick={fetchLogs}
          className="p-2.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 transition self-start sm:self-auto"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Filters Bar */}
      <div className="p-4 rounded-xl bg-[#0d1a2b] border border-white/10 flex flex-wrap items-center gap-4 text-xs">
        <div className="flex items-center gap-2 text-slate-400">
          <Filter size={14} />
          <span className="font-semibold uppercase tracking-wider text-[10px]">Filter Events:</span>
        </div>

        <div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[#07111f] border border-white/15 rounded-lg px-3 py-1.5 text-xs text-white"
          >
            <option value="">All Statuses</option>
            <option value="SUCCESS">SUCCESS only</option>
            <option value="DENIED">DENIED only</option>
            <option value="ERROR">ERROR only</option>
          </select>
        </div>

        <div>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="bg-[#07111f] border border-white/15 rounded-lg px-3 py-1.5 text-xs text-white"
          >
            <option value="">All Actions</option>
            <option value="LOGIN_SUCCESS">LOGIN_SUCCESS</option>
            <option value="LOGIN_FAILURE">LOGIN_FAILURE</option>
            <option value="DOCUMENT_QUERY">DOCUMENT_QUERY</option>
            <option value="ACCESS_DENIED">ACCESS_DENIED</option>
            <option value="DOCUMENT_UPLOAD">DOCUMENT_UPLOAD</option>
            <option value="DOCUMENT_DELETE">DOCUMENT_DELETE</option>
            <option value="DOCUMENT_CLASSIFY">DOCUMENT_CLASSIFY</option>
            <option value="ADMIN_ROLE_CHANGE">ADMIN_ROLE_CHANGE</option>
          </select>
        </div>

        <span className="text-slate-500 ml-auto">
          Displaying {logs.length} most recent records
        </span>
      </div>

      {/* Audit Log Table */}
      <div className="bg-[#0d1a2b] border border-white/10 rounded-2xl shadow-xl overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-xs text-slate-400">Loading audit ledger…</div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400">No audit events match the selected criteria.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#07111f] border-b border-white/10 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-5 py-3.5">Timestamp (UTC)</th>
                  <th className="px-4 py-3.5">Action</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-4 py-3.5">Subject Email / Role</th>
                  <th className="px-5 py-3.5">Event Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-200">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-white/[0.02] transition font-mono text-[11px]">
                    <td className="px-5 py-3.5 text-slate-400 whitespace-nowrap">
                      {new Date(log.timestamp).toISOString().replace('T', ' ').substring(0, 19)}
                    </td>
                    <td className="px-4 py-3.5 font-semibold text-white">
                      {log.action}
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                          log.status === 'SUCCESS'
                            ? 'bg-emerald-500/15 text-emerald-400'
                            : log.status === 'DENIED'
                            ? 'bg-rose-500/15 text-rose-400'
                            : 'bg-amber-500/15 text-amber-400'
                        }`}
                      >
                        {log.status === 'SUCCESS' ? (
                          <CheckCircle2 size={11} />
                        ) : log.status === 'DENIED' ? (
                          <XCircle size={11} />
                        ) : (
                          <AlertTriangle size={11} />
                        )}
                        {log.status}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-slate-300">
                      {log.user_email || 'System'} {log.user_role ? `(${log.user_role})` : ''}
                    </td>
                    <td className="px-5 py-3.5 text-slate-400 font-sans text-xs">
                      {log.details || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
