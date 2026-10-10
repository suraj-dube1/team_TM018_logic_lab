import { Shield, ShieldAlert, ShieldCheck } from 'lucide-react';

export function RoleBadge({ role }: { role: string }) {
  switch (role) {
    case 'ADMIN':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-400/10 text-amber-300 border border-amber-400/20">
          <ShieldAlert size={12} />
          ADMIN
        </span>
      );
    case 'FACULTY':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-400/10 text-purple-300 border border-purple-400/20">
          <Shield size={12} />
          FACULTY
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-400/10 text-cyan-300 border border-cyan-400/20">
          <ShieldCheck size={12} />
          STUDENT
        </span>
      );
  }
}

export function SecurityLevelBadge({ level }: { level: string }) {
  switch (level) {
    case 'CONFIDENTIAL':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-rose-500/10 text-rose-300 border border-rose-500/25">
          CONFIDENTIAL
        </span>
      );
    case 'INTERNAL':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-sky-500/10 text-sky-300 border border-sky-500/25">
          INTERNAL
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/25">
          PUBLIC
        </span>
      );
  }
}

export function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'READY':
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <span className="size-1.5 rounded-full bg-emerald-400" />
          READY
        </span>
      );
    case 'PROCESSING_FAILED':
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
          <span className="size-1.5 rounded-full bg-rose-400" />
          FAILED
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" />
          PROCESSING
        </span>
      );
  }
}
