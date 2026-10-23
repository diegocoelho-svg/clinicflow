import { createContext } from 'react';
import type { NoticeData } from '../../shared/ui/Notice';
import type { Credentials, Session } from './types';

export interface AuthContextValue {
  session: Session | null;
  notice: NoticeData | null;
  suggestedUsername: string;
  login: (credentials: Credentials, signal: AbortSignal) => Promise<boolean>;
  logout: () => void;
  expire: (token: string) => void;
  clearNotice: () => void;
  registrationSucceeded: (username: string) => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
