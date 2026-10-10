import { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Sidebar, type TabKey } from './components/Sidebar';
import { AuthView } from './views/AuthView';
import { DashboardView } from './views/DashboardView';
import { ChatView } from './views/ChatView';
import { DocumentsView } from './views/DocumentsView';
import { AdminView } from './views/AdminView';
import { AuditView } from './views/AuditView';

function MainApp() {
  const { user, isLoading } = useAuth();
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#07111f] grid place-items-center text-slate-400 text-sm">
        <div className="flex items-center gap-3">
          <span className="size-2 rounded-full bg-cyan-400 animate-ping" />
          <span>Initializing VaultRAG environment…</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <AuthView />;
  }

  return (
    <div className="min-h-screen bg-[#07111f] flex text-slate-100">
      {/* Sidebar */}
      <Sidebar activeTab={activeTab} onSelectTab={setActiveTab} />

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto p-8">
        {activeTab === 'dashboard' && <DashboardView onSelectTab={setActiveTab} />}
        {activeTab === 'chat' && <ChatView />}
        {activeTab === 'documents' && <DocumentsView />}
        {activeTab === 'admin' && user.role === 'ADMIN' && <AdminView />}
        {activeTab === 'audit' && user.role === 'ADMIN' && <AuditView />}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}
