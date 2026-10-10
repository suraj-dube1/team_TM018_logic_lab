import { useEffect, useRef, useState } from 'react';
import {
  FileText,
  Layers,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
  X,
  FileCheck,
  Folder,
  FolderPlus,
  FolderUp,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { SecurityLevelBadge, StatusBadge } from '../components/Badges';
import { api, type DocumentChunkItem, type DocumentItem } from '../services/api';

export function DocumentsView() {
  const { user } = useAuth();
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadMode, setUploadMode] = useState<'file' | 'folder'>('file');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadLevel, setUploadLevel] = useState<string>('PUBLIC');
  const [uploading, setUploading] = useState(false);

  // Folder & batch state
  const [folderFiles, setFolderFiles] = useState<File[]>([]);
  const [folderName, setFolderName] = useState('');
  const [batchSummary, setBatchSummary] = useState<{ total: number; success: number; failed: number } | null>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const zipInputRef = useRef<HTMLInputElement>(null);

  // Chunk inspector modal state
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [chunks, setChunks] = useState<DocumentChunkItem[]>([]);
  const [loadingChunks, setLoadingChunks] = useState(false);

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const data = await api.documents.list();
      setDocs(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleFolderSelect = (filesList: FileList | null) => {
    if (!filesList || filesList.length === 0) return;
    const files = Array.from(filesList);
    setFolderFiles(files);

    // Extract folder name from relative path if available
    const firstRel = (files[0] as unknown as { webkitRelativePath?: string }).webkitRelativePath || '';
    if (firstRel) {
      const detected = firstRel.split('/')[0];
      if (detected && !folderName) {
        setFolderName(detected);
      }
    } else if (!folderName) {
      setFolderName('Imported_Folder');
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();

    if (uploadMode === 'file') {
      if (!uploadFile) return;
      setUploading(true);
      try {
        await api.documents.upload(uploadFile, uploadTitle, uploadLevel);
        setIsUploadOpen(false);
        setUploadFile(null);
        setUploadTitle('');
        setUploadLevel('PUBLIC');
        await fetchDocs();
      } catch (err: unknown) {
        alert(err instanceof Error ? err.message : 'Upload failed');
      } finally {
        setUploading(false);
      }
    } else {
      // Folder batch upload
      if (folderFiles.length === 0) return;
      setUploading(true);
      try {
        const res = await api.documents.uploadBatch(folderFiles, uploadLevel, folderName || 'Imported_Folder');
        setBatchSummary({
          total: res.total_files,
          success: res.successful_count,
          failed: res.failed_count,
        });
        await fetchDocs();
        setTimeout(() => {
          setIsUploadOpen(false);
          setFolderFiles([]);
          setFolderName('');
          setBatchSummary(null);
        }, 1800);
      } catch (err: unknown) {
        alert(err instanceof Error ? err.message : 'Folder upload failed');
      } finally {
        setUploading(false);
      }
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to permanently delete this document and its vector embeddings?')) return;
    try {
      await api.documents.delete(id);
      await fetchDocs();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const handleInspectChunks = async (doc: DocumentItem) => {
    setSelectedDoc(doc);
    setLoadingChunks(true);
    try {
      const chunkData = await api.documents.getChunks(doc.id);
      setChunks(chunkData);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to retrieve chunks');
    } finally {
      setLoadingChunks(false);
    }
  };

  const handleReclassify = async (docId: string, newLevel: string) => {
    try {
      await api.documents.reclassify(docId, newLevel);
      await fetchDocs();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Reclassification failed');
    }
  };

  // Determine permitted classification levels for this user
  const allowedUploadLevels =
    user?.role === 'ADMIN'
      ? ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL']
      : user?.role === 'FACULTY'
      ? ['PUBLIC', 'INTERNAL']
      : ['PUBLIC'];

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Document Vault</h1>
          <p className="text-xs text-slate-400 mt-1">
            Displaying documents matching your permission level ({allowedUploadLevels.join(', ')})
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchDocs}
            className="p-2.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 transition"
            title="Refresh"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => {
              setUploadMode('file');
              setIsUploadOpen(true);
            }}
            className="px-3.5 py-2.5 rounded-lg bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-semibold text-xs flex items-center gap-2 shadow-lg shadow-cyan-400/10 transition"
          >
            <Plus size={16} />
            <span>Upload File</span>
          </button>
          <button
            onClick={() => {
              setUploadMode('folder');
              setIsUploadOpen(true);
            }}
            className="px-3.5 py-2.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-400/30 font-semibold text-xs flex items-center gap-2 shadow-lg transition"
          >
            <FolderPlus size={16} />
            <span>Upload Folder</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300">
          {error}
        </div>
      )}

      {/* Documents Table */}
      <div className="bg-[#0d1a2b] border border-white/10 rounded-2xl shadow-xl overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-xs text-slate-400">Loading documents…</div>
        ) : docs.length === 0 ? (
          <div className="p-16 text-center space-y-3">
            <div className="size-12 rounded-2xl bg-white/5 border border-white/10 mx-auto grid place-items-center text-slate-400">
              <FileText size={24} />
            </div>
            <h3 className="text-sm font-semibold text-white">No documents available</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              No documents exist within your security authorization level yet. Upload a document to start indexing.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#07111f] border-b border-white/10 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-5 py-3.5">Title & Source</th>
                  <th className="px-4 py-3.5">Security Level</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-4 py-3.5">File Size</th>
                  <th className="px-4 py-3.5">Date Added</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-200">
                {docs.map((d) => (
                  <tr key={d.id} className="hover:bg-white/[0.02] transition">
                    <td className="px-5 py-4">
                      <div className="font-semibold text-white">{d.title}</div>
                      <div className="text-[11px] text-slate-400">{d.original_filename} ({d.source_type})</div>
                    </td>
                    <td className="px-4 py-4">
                      {user?.role === 'ADMIN' ? (
                        <select
                          value={d.security_level}
                          onChange={(e) => handleReclassify(d.id, e.target.value)}
                          className="bg-[#07111f] border border-white/15 rounded px-2 py-1 text-xs text-white"
                        >
                          <option value="PUBLIC">PUBLIC</option>
                          <option value="INTERNAL">INTERNAL</option>
                          <option value="CONFIDENTIAL">CONFIDENTIAL</option>
                        </select>
                      ) : (
                        <SecurityLevelBadge level={d.security_level} />
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <StatusBadge status={d.processing_status} />
                    </td>
                    <td className="px-4 py-4 text-slate-400">
                      {(d.file_size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="px-4 py-4 text-slate-400">
                      {new Date(d.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <div className="inline-flex items-center gap-2">
                        <button
                          onClick={() => handleInspectChunks(d)}
                          className="px-2.5 py-1.5 rounded-lg bg-cyan-400/10 hover:bg-cyan-400/20 text-cyan-300 font-medium text-[11px] transition flex items-center gap-1"
                        >
                          <Layers size={12} />
                          <span>Chunks</span>
                        </button>
                        {(user?.role === 'ADMIN' || user?.id === d.uploaded_by) && (
                          <button
                            onClick={() => handleDelete(d.id)}
                            className="p-1.5 rounded-lg hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 transition"
                            title="Delete"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm grid place-items-center p-4">
          <div className="bg-[#0d1a2b] border border-white/10 rounded-2xl w-full max-w-md p-6 shadow-2xl relative">
            <button
              onClick={() => setIsUploadOpen(false)}
              className="absolute right-4 top-4 text-slate-400 hover:text-white"
            >
              <X size={18} />
            </button>
            <div className="flex items-center gap-3 mb-4">
              <div className="size-9 rounded-xl bg-cyan-400/10 text-cyan-300 grid place-items-center">
                {uploadMode === 'file' ? <Upload size={18} /> : <FolderUp size={18} />}
              </div>
              <div>
                <h2 className="text-base font-bold text-white">
                  {uploadMode === 'file' ? 'Upload Single Document' : 'Upload Document Folder'}
                </h2>
                <p className="text-[11px] text-slate-400">
                  {uploadMode === 'file'
                    ? 'Upload an individual PDF, PNG, JPG, or TXT file'
                    : 'Ingest an entire directory or .zip archive of documents'}
                </p>
              </div>
            </div>

            {/* Mode Tabs */}
            <div className="flex p-1 mb-4 rounded-xl bg-[#07111f] border border-white/10">
              <button
                type="button"
                onClick={() => setUploadMode('file')}
                className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition ${
                  uploadMode === 'file'
                    ? 'bg-cyan-400 text-slate-950 shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <FileText size={14} />
                <span>Single File</span>
              </button>
              <button
                type="button"
                onClick={() => setUploadMode('folder')}
                className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition ${
                  uploadMode === 'folder'
                    ? 'bg-cyan-400 text-slate-950 shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Folder size={14} />
                <span>Folder / Directory</span>
              </button>
            </div>

            {/* Success notification */}
            {batchSummary && (
              <div className="mb-4 p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
                <CheckCircle2 size={16} className="shrink-0" />
                <span>
                  Successfully indexed {batchSummary.success} of {batchSummary.total} documents into the vault!
                </span>
              </div>
            )}

            <form onSubmit={handleUpload} className="space-y-4">
              {uploadMode === 'file' ? (
                <>
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Select File (PDF, PNG, JPG, TXT, MD)
                    </label>
                    <input
                      type="file"
                      required
                      accept=".pdf,.png,.jpg,.jpeg,.txt,.md"
                      onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                      className="w-full text-xs text-slate-300 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-cyan-400 file:text-slate-950 hover:file:bg-cyan-300"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">Title (Optional)</label>
                    <input
                      type="text"
                      value={uploadTitle}
                      onChange={(e) => setUploadTitle(e.target.value)}
                      placeholder="e.g. Student Handbook 2026"
                      className="w-full bg-[#07111f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-400"
                    />
                  </div>
                </>
              ) : (
                <>
                  {/* Folder Mode Inputs */}
                  <input
                    ref={folderInputRef}
                    type="file"
                    className="hidden"
                    // @ts-expect-error webkitdirectory is standard for folder picker
                    webkitdirectory=""
                    directory=""
                    multiple
                    onChange={(e) => handleFolderSelect(e.target.files)}
                  />
                  <input
                    ref={zipInputRef}
                    type="file"
                    className="hidden"
                    accept=".zip"
                    onChange={(e) => handleFolderSelect(e.target.files)}
                  />

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Select Folder or ZIP Archive
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => folderInputRef.current?.click()}
                        className="p-3 rounded-xl bg-[#07111f] hover:bg-[#0c1c33] border border-white/10 text-left transition flex flex-col gap-1 text-slate-200"
                      >
                        <div className="flex items-center gap-1.5 text-cyan-300 text-xs font-semibold">
                          <Folder size={14} />
                          <span>Select Folder</span>
                        </div>
                        <span className="text-[10px] text-slate-400">Choose entire directory</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => zipInputRef.current?.click()}
                        className="p-3 rounded-xl bg-[#07111f] hover:bg-[#0c1c33] border border-white/10 text-left transition flex flex-col gap-1 text-slate-200"
                      >
                        <div className="flex items-center gap-1.5 text-cyan-300 text-xs font-semibold">
                          <Layers size={14} />
                          <span>Upload .ZIP</span>
                        </div>
                        <span className="text-[10px] text-slate-400">Compressed folder</span>
                      </button>
                    </div>

                    {folderFiles.length > 0 && (
                      <div className="mt-3 p-3 rounded-xl bg-cyan-950/30 border border-cyan-400/20 text-xs text-slate-300 space-y-1.5">
                        <div className="flex items-center justify-between font-semibold text-cyan-300">
                          <span>Detected: {folderFiles.length} file(s)</span>
                          <span className="text-[10px] text-slate-400">Ready to ingest</span>
                        </div>
                        <div className="max-h-24 overflow-y-auto space-y-1 text-[11px] text-slate-400">
                          {folderFiles.slice(0, 5).map((f, i) => (
                            <div key={i} className="truncate flex items-center gap-1.5">
                              <FileCheck size={12} className="text-cyan-400 shrink-0" />
                              <span className="truncate">{f.name}</span>
                            </div>
                          ))}
                          {folderFiles.length > 5 && (
                            <div className="text-[10px] text-slate-500 italic">
                              + {folderFiles.length - 5} more files in folder
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">Folder Name (Optional)</label>
                    <input
                      type="text"
                      value={folderName}
                      onChange={(e) => setFolderName(e.target.value)}
                      placeholder="e.g. Engineering_Docs"
                      className="w-full bg-[#07111f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-400"
                    />
                  </div>
                </>
              )}

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Security Classification {uploadMode === 'folder' && '(Applied to all files in folder)'}
                </label>
                <select
                  value={uploadLevel}
                  onChange={(e) => setUploadLevel(e.target.value)}
                  className="w-full bg-[#07111f] border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-400"
                >
                  {allowedUploadLevels.map((lvl) => (
                    <option key={lvl} value={lvl}>
                      {lvl}
                    </option>
                  ))}
                </select>
                <p className="text-[10px] text-slate-400 mt-1">
                  Based on your role ({user?.role}), you may classify up to {allowedUploadLevels[allowedUploadLevels.length - 1]}.
                </p>
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsUploadOpen(false);
                    setFolderFiles([]);
                  }}
                  className="px-4 py-2 rounded-lg border border-white/10 text-xs text-slate-300 hover:bg-white/5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || (uploadMode === 'file' ? !uploadFile : folderFiles.length === 0)}
                  className="px-4 py-2 rounded-lg bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-semibold text-xs disabled:opacity-50 flex items-center gap-2"
                >
                  {uploading ? (
                    'Processing & Indexing…'
                  ) : uploadMode === 'file' ? (
                    'Upload & Process'
                  ) : (
                    `Ingest Folder (${folderFiles.length} files)`
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Chunks Inspector Modal */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm grid place-items-center p-4">
          <div className="bg-[#0d1a2b] border border-white/10 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col p-6 shadow-2xl relative">
            <button
              onClick={() => setSelectedDoc(null)}
              className="absolute right-4 top-4 text-slate-400 hover:text-white"
            >
              <X size={18} />
            </button>
            <div className="mb-4">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Layers size={18} className="text-cyan-400" />
                <span>Chunk Inspector: {selectedDoc.title}</span>
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Showing {chunks.length} page-aware searchable chunks indexed in FAISS
              </p>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-2">
              {loadingChunks ? (
                <div className="p-8 text-center text-xs text-slate-400">Loading indexed chunks…</div>
              ) : chunks.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-400">No chunks found for this document.</div>
              ) : (
                chunks.map((c) => (
                  <div key={c.id} className="p-3.5 rounded-xl bg-[#07111f] border border-white/10 text-xs space-y-1">
                    <div className="flex items-center justify-between font-semibold text-slate-300">
                      <span>Chunk #{c.chunk_index + 1} (Page {c.page_number})</span>
                      <SecurityLevelBadge level={c.security_level} />
                    </div>
                    <p className="text-slate-400 whitespace-pre-wrap">{c.text}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
