import type { Resource } from '../hooks/useResource';
import { Notice } from './Notice';

export function ResourceMessage({
  state,
  label,
  retry,
}: {
  state: Resource<unknown>;
  label: string;
  retry: () => void;
}) {
  if (state.status === 'loading')
    return (
      <div className="loading" role="status">
        <span className="spinner" />
        Carregando {label}…
      </div>
    );
  if (state.status === 'error')
    return (
      <div className="resource-error">
        <Notice>{state.message}</Notice>
        <button className="button secondary" onClick={retry}>
          Tentar carregar novamente
        </button>
      </div>
    );
  return null;
}
