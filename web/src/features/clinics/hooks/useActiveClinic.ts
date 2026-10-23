import { useOutletContext } from 'react-router';
import type { Clinic } from '../types';

export function useActiveClinic(): Clinic {
  const context = useOutletContext<{ clinic: Clinic }>();
  if (!context?.clinic) throw new Error('Clinic operation routes require verified clinic access');
  return context.clinic;
}
