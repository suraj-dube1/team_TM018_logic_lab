/**
 * API client for VaultRAG backend services.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: 'STUDENT' | 'FACULTY' | 'ADMIN';
  is_active: boolean;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  title: string;
  original_filename: string;
  source_type: string;
  security_level: 'PUBLIC' | 'INTERNAL' | 'CONFIDENTIAL';
  processing_status: 'UPLOADED' | 'PROCESSING' | 'READY' | 'PROCESSING_FAILED';
  file_size_bytes: number;
  uploaded_by: string;
  created_at: string;
}

export interface BatchUploadItemResult {
  filename: string;
  status: 'SUCCESS' | 'FAILED';
  document_id?: string;
  title?: string;
  chunk_count: number;
  error?: string;
}

export interface BatchUploadResponse {
  total_files: number;
  successful_count: number;
  failed_count: number;
  folder_name?: string;
  results: BatchUploadItemResult[];
}

export interface DocumentChunkItem {
  id: string;
  document_id: string;
  chunk_index: number;
  page_number: number;
  text: string;
  document_title: string;
  source_type: string;
  security_level: string;
}

export interface Citation {
  source_number: number;
  document_id: string;
  document_title: string;
  page_number: number;
  security_level: string;
  chunk_id: string;
  quote_excerpt: string;
}

export interface RAGResponse {
  question: string;
  answer: string;
  user_role: string;
  allowed_security_levels: string[];
  citations: Citation[];
  has_sufficient_context: boolean;
}

export interface AdminStats {
  total_users: number;
  total_documents: number;
  documents_by_level: Record<string, number>;
  total_queries: number;
  successful_accesses: number;
  denied_accesses: number;
  recent_events_count: number;
}

export interface AuditLogItem {
  id: string;
  timestamp: string;
  user_id: string | null;
  user_email: string | null;
  user_role: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  status: 'SUCCESS' | 'DENIED' | 'ERROR';
  details: string | null;
  ip_address: string | null;
}

function getToken(): string | null {
  return localStorage.getItem('vaultrag_token');
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorDetail = `Request failed (${res.status})`;
    try {
      const errorJson = await res.json();
      errorDetail = errorJson.detail || errorDetail;
    } catch {
      // Non-JSON error
    }
    if (res.status === 401) {
      localStorage.removeItem('vaultrag_token');
      window.dispatchEvent(new Event('vaultrag_unauthorized'));
      throw new Error('Your session has expired. Please sign in again.');
    }
    throw new Error(errorDetail);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json() as Promise<T>;
}

export const api = {
  health: {
    check: () => request<{ status: string; database: string; environment: string }>('/api/health'),
  },
  auth: {
    register: (name: string, email: string, password: string) =>
      request<UserProfile>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ name, email, password }),
      }),
    login: async (email: string, password: string) => {
      const data = await request<{ access_token: string; expires_in: number }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      localStorage.setItem('vaultrag_token', data.access_token);
      return data;
    },
    getMe: () => request<UserProfile>('/api/auth/me'),
    logout: () => {
      localStorage.removeItem('vaultrag_token');
    },
  },
  documents: {
    list: () => request<DocumentItem[]>('/api/documents'),
    get: (id: string) => request<DocumentItem>(`/api/documents/${id}`),
    getChunks: (id: string) => request<DocumentChunkItem[]>(`/api/documents/${id}/chunks`),
    upload: (file: File, title: string, security_level: string) => {
      const formData = new FormData();
      formData.append('file', file);
      if (title.trim()) formData.append('title', title.trim());
      formData.append('security_level', security_level);
      return request<DocumentItem>('/api/documents', {
        method: 'POST',
        body: formData,
      });
    },
    uploadBatch: (files: File[], security_level: string, folder_name?: string) => {
      const formData = new FormData();
      files.forEach((file) => {
        formData.append('files', file);
      });
      formData.append('security_level', security_level);
      if (folder_name?.trim()) formData.append('folder_name', folder_name.trim());
      return request<BatchUploadResponse>('/api/documents/batch', {
        method: 'POST',
        body: formData,
      });
    },
    delete: (id: string) =>
      request<void>(`/api/documents/${id}`, {
        method: 'DELETE',
      }),
    reclassify: (id: string, security_level: string) =>
      request<DocumentItem>(`/api/documents/${id}/classification`, {
        method: 'PATCH',
        body: JSON.stringify({ security_level }),
      }),
  },
  rag: {
    query: (question: string, top_k = 4, history: { role: string; content: string }[] = []) =>
      request<RAGResponse>('/api/rag/query', {
        method: 'POST',
        body: JSON.stringify({ question, top_k, history }),
      }),
  },
  admin: {
    getStats: () => request<AdminStats>('/api/admin/stats'),
    getUsers: () => request<UserProfile[]>('/api/admin/users'),
    updateUserRole: (userId: string, role: string, is_active?: boolean) =>
      request<UserProfile>(`/api/admin/users/${userId}/role`, {
        method: 'PATCH',
        body: JSON.stringify({ role, is_active }),
      }),
    getAuditLogs: (limit = 100, action?: string, status?: string) => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (action) params.append('action', action);
      if (status) params.append('status', status);
      return request<AuditLogItem[]>(`/api/audit?${params.toString()}`);
    },
  },
};
