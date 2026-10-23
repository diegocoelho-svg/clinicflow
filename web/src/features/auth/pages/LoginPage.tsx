import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { useAsyncForm } from '../../../shared/hooks/useAsyncForm';
import { Field } from '../../../shared/ui/Field';
import { Notice } from '../../../shared/ui/Notice';
import { useAuth } from '../useAuth';

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const form = useAsyncForm();
  const [username, setUsername] = useState(auth.suggestedUsername);
  const [password, setPassword] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = await form.submit((signal) =>
      auth.login({ username: username.trim(), password }, signal),
    );
    setPassword('');
    if (result?.data) void navigate('/clinicas', { replace: true });
  }

  return (
    <>
      <span className="eyebrow">BEM-VINDO DE VOLTA</span>
      <h1 id="auth-title" tabIndex={-1} data-route-heading>
        Entre no ClinicFlow
      </h1>
      <p className="muted">Acesse sua conta para escolher sua clínica e continuar.</p>
      {auth.notice && (
        <Notice kind={auth.notice.kind} routeAlert={auth.notice.routeAlert}>
          {auth.notice.message}
        </Notice>
      )}
      {form.error && <Notice>{form.error}</Notice>}
      <form onSubmit={submit} aria-busy={form.pending}>
        <fieldset disabled={form.pending}>
          <Field
            label="Usuário"
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
            maxLength={150}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            error={form.fields.username}
          />
          <Field
            label="Senha"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            maxLength={1024}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={form.fields.password}
          />
          <button className="button primary full" type="submit">
            {form.pending ? 'Entrando…' : 'Entrar'}
            <span aria-hidden="true">→</span>
          </button>
        </fieldset>
      </form>
      <p className="auth-switch">
        Primeiro acesso?{' '}
        <Link className="text-button" to="/cadastro" onClick={auth.clearNotice}>
          Criar uma conta
        </Link>
      </p>
      <p className="session-note">
        Por enquanto, sua sessão fica apenas nesta aba.
        <br />
        Ao atualizar a página, entre novamente.
      </p>
    </>
  );
}
