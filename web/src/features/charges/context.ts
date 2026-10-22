import { createContext, useContext } from 'react';
import type { Charge } from './types';

export type Issuance =
  | { key: string; status: 'pending' }
  | { key: string; status: 'uncertain' | 'rejected'; message: string }
  | { key: string; status: 'confirmed'; charge: Charge };

interface ChargeOperations {
  intents: ReadonlyMap<string, Issuance>;
  revision: number;
  issue: (clinic: number, encounter: number) => Promise<void>;
  refresh: () => void;
}

export const ChargeOperationsContext = createContext<ChargeOperations | null>(null);
export const issuanceScope = (clinic: number, encounter: number) => `${clinic}:${encounter}`;

export function useChargeOperations() {
  const context = useContext(ChargeOperationsContext);
  if (!context) throw new Error('Charge operations require their session-scoped provider');
  return context;
}
