import { useMemo } from 'react';
import type { RequestAuth } from '../../../shared/api/http';
import { useAuth } from '../../auth/useAuth';

export function useClinicAccess(): RequestAuth {
  const { session, expire } = useAuth();
  if (!session) throw new Error('Clinic access requires an authenticated route');
  return useMemo(() => ({ token: session.token, onUnauthorized: expire }), [session.token, expire]);
}
