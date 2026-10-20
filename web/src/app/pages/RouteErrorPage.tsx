import { useEffect } from 'react';
import { useRouteError } from 'react-router';

export function RouteErrorPage() {
  useRouteError();
  useEffect(() => {
    document.title = 'ClinicFlow · Erro ao abrir a página';
    document.querySelector<HTMLElement>('[data-route-heading]')?.focus();
  }, []);

  return (
    <main className="route-message">
      <h1 tabIndex={-1} data-route-heading>
        Não foi possível abrir esta página
      </h1>
      <p>Tente recarregar a aplicação para continuar.</p>
      <a className="button primary" href="/entrar">
        Voltar ao início
      </a>
    </main>
  );
}
