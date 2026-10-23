import type { ChargeItem } from '../charges/types';

export interface Encounter {
  id: number;
  clinic: number;
  patient: number;
  performed_at: string;
  description: string;
}
export interface EncounterItem extends ChargeItem {
  encounter: number;
}
export interface PatientSummary {
  id: number;
  full_name: string;
}
export interface Procedure {
  id: number;
  name: string;
  unit_price: string;
  is_active: boolean;
}
