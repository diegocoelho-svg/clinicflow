import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { useAsyncForm } from '../../../shared/hooks/useAsyncForm';
import { Field } from '../../../shared/ui/Field';
import { Notice } from '../../../shared/ui/Notice';
import { authApi } from '../api';
import { useAuth } from '../useAuth';

export function RegisterPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const form = useAsyncForm();
  const [password, setPassword] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const username = String(values.get('username')).trim();
    const result = await form.submit((signal) =>
      authApi.register(
        {
          username,
          password,
          first_name: String(values.get('first_name')).trim(),
          last_name: String(values.get('last_name')).trim(),
          email: String(values.get('email')).trim(),
        },
        signal,
      ),
    );
    setPassword('');
    if (result) {
      auth.registrationSucceeded(username);
      void navigate('/entrar', { replace: true });
    }
  }

  return (
    <>
      <span className="eyebrow">VAMOS COMEÇAR</span>
      <h1 id="auth-title" tabIndex={-1} data-route-heading>
        Crie sua conta
      </h1>
      <p className="muted">Preencha seus dados para começar a organizar suas clínicas.</p>
      {form.error && <Notice>{form.error}</Notice>}
      <form onSubmit={submit} aria-busy={form.pending}>
        <fieldset disabled={form.pending}>
          <div className="field-row">
            <Field
              label="Nome"
              name="first_name"
              autoComplete="given-name"
              required
              maxLength={150}
              error={form.fields.first_name}
            />
            <Field
              label="Sobrenome"
              name="last_name"
              autoComplete="family-name"
              required
              maxLength={150}
              error={form.fields.last_name}
            />
          </div>
          <Field
            label="E-mail"
            name="email"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            error={form.fields.email}
          />
          <Field
            label="Usuário"
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
            maxLength={150}
            error={form.fields.username}
          />
          <Field
            label="Senha"
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={1024}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={form.fields.password}
            hint="Use ao menos 8 caracteres. Evite senhas comuns, apenas números ou seus dados pessoais."
          />
          <button className="button primary full" type="submit">
            {form.pending ? 'Criando conta…' : 'Criar conta'}
            <span aria-hidden="true">→</span>
          </button>
        </fieldset>
      </form>
      <p className="auth-switch">
        Já tem uma conta?{' '}
        <Link className="text-button" to="/entrar" onClick={auth.clearNotice}>
          Entrar na conta
        </Link>
      </p>
    </>
  );
}
