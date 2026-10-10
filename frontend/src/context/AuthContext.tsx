import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, type UserProfile } from '../services/api';

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  register: (name: string, email: string, pass: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('vaultrag_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshUser = async () => {
    try {
      const profile = await api.auth.getMe();
      setUser(profile);
    } catch {
      setUser(null);
      setToken(null);
      api.auth.logout();
    }
  };

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null);
      setToken(null);
    };
    window.addEventListener('vaultrag_unauthorized', handleUnauthorized);

    const initializeAuth = async () => {
      const storedToken = localStorage.getItem('vaultrag_token');
      if (storedToken) {
        setToken(storedToken);
        await refreshUser();
      }
      setIsLoading(false);
    };
    initializeAuth();

    return () => {
      window.removeEventListener('vaultrag_unauthorized', handleUnauthorized);
    };
  }, []);

  const login = async (email: string, pass: string) => {
    const data = await api.auth.login(email, pass);
    setToken(data.access_token);
    await refreshUser();
  };

  const register = async (name: string, email: string, pass: string) => {
    await api.auth.register(name, email, pass);
    await login(email, pass);
  };

  const logout = () => {
    api.auth.logout();
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
