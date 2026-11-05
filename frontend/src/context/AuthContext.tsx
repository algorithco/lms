import { AuthProvider, useAuth as useBaseAuth } from '../auth/AuthContext';
import type { AuthUser } from '../lib/api';

export { AuthProvider };

export function useAuth() {
  const ctx = useBaseAuth();
  return {
    ...ctx,
    updateUser: (partial: Partial<AuthUser>) => ctx.updateUserLocal(partial),
  };
}
