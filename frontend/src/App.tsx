import { useEffect, useState } from 'react'
import { ArrowUpRight, FileLock2, Fingerprint, ShieldCheck } from 'lucide-react'

type Health = { status: string; database: string; environment: string }

const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${apiBase}/api/health`)
      .then(async (response) => {
        if (!response.ok) throw new Error('API is not ready')
        return response.json() as Promise<Health>
      })
      .then(setHealth)
      .catch(() => setError('Backend unavailable. Start the API and refresh this page.'))
  }, [])

  return (
    <main className="min-h-screen bg-[#07111f] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-6 py-7 lg:px-12">
        <header className="flex items-center justify-between border-b border-white/10 pb-6">
          <a className="flex items-center gap-3" href="/" aria-label="Secure RAG home">
            <span className="grid size-10 place-items-center rounded-xl bg-cyan-300 text-slate-950"><ShieldCheck size={22} /></span>
            <span><span className="block text-sm font-semibold tracking-wide">NORTHSTAR</span><span className="text-xs text-slate-400">SECURE KNOWLEDGE</span></span>
          </a>
          <span className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300">LOCAL ENVIRONMENT</span>
        </header>

        <section className="grid flex-1 items-center gap-14 py-16 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/5 px-3 py-1.5 text-xs text-cyan-200"><span className="size-1.5 rounded-full bg-cyan-300" /> Permission-aware document intelligence</div>
            <h1 className="max-w-3xl text-5xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">Answers grounded in the documents you’re <span className="text-cyan-300">allowed to see.</span></h1>
            <p className="mt-6 max-w-xl text-lg leading-8 text-slate-400">A secure workspace for searching institutional knowledge, with access controls applied before retrieval and citations attached to every answer.</p>
            <div className="mt-9 flex flex-wrap gap-3">
              <button className="inline-flex items-center gap-2 rounded-lg bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200">Open workspace <ArrowUpRight size={17} /></button>
              <button className="rounded-lg border border-white/15 px-5 py-3 text-sm font-medium text-slate-200 hover:bg-white/5">Explore security model</button>
            </div>
            <div className="mt-12 flex flex-wrap gap-x-8 gap-y-3 text-sm text-slate-400"><span className="flex items-center gap-2"><Fingerprint size={16} className="text-cyan-300" /> Identity-aware access</span><span className="flex items-center gap-2"><FileLock2 size={16} className="text-cyan-300" /> Protected retrieval</span></div>
          </div>

          <aside className="rounded-2xl border border-white/10 bg-[#0d1a2b] p-6 shadow-2xl shadow-black/20">
            <div className="flex items-start justify-between"><div><p className="text-sm font-medium text-slate-300">System status</p><p className="mt-1 text-xs text-slate-500">Local services overview</p></div><span className="rounded-md border border-white/10 px-2 py-1 text-[10px] tracking-wider text-slate-400">PHASE 1</span></div>
            <div className="mt-6 space-y-3">
              <StatusRow name="API service" value={health ? 'Operational' : error ? 'Unavailable' : 'Checking…'} good={Boolean(health)} />
              <StatusRow name="Database" value={health?.database === 'ok' ? 'Connected' : health ? 'Unavailable' : 'Checking…'} good={health?.database === 'ok'} />
              <StatusRow name="Environment" value={health?.environment ?? 'Local development'} good={Boolean(health)} />
            </div>
            {error && <p role="status" className="mt-4 rounded-lg border border-amber-400/20 bg-amber-400/5 p-3 text-sm text-amber-200">{error}</p>}
            <div className="mt-6 rounded-xl border border-white/10 bg-[#091422] p-4"><p className="text-xs font-medium uppercase tracking-wider text-slate-500">Access policy</p><div className="mt-3 flex items-center gap-2 text-sm text-slate-300"><ShieldCheck size={16} className="text-emerald-300" /> Enforced in the retrieval layer</div></div>
          </aside>
        </section>

        <footer className="flex flex-wrap justify-between gap-3 border-t border-white/10 py-5 text-xs text-slate-500"><span>Secure RAG · Local development</span><span>Documents stay under your access policy</span></footer>
      </div>
    </main>
  )
}

function StatusRow({ name, value, good }: { name: string; value: string; good: boolean }) {
  return <div className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.025] px-4 py-3"><span className="text-sm text-slate-400">{name}</span><span className="flex items-center gap-2 text-sm text-slate-200"><span className={`size-1.5 rounded-full ${good ? 'bg-emerald-300' : 'bg-slate-500'}`} />{value}</span></div>
}
