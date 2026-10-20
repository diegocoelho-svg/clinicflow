import { Navigate, Outlet } from 'react-router';
import { useAuth } from './useAuth';

export function RequireSession() {
  return useAuth().session ? <Outlet /> : <Navigate to="/entrar" replace />;
}
