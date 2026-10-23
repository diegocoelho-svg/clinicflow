import { createContext, useContext } from 'react';
import type { Clinic } from './types';

interface ClinicDirectoryValue {
  clinics: Clinic[];
  loading: boolean;
  error: string;
  reload: () => void;
  addClinic: (clinic: Clinic) => void;
  removeClinic: (id: number) => void;
}

export const ClinicDirectoryContext = createContext<ClinicDirectoryValue | null>(null);

export function useClinicDirectory() {
  const directory = useContext(ClinicDirectoryContext);
  if (!directory) throw new Error('Clinic directory requires ClinicDirectoryProvider');
  return directory;
}
