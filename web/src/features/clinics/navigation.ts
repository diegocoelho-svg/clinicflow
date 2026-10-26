export const clinicSections = [
  { path: 'atendimentos', label: 'Atendimentos', icon: '▤' },
  { path: 'pacientes', label: 'Pacientes', icon: '♧' },
  { path: 'procedimentos', label: 'Procedimentos e preços', icon: '＋' },
  { path: 'cobrancas', label: 'Cobranças', icon: '$' },
  { path: 'pagamentos', label: 'Pagamentos', icon: '✓' },
] as const;

export function findClinicSection(path: string | null | undefined) {
  return clinicSections.find((section) => section.path === path);
}
