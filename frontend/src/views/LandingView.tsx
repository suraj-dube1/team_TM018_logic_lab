import { useState } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Database,
  FileText,
  FolderUp,
  Layers,
  Lock,
  Search,
  Shield,
  Sparkles,
  Terminal,
  UserCheck,
  Users,
  XCircle,
  Zap,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface LandingViewProps {
  onOpenSignIn: () => void;
  onOpenRegister: () => void;
}

export function LandingView({ onOpenSignIn, onOpenRegister }: LandingViewProps) {
  const { login, register } = useAuth();
  const [activeDemoTab, setActiveDemoTab] = useState<'student_denied' | 'student_allowed' | 'admin_confidential'>('student_denied');
  const [quickLoginLoading, setQuickLoginLoading] = useState<string | null>(null);

  const handleQuickDemo = async (roleName: string, email: string, pass: string, name: string) => {
    setQuickLoginLoading(roleName);
    try {
      try {
        await login(email, pass);
      } catch {
        await register(name, email, pass);
      }
    } catch {
      // Handled in auth context
    } finally {
      setQuickLoginLoading(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#07111f] text-slate-100 selection:bg-cyan-500 selection:text-slate-950 overflow-x-hidden">
      {/* Top Background Ambient Glows */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[700px] h-[450px] bg-cyan-500/10 blur-[130px] rounded-full" />
        <div className="absolute top-96 -left-32 w-[400px] h-[400px] bg-purple-500/10 blur-[120px] rounded-full" />
        <div className="absolute top-96 -right-32 w-[400px] h-[400px] bg-emerald-500/10 blur-[120px] rounded-full" />
      </div>

      {/* Navigation Header */}
      <nav className="relative z-20 border-b border-white/10 backdrop-blur-md bg-[#07111f]/80 sticky top-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl bg-gradient-to-br from-cyan-400 to-teal-500 text-slate-950 grid place-items-center shadow-lg shadow-cyan-400/20 font-black">
              <Shield size={22} className="stroke-[2.5]" />
            </div>
            <div>
              <span className="font-extrabold tracking-tight text-white text-lg">NORTHSTAR VAULTRAG</span>
              <span className="hidden sm:inline-block ml-2 text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded-full bg-cyan-400/10 text-cyan-300 border border-cyan-400/20">
                Security-First AI
              </span>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-8 text-xs font-semibold text-slate-300">
            <a href="#features" className="hover:text-cyan-300 transition">Features</a>
            <a href="#simulator" className="hover:text-cyan-300 transition">Security Simulator</a>
            <a href="#roles" className="hover:text-cyan-300 transition">Role Clearance</a>
            <a href="#pipeline" className="hover:text-cyan-300 transition">Architecture</a>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={onOpenSignIn}
              className="text-xs font-semibold text-slate-300 hover:text-white px-3.5 py-2 rounded-lg hover:bg-white/5 transition"
            >
              Sign In
            </button>
            <button
              onClick={onOpenRegister}
              className="text-xs font-semibold bg-cyan-400 hover:bg-cyan-300 text-slate-950 px-4 py-2 rounded-lg shadow-lg shadow-cyan-400/20 transition flex items-center gap-1.5 font-bold"
            >
              <span>Get Started</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative z-10 pt-20 pb-24 sm:pt-28 sm:pb-32 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-cyan-400/10 border border-cyan-400/25 text-cyan-300 text-xs font-medium mb-8 shadow-inner animate-pulse-glow">
          <span className="size-2 rounded-full bg-cyan-400 animate-ping" />
          <span>ZERO-LEAKAGE MULTI-MODAL RAG • ROW-LEVEL SECURITY</span>
        </div>

        {/* Headline */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white max-w-4xl mx-auto leading-tight sm:leading-tight">
          Secure, Role-Based <br className="hidden sm:inline" />
          <span className="bg-gradient-to-r from-cyan-400 via-teal-300 to-emerald-400 bg-clip-text text-transparent">
            AI Knowledge Retrieval
          </span>
        </h1>

        {/* Subtitle */}
        <p className="mt-6 text-base sm:text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed">
          Enforce institutional clearance policies at the database layer <em>before</em> retrieval.
          Eliminate prompt injection and confidential document leakage across students, faculty, and administrators.
        </p>

        {/* Call to Actions */}
        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <button
            onClick={onOpenRegister}
            className="px-6 py-3.5 rounded-xl bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-bold text-sm shadow-xl shadow-cyan-400/25 hover:shadow-cyan-400/40 transition flex items-center gap-2"
          >
            <span>Create Student Account</span>
            <ArrowRight size={16} />
          </button>
          <button
            onClick={onOpenSignIn}
            className="px-6 py-3.5 rounded-xl bg-white/5 hover:bg-white/10 text-white font-semibold text-sm border border-white/15 transition flex items-center gap-2"
          >
            <Lock size={15} className="text-cyan-400" />
            <span>Sign In to Vault</span>
          </button>
          <a
            href="#demo"
            className="px-5 py-3.5 rounded-xl bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 font-semibold text-sm border border-purple-500/25 transition flex items-center gap-2"
          >
            <Sparkles size={15} className="text-purple-300" />
            <span>Instant Demo Roles</span>
          </a>
        </div>

        {/* Trust Badges */}
        <div className="mt-14 pt-8 border-t border-white/10 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto text-left">
          <div className="p-3 rounded-xl bg-white/5 border border-white/10">
            <div className="text-xs text-slate-400 font-medium">Pre-Retrieval Filter</div>
            <div className="text-sm font-bold text-cyan-300 flex items-center gap-1.5 mt-0.5">
              <CheckCircle2 size={15} /> Physical FAISS Partition
            </div>
          </div>
          <div className="p-3 rounded-xl bg-white/5 border border-white/10">
            <div className="text-xs text-slate-400 font-medium">Authorization Layer</div>
            <div className="text-sm font-bold text-emerald-300 flex items-center gap-1.5 mt-0.5">
              <CheckCircle2 size={15} /> Centralized RBAC
            </div>
          </div>
          <div className="p-3 rounded-xl bg-white/5 border border-white/10">
            <div className="text-xs text-slate-400 font-medium">Search Technology</div>
            <div className="text-sm font-bold text-purple-300 flex items-center gap-1.5 mt-0.5">
              <CheckCircle2 size={15} /> Hybrid BM25 + FAISS (RRF)
            </div>
          </div>
          <div className="p-3 rounded-xl bg-white/5 border border-white/10">
            <div className="text-xs text-slate-400 font-medium">Anti-Hallucination</div>
            <div className="text-sm font-bold text-amber-300 flex items-center gap-1.5 mt-0.5">
              <CheckCircle2 size={15} /> Verified Bracket Citations
            </div>
          </div>
        </div>
      </section>

      {/* Interactive Security Simulator */}
      <section id="simulator" className="relative z-10 py-16 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto">
        <div className="text-center mb-8">
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white">Live Security Simulation</h2>
          <p className="text-sm text-slate-400 mt-2">
            See how VaultRAG's pre-retrieval firewall protects documents across different user personas
          </p>
        </div>

        {/* Tab Controls */}
        <div className="bg-[#0d1a2b] p-1.5 rounded-2xl border border-white/10 flex flex-wrap gap-2 mb-6 shadow-xl">
          <button
            onClick={() => setActiveDemoTab('student_denied')}
            className={`flex-1 py-2.5 px-3 rounded-xl text-xs font-semibold transition flex items-center justify-center gap-2 ${
              activeDemoTab === 'student_denied'
                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <XCircle size={15} className="text-rose-400" />
            <span>Student asks for Confidential Budget</span>
          </button>
          <button
            onClick={() => setActiveDemoTab('student_allowed')}
            className={`flex-1 py-2.5 px-3 rounded-xl text-xs font-semibold transition flex items-center justify-center gap-2 ${
              activeDemoTab === 'student_allowed'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <CheckCircle2 size={15} className="text-cyan-400" />
            <span>Student asks for Attendance Policy</span>
          </button>
          <button
            onClick={() => setActiveDemoTab('admin_confidential')}
            className={`flex-1 py-2.5 px-3 rounded-xl text-xs font-semibold transition flex items-center justify-center gap-2 ${
              activeDemoTab === 'admin_confidential'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-400/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Shield size={15} className="text-amber-400" />
            <span>Admin asks for Confidential Budget</span>
          </button>
        </div>

        {/* Simulation Output Card */}
        <div className="bg-[#0d1a2b] border border-white/10 rounded-2xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
          {activeDemoTab === 'student_denied' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2 text-xs text-slate-300">
                  <span className="px-2 py-0.5 rounded bg-cyan-400/20 text-cyan-300 font-bold">STUDENT</span>
                  <span>Clearance: <strong>PUBLIC only</strong></span>
                </div>
                <span className="text-[11px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold flex items-center gap-1">
                  <XCircle size={12} /> Access Denied / Fail-Closed
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-400 font-medium">User Query:</span>
                <p className="text-sm font-semibold text-white mt-1">
                  "What is the institutional emergency reserve fund endowment allocation in the executive financial plan?"
                </p>
              </div>
              <div className="p-3.5 rounded-xl bg-[#07111f] border border-rose-500/20">
                <span className="text-[11px] font-bold text-rose-400 uppercase tracking-wider block mb-1">
                  Pre-Retrieval Security Action:
                </span>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Query restricted strictly to <code>index_public.faiss</code>. The <code>CONFIDENTIAL</code> sub-index is physically excluded from search. Zero unauthorized vectors retrieved.
                </p>
              </div>
              <div className="p-3.5 rounded-xl bg-[#07111f] border border-white/10">
                <span className="text-[11px] font-bold text-cyan-300 uppercase tracking-wider block mb-1">
                  VaultRAG Grounded Response:
                </span>
                <p className="text-xs text-slate-200 leading-relaxed">
                  "The authorized documents do not contain enough information to answer this question."
                </p>
                <div className="mt-2 text-[11px] text-slate-400 flex items-center gap-2">
                  <span className="size-2 rounded-full bg-rose-400" />
                  <span>0 Citations generated • Zero data leaked • Logged as ACCESS_DENIED in Audit Trail</span>
                </div>
              </div>
            </div>
          )}

          {activeDemoTab === 'student_allowed' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2 text-xs text-slate-300">
                  <span className="px-2 py-0.5 rounded bg-cyan-400/20 text-cyan-300 font-bold">STUDENT</span>
                  <span>Clearance: <strong>PUBLIC only</strong></span>
                </div>
                <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold flex items-center gap-1">
                  <CheckCircle2 size={12} /> Authorized & Grounded
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-400 font-medium">User Query:</span>
                <p className="text-sm font-semibold text-white mt-1">
                  "What is the undergraduate student attendance percentage requirement?"
                </p>
              </div>
              <div className="p-3.5 rounded-xl bg-[#07111f] border border-emerald-500/20">
                <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider block mb-1">
                  Pre-Retrieval Security Action:
                </span>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Searched <code>index_public.faiss</code>. Found matching chunks with similarity score 0.89 in <em>Student Attendance Rules</em>.
                </p>
              </div>
              <div className="p-3.5 rounded-xl bg-[#07111f] border border-white/10">
                <span className="text-[11px] font-bold text-cyan-300 uppercase tracking-wider block mb-1">
                  VaultRAG Grounded Response:
                </span>
                <p className="text-xs text-slate-200 leading-relaxed">
                  "Undergraduate students must maintain a mandatory minimum of 75% attendance across all registered courses. Students falling below this requirement without medical condonation are disqualified from examinations [Source 1]."
                </p>
                <div className="mt-2 text-[11px] text-cyan-300 font-semibold flex items-center gap-2">
                  <FileText size={13} />
                  <span>[Source 1] Student Attendance Rules (Page 4, Classification: PUBLIC)</span>
                </div>
              </div>
            </div>
          )}

          {activeDemoTab === 'admin_confidential' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2 text-xs text-slate-300">
                  <span className="px-2 py-0.5 rounded bg-amber-400/20 text-amber-300 font-bold">ADMIN</span>
                  <span>Clearance: <strong>PUBLIC, INTERNAL, CONFIDENTIAL</strong></span>
                </div>
                <span className="text-[11px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold flex items-center gap-1">
                  <CheckCircle2 size={12} /> Executive Clearance Authorized
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-400 font-medium">User Query:</span>
                <p className="text-sm font-semibold text-white mt-1">
                  "What is the institutional emergency reserve fund endowment allocation in the executive financial plan?"
                </p>
              </div>
              <div className="p-3.5 rounded-xl bg-[#07111f] border border-amber-500/20">
                <span className="text-[11px] font-bold text-amber-400 uppercase tracking-wider block mb-1">
                  Pre-Retrieval Security Action:
                </span>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Searched <code>index_confidential.faiss</code>. Found exact match in Section 1 of <em>Board of Trustees Executive Financial Plan 2026</em>.
                </p>
              </div>
              <div className="p-3.5 rounded-xl bg-[#07111f] border border-white/10">
                <span className="text-[11px] font-bold text-cyan-300 uppercase tracking-wider block mb-1">
                  VaultRAG Grounded Response:
                </span>
                <p className="text-xs text-slate-200 leading-relaxed">
                  "The institutional emergency reserve fund endowment maintains a designated liquidity balance of $42.5 million ($42.5M) for campus expansion, high-security facilities, and crisis contingency stabilization for fiscal year 2026 [Source 1]."
                </p>
                <div className="mt-2 text-[11px] text-amber-400 font-semibold flex items-center gap-2">
                  <FileText size={13} />
                  <span>[Source 1] Board of Trustees Executive Financial Plan 2026 (Page 1, Classification: CONFIDENTIAL)</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Core Architectural Features */}
      <section id="features" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-white/10">
        <div className="text-center mb-16">
          <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">Security Architecture</span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white mt-2">Engineered for Zero Data Leakage</h2>
          <p className="text-sm text-slate-400 mt-3 max-w-2xl mx-auto">
            Traditional RAG searches all documents and filters afterward. VaultRAG physically isolates data before retrieval.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Card 1 */}
          <div className="p-6 rounded-2xl bg-[#0d1a2b] border border-white/10 hover:border-cyan-400/40 transition group">
            <div className="size-12 rounded-xl bg-cyan-400/10 text-cyan-300 grid place-items-center mb-4 group-hover:scale-110 transition">
              <Database size={24} />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Physical Vector Partitioning</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Maintains distinct FAISS indices for PUBLIC, INTERNAL, and CONFIDENTIAL tiers. Unauthorized chunks are physically excluded from vector search.
            </p>
          </div>

          {/* Card 2 */}
          <div className="p-6 rounded-2xl bg-[#0d1a2b] border border-white/10 hover:border-emerald-400/40 transition group">
            <div className="size-12 rounded-xl bg-emerald-400/10 text-emerald-300 grid place-items-center mb-4 group-hover:scale-110 transition">
              <UserCheck size={24} />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Centralized RBAC Engine</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Single-source-of-truth authorization matrix in <code>access_control_service.py</code>. Verifies user roles directly against the database on every query.
            </p>
          </div>

          {/* Card 3 */}
          <div className="p-6 rounded-2xl bg-[#0d1a2b] border border-white/10 hover:border-purple-400/40 transition group">
            <div className="size-12 rounded-xl bg-purple-400/10 text-purple-300 grid place-items-center mb-4 group-hover:scale-110 transition">
              <Search size={24} />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Hybrid BM25 + FAISS Fusion</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Combines lexical BM25Okapi scoring for exact codes and numbers with dense semantic vectors via Reciprocal Rank Fusion (RRF, k=60).
            </p>
          </div>

          {/* Card 4 */}
          <div className="p-6 rounded-2xl bg-[#0d1a2b] border border-white/10 hover:border-amber-400/40 transition group">
            <div className="size-12 rounded-xl bg-amber-400/10 text-amber-300 grid place-items-center mb-4 group-hover:scale-110 transition">
              <FolderUp size={24} />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Batch & Folder Ingestion</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Accepts single files, multi-file drag-and-drop, entire directory folders (<code>webkitdirectory</code>), and ZIP archives across PDF, TXT, MD, and images.
            </p>
          </div>

          {/* Card 5 */}
          <div className="p-6 rounded-2xl bg-[#0d1a2b] border border-white/10 hover:border-rose-400/40 transition group">
            <div className="size-12 rounded-xl bg-rose-400/10 text-rose-300 grid place-items-center mb-4 group-hover:scale-110 transition">
              <Terminal size={24} />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Tamper-Evident Audit Trail</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Comprehensive event logging for document queries, uploads, classification migrations, and ACCESS_DENIED security events with full timestamps.
            </p>
          </div>

          {/* Card 6 */}
          <div className="p-6 rounded-2xl bg-[#0d1a2b] border border-white/10 hover:border-cyan-400/40 transition group">
            <div className="size-12 rounded-xl bg-cyan-400/10 text-cyan-300 grid place-items-center mb-4 group-hover:scale-110 transition">
              <Zap size={24} />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Anti-Hallucination & Citations</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Strict bracketed source grounding <code>[Source 1]</code> pointing to document titles and page numbers. Fails closed when context is absent.
            </p>
          </div>
        </div>
      </section>

      {/* Role Clearance Matrix */}
      <section id="roles" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto border-t border-white/10">
        <div className="text-center mb-12">
          <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">Access Governance</span>
          <h2 className="text-3xl font-extrabold text-white mt-2">Role Clearance Matrix</h2>
          <p className="text-sm text-slate-400 mt-2">How permissions are enforced across academic and corporate personas</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Student */}
          <div className="p-6 rounded-2xl bg-[#0d1a2b] border border-cyan-400/20 relative">
            <div className="text-xs font-bold uppercase tracking-wider text-cyan-300 mb-2">Academic Persona</div>
            <h3 className="text-xl font-bold text-white mb-1">STUDENT</h3>
            <div className="text-xs text-slate-400 mb-4">Clearance Level: <strong>PUBLIC</strong></div>
            <ul className="text-xs space-y-2.5 text-slate-300">
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-cyan-400 shrink-0 mt-0.5" />
                <span>Undergraduate Student Handbook</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-cyan-400 shrink-0 mt-0.5" />
                <span>Attendance & Exam Regulations</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-cyan-400 shrink-0 mt-0.5" />
                <span>Admission & Scholarship Guidelines</span>
              </li>
              <li className="flex items-start gap-2 text-slate-500">
                <XCircle size={14} className="text-rose-400 shrink-0 mt-0.5" />
                <span>Faculty Senate Operations (Denied)</span>
              </li>
              <li className="flex items-start gap-2 text-slate-500">
                <XCircle size={14} className="text-rose-400 shrink-0 mt-0.5" />
                <span>Executive Financial Plans (Denied)</span>
              </li>
            </ul>
          </div>

          {/* Faculty */}
          <div className="p-6 rounded-2xl bg-[#0d1a2b] border border-purple-400/20 relative">
            <div className="text-xs font-bold uppercase tracking-wider text-purple-300 mb-2">Faculty / Staff Persona</div>
            <h3 className="text-xl font-bold text-white mb-1">FACULTY</h3>
            <div className="text-xs text-slate-400 mb-4">Clearance Level: <strong>PUBLIC + INTERNAL</strong></div>
            <ul className="text-xs space-y-2.5 text-slate-300">
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-purple-400 shrink-0 mt-0.5" />
                <span>All Public Student Documents</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-purple-400 shrink-0 mt-0.5" />
                <span>Faculty Senate Operations & Guidelines</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-purple-400 shrink-0 mt-0.5" />
                <span>Internal Research Grants ($75k)</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-purple-400 shrink-0 mt-0.5" />
                <span>Sabbatical Approval Procedures</span>
              </li>
              <li className="flex items-start gap-2 text-slate-500">
                <XCircle size={14} className="text-rose-400 shrink-0 mt-0.5" />
                <span>Board Financial Reserves (Denied)</span>
              </li>
            </ul>
          </div>

          {/* Admin */}
          <div className="p-6 rounded-2xl bg-[#0d1a2b] border border-amber-400/20 relative">
            <div className="text-xs font-bold uppercase tracking-wider text-amber-300 mb-2">Executive Persona</div>
            <h3 className="text-xl font-bold text-white mb-1">ADMIN</h3>
            <div className="text-xs text-slate-400 mb-4">Clearance Level: <strong>FULL (ALL TIERS)</strong></div>
            <ul className="text-xs space-y-2.5 text-slate-300">
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-amber-400 shrink-0 mt-0.5" />
                <span>All Public & Internal Documents</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-amber-400 shrink-0 mt-0.5" />
                <span>Board Executive Financial Plans ($42.5M)</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-amber-400 shrink-0 mt-0.5" />
                <span>Project Silicon Annex Acquisition ($18M)</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-amber-400 shrink-0 mt-0.5" />
                <span>Dynamic Document Reclassification</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-amber-400 shrink-0 mt-0.5" />
                <span>System Audit Logs & User Roles</span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* 4-Step Pipeline Architecture */}
      <section id="pipeline" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto border-t border-white/10">
        <div className="text-center mb-16">
          <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">Processing Workflow</span>
          <h2 className="text-3xl font-extrabold text-white mt-2">How Information Flows Through VaultRAG</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl bg-[#0d1a2b] border border-white/10 relative">
            <div className="size-8 rounded-lg bg-cyan-400/20 text-cyan-300 font-black text-xs grid place-items-center mb-3">
              01
            </div>
            <h4 className="font-bold text-sm text-white mb-1">Ingestion & Hash</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              Magic byte validation, SHA-256 integrity fingerprinting, and UUID file obfuscation.
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-[#0d1a2b] border border-white/10 relative">
            <div className="size-8 rounded-lg bg-purple-400/20 text-purple-300 font-black text-xs grid place-items-center mb-3">
              02
            </div>
            <h4 className="font-bold text-sm text-white mb-1">Chunk & Embed</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              Page-isolated 1000-char windows with 384-dimensional dense semantic vectors.
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-[#0d1a2b] border border-white/10 relative">
            <div className="size-8 rounded-lg bg-emerald-400/20 text-emerald-300 font-black text-xs grid place-items-center mb-3">
              03
            </div>
            <h4 className="font-bold text-sm text-white mb-1">Pre-Retrieval Filter</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              Queries only the authorized FAISS sub-indices for the active user's role.
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-[#0d1a2b] border border-white/10 relative">
            <div className="size-8 rounded-lg bg-amber-400/20 text-amber-300 font-black text-xs grid place-items-center mb-3">
              04
            </div>
            <h4 className="font-bold text-sm text-white mb-1">Grounded RAG</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              OpenRouter GPT-4o-mini synthesizes verified answers with bracketed citations.
            </p>
          </div>
        </div>
      </section>

      {/* One-Click Demo Role Section */}
      <section id="demo" className="relative z-10 py-16 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
        <div className="p-8 sm:p-10 rounded-3xl bg-gradient-to-br from-[#0d1a2b] via-[#0b1726] to-[#07111f] border border-cyan-400/30 shadow-2xl text-center">
          <div className="size-14 mx-auto rounded-2xl bg-cyan-400/10 border border-cyan-400/20 text-cyan-300 grid place-items-center mb-4">
            <Sparkles size={28} />
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white">Experience VaultRAG Live</h2>
          <p className="text-sm text-slate-400 mt-2 max-w-lg mx-auto">
            Click any role below to instantly log in and test document retrieval, catalog exploration, and security boundaries.
          </p>

          <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <button
              onClick={() => handleQuickDemo('student', 'student@example.com', 'student_password_123', 'Alice Student')}
              disabled={!!quickLoginLoading}
              className="py-3 px-4 rounded-xl border border-cyan-400/30 bg-cyan-400/10 hover:bg-cyan-400/20 text-cyan-300 text-xs font-bold transition flex items-center justify-between disabled:opacity-50"
            >
              <span>{quickLoginLoading === 'student' ? 'Entering…' : 'Alice (Student)'}</span>
              <span className="text-[10px] bg-cyan-400/20 px-2 py-0.5 rounded">PUBLIC only</span>
            </button>
            <button
              onClick={() => handleQuickDemo('faculty', 'faculty@example.com', 'faculty_password_123', 'Dr. Bob Faculty')}
              disabled={!!quickLoginLoading}
              className="py-3 px-4 rounded-xl border border-purple-400/30 bg-purple-400/10 hover:bg-purple-400/20 text-purple-300 text-xs font-bold transition flex items-center justify-between disabled:opacity-50"
            >
              <span>{quickLoginLoading === 'faculty' ? 'Entering…' : 'Dr. Bob (Faculty)'}</span>
              <span className="text-[10px] bg-purple-400/20 px-2 py-0.5 rounded">+ INTERNAL</span>
            </button>
            <button
              onClick={() => handleQuickDemo('admin', 'admin@example.com', 'admin_password_123', 'Root Admin')}
              disabled={!!quickLoginLoading}
              className="py-3 px-4 rounded-xl border border-amber-400/30 bg-amber-400/10 hover:bg-amber-400/20 text-amber-300 text-xs font-bold transition flex items-center justify-between disabled:opacity-50"
            >
              <span>{quickLoginLoading === 'admin' ? 'Entering…' : 'Root Administrator'}</span>
              <span className="text-[10px] bg-amber-400/20 px-2 py-0.5 rounded">ALL TIERS</span>
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/10 py-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-cyan-400" />
          <span className="font-bold text-slate-400">VaultRAG Enterprise</span>
          <span>— Role-Based AI Knowledge Retrieval</span>
        </div>
        <div>
          <span>Zero Information Leakage • Physical Vector Partitioning • Built for Hackathon Excellence</span>
        </div>
      </footer>
    </div>
  );
}
