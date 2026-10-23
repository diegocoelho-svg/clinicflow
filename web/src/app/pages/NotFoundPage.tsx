import { Link } from 'react-router';

export function NotFoundPage() {
  return (
    <main className="route-message">
      <span className="eyebrow">CLINICFLOW</span>
      <h1 tabIndex={-1} data-route-heading>
        Página não encontrada
      </h1>
      <p>Confira o endereço ou volte para suas clínicas.</p>
      <Link className="button primary" to="/clinicas">
        Ir para minhas clínicas
      </Link>
    </main>
  );
}
