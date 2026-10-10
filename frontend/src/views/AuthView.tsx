import { useState } from 'react';
import { ArrowRight, Lock, Mail, Shield, User, Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export function AuthView() {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        if (!name.trim()) throw new Error('Name is required');
        await register(name.trim(), email.trim(), password);
      } else {
        await login(email.trim(), password);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = async (demoEmail: string, demoPass: string, demoName: string) => {
    setError(null);
    setLoading(true);
    try {
      // Attempt login, if account missing, register first then login
      try {
        await login(demoEmail, demoPass);
      } catch {
        await register(demoName, demoEmail, demoPass);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Demo login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#07111f] flex flex-col justify-center py-12 sm:px-6 lg:px-8 text-slate-100">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="size-14 mx-auto rounded-2xl bg-cyan-400 text-slate-950 grid place-items-center shadow-xl shadow-cyan-400/20">
          <Shield size={32} className="stroke-[2.5]" />
        </div>
        <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-white">NORTHSTAR VAULTRAG</h2>
        <p className="mt-2 text-sm text-slate-400">
          Role-Based Multi-Modal Document Intelligence
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-[#0d1a2b] py-8 px-6 shadow-2xl rounded-2xl border border-white/10 sm:px-10">
          <div className="flex border-b border-white/10 mb-6">
            <button
              onClick={() => { setIsRegister(false); setError(null); }}
              className={`flex-1 pb-3 text-sm font-semibold text-center transition ${
                !isRegister ? 'text-cyan-300 border-b-2 border-cyan-300' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => { setIsRegister(true); setError(null); }}
              className={`flex-1 pb-3 text-sm font-semibold text-center transition ${
                isRegister ? 'text-cyan-300 border-b-2 border-cyan-300' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Register (Student)
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg text-xs text-rose-300">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Full Name</label>
                <div className="relative">
                  <User size={16} className="absolute left-3 top-3 text-slate-400" />
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Alice Student"
                    className="w-full bg-[#07111f] border border-white/10 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Email Address</label>
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-3 text-slate-400" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="student@example.com"
                  className="w-full bg-[#07111f] border border-white/10 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Password</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-3 text-slate-400" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 12 characters"
                  className="w-full bg-[#07111f] border border-white/10 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-2.5 px-4 rounded-lg bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-semibold text-sm flex items-center justify-center gap-2 transition disabled:opacity-50"
            >
              <span>{loading ? 'Authenticating…' : isRegister ? 'Create Student Account' : 'Sign In'}</span>
              <ArrowRight size={16} />
            </button>
          </form>

          {/* Quick Demo Login */}
          <div className="mt-8 pt-6 border-t border-white/10">
            <div className="flex items-center gap-2 mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <Sparkles size={14} className="text-cyan-300" />
              <span>One-Click Demo Roles</span>
            </div>
            <div className="grid grid-cols-1 gap-2">
              <button
                type="button"
                onClick={() => handleQuickLogin('student@example.com', 'student_password_123', 'Alice Student')}
                className="w-full py-2 px-3 text-xs rounded-lg border border-cyan-400/20 bg-cyan-400/5 hover:bg-cyan-400/10 text-cyan-300 text-left flex items-center justify-between"
              >
                <span>Student (Access: PUBLIC only)</span>
                <span className="text-[10px] bg-cyan-400/20 px-1.5 py-0.5 rounded">Quick Demo</span>
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('faculty@example.com', 'faculty_password_123', 'Dr. Bob Faculty')}
                className="w-full py-2 px-3 text-xs rounded-lg border border-purple-400/20 bg-purple-400/5 hover:bg-purple-400/10 text-purple-300 text-left flex items-center justify-between"
              >
                <span>Faculty (Access: PUBLIC + INTERNAL)</span>
                <span className="text-[10px] bg-purple-400/20 px-1.5 py-0.5 rounded">Quick Demo</span>
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('admin@example.com', 'admin_password_123', 'Root Admin')}
                className="w-full py-2 px-3 text-xs rounded-lg border border-amber-400/20 bg-amber-400/5 hover:bg-amber-400/10 text-amber-300 text-left flex items-center justify-between"
              >
                <span>Admin (Access: ALL + Governance)</span>
                <span className="text-[10px] bg-amber-400/20 px-1.5 py-0.5 rounded">Quick Demo</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
