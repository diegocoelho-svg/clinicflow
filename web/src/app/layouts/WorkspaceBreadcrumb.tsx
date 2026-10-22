import { Link, useMatch, useMatches, useSearchParams } from 'react-router';
import { useClinicDirectory } from '../../features/clinics/context';
import { findClinicSection } from '../../features/clinics/navigation';

export function WorkspaceBreadcrumb() {
  const clinicRoute = useMatch('/clinicas/:clinicId/*');
  const clinicId = clinicRoute?.params.clinicId;
  const [searchParams] = useSearchParams();
  const matches = useMatches();
  const params = matches.at(-1)?.params;
  const { clinics } = useClinicDirectory();
  const section = findClinicSection(
    clinicId ? clinicRoute?.params['*']?.split('/')[0] : searchParams.get('area'),
  );
  const crumbs = [{ label: 'Minhas clínicas', to: '/clinicas' }];
  if (clinicId) {
    const clinic = clinics.find((item) => String(item.id) === clinicId);
    crumbs.push({ label: clinic?.name ?? `Clínica #${clinicId}`, to: `/clinicas/${clinicId}` });
  }
  if (section) {
    crumbs.push({
      label: section.label,
      to: clinicId ? `/clinicas/${clinicId}/${section.path}` : `/clinicas?area=${section.path}`,
    });
  }
  if (params?.encounterId) {
    crumbs.push({
      label: `Atendimento #${params.encounterId}`,
      to: `/clinicas/${clinicId}/atendimentos/${params.encounterId}`,
    });
  } else if (params?.chargeId) {
    crumbs.push({
      label: `Cobrança #${params.chargeId}`,
      to: `/clinicas/${clinicId}/cobrancas/${params.chargeId}`,
    });
  }
  return (
    <nav className="breadcrumb" aria-label="Caminho de navegação">
      <ol>
        {crumbs.map((crumb, index) => (
          <li key={crumb.to}>
            {index === crumbs.length - 1 ? (
              <span aria-current="page">{crumb.label}</span>
            ) : (
              <Link to={crumb.to}>{crumb.label}</Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
