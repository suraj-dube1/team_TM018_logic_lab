import { useEffect, useState } from 'react';
import {
  RefreshCw,
  Shield,
  ShieldAlert,
  Users,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import { RoleBadge } from '../components/Badges';
import { api, type AdminStats, type UserProfile } from '../services/api';

export function AdminView() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [s, u] = await Promise.all([api.admin.getStats(), api.admin.getUsers()]);
      setStats(s);
      setUsers(u);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch admin data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await api.admin.updateUserRole(userId, newRole);
      await fetchData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Role update failed');
    }
  };

  const handleToggleActive = async (userId: string, currentActive: boolean, currentRole: string) => {
    try {
      await api.admin.updateUserRole(userId, currentRole, !currentActive);
      await fetchData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Status update failed');
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Shield className="text-amber-400" size={24} />
            <span>Governance & User Administration</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Manage system roles, security classifications, and observe security posture
          </p>
        </div>
        <button
          onClick={fetchData}
          className="p-2.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 transition"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300">
          {error}
        </div>
      )}

      {/* Metrics Cards */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl bg-[#0d1a2b] border border-white/10 shadow-lg">
            <span className="text-xs text-slate-400 font-medium">Total Registered Users</span>
            <div className="text-2xl font-bold text-white mt-1">{stats.total_users}</div>
          </div>
          <div className="p-5 rounded-2xl bg-[#0d1a2b] border border-white/10 shadow-lg">
            <span className="text-xs text-slate-400 font-medium">Total Documents</span>
            <div className="text-2xl font-bold text-white mt-1">{stats.total_documents}</div>
            <div className="text-[10px] text-slate-400 mt-1 flex gap-2">
              <span>Pub: {stats.documents_by_level.PUBLIC || 0}</span>
              <span>Int: {stats.documents_by_level.INTERNAL || 0}</span>
              <span>Conf: {stats.documents_by_level.CONFIDENTIAL || 0}</span>
            </div>
          </div>
          <div className="p-5 rounded-2xl bg-[#0d1a2b] border border-white/10 shadow-lg">
            <span className="text-xs text-slate-400 font-medium">Successful Accesses</span>
            <div className="text-2xl font-bold text-emerald-400 mt-1">{stats.successful_accesses}</div>
          </div>
          <div className="p-5 rounded-2xl bg-[#0d1a2b] border border-white/10 shadow-lg">
            <span className="text-xs text-slate-400 font-medium">Denied Accesses</span>
            <div className="text-2xl font-bold text-rose-400 mt-1">{stats.denied_accesses}</div>
          </div>
        </div>
      )}

      {/* User Management Table */}
      <div className="bg-[#0d1a2b] border border-white/10 rounded-2xl shadow-xl overflow-hidden">
        <div className="p-5 border-b border-white/10 flex items-center justify-between">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Users size={16} className="text-cyan-400" />
            <span>User Accounts & Role Permissions</span>
          </h3>
          <span className="text-xs text-slate-400">{users.length} registered accounts</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#07111f] border-b border-white/10 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
              <tr>
                <th className="px-5 py-3.5">Name</th>
                <th className="px-4 py-3.5">Email</th>
                <th className="px-4 py-3.5">Assigned Role</th>
                <th className="px-4 py-3.5">Status</th>
                <th className="px-4 py-3.5">Registered</th>
                <th className="px-5 py-3.5 text-right">Change Role</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-200">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-white/[0.02] transition">
                  <td className="px-5 py-4 font-semibold text-white">{u.name}</td>
                  <td className="px-4 py-4 text-slate-400">{u.email}</td>
                  <td className="px-4 py-4">
                    <RoleBadge role={u.role} />
                  </td>
                  <td className="px-4 py-4">
                    <button
                      onClick={() => handleToggleActive(u.id, u.is_active, u.role)}
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium transition ${
                        u.is_active
                          ? 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-400 hover:bg-rose-500/20'
                      }`}
                    >
                      {u.is_active ? <CheckCircle size={12} /> : <XCircle size={12} />}
                      {u.is_active ? 'Active' : 'Disabled'}
                    </button>
                  </td>
                  <td className="px-4 py-4 text-slate-400">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-5 py-4 text-right">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      className="bg-[#07111f] border border-white/15 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-cyan-400"
                    >
                      <option value="STUDENT">STUDENT</option>
                      <option value="FACULTY">FACULTY</option>
                      <option value="ADMIN">ADMIN</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
