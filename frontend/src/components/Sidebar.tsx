import {
  FileText,
  LayoutDashboard,
  LogOut,
  MessageSquareLock,
  Shield,
  ShieldAlert,
  Users,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { RoleBadge } from './Badges';

export type TabKey = 'dashboard' | 'chat' | 'documents' | 'admin' | 'audit';

interface SidebarProps {
  activeTab: TabKey;
  onSelectTab: (tab: TabKey) => void;
}

export function Sidebar({ activeTab, onSelectTab }: SidebarProps) {
  const { user, logout } = useAuth();

  const navItems: { key: TabKey; label: string; icon: typeof LayoutDashboard; adminOnly?: boolean }[] = [
    { key: 'dashboard', label: 'System Overview', icon: LayoutDashboard },
    { key: 'chat', label: 'Secure AI Chat', icon: MessageSquareLock },
    { key: 'documents', label: 'Document Vault', icon: FileText },
    { key: 'admin', label: 'Governance & Users', icon: Users, adminOnly: true },
    { key: 'audit', label: 'Compliance Audit', icon: ShieldAlert, adminOnly: true },
  ];

  return (
    <aside className="w-64 bg-[#0a1526] border-r border-white/10 flex flex-col justify-between shrink-0 h-screen sticky top-0">
      <div>
        {/* Brand */}
        <div className="h-16 px-6 flex items-center gap-3 border-b border-white/10">
          <div className="size-9 rounded-xl bg-cyan-400 text-slate-950 grid place-items-center shadow-lg shadow-cyan-400/20">
            <Shield size={20} className="stroke-[2.5]" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-wide text-white">NORTHSTAR</div>
            <div className="text-[10px] font-semibold tracking-wider text-cyan-300">SECURE VAULTRAG</div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-3 space-y-1 mt-2">
          {navItems
            .filter((item) => !item.adminOnly || user?.role === 'ADMIN')
            .map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => onSelectTab(item.key)}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-cyan-400 text-slate-950 font-semibold shadow-md shadow-cyan-400/10'
                      : 'text-slate-300 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  <Icon size={18} />
                  <span>{item.label}</span>
                </button>
              );
            })}
        </nav>
      </div>

      {/* User profile & logout */}
      <div className="p-4 border-t border-white/10 bg-[#07111f]/60">
        {user ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="truncate mr-2">
                <p className="text-xs font-semibold text-slate-200 truncate">{user.name}</p>
                <p className="text-[11px] text-slate-400 truncate">{user.email}</p>
              </div>
              <RoleBadge role={user.role} />
            </div>
            <button
              onClick={logout}
              className="w-full flex items-center justify-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-rose-300 hover:bg-rose-500/10 transition border border-white/10"
            >
              <LogOut size={13} />
              <span>Sign out</span>
            </button>
          </div>
        ) : null}
      </div>
    </aside>
  );
}
