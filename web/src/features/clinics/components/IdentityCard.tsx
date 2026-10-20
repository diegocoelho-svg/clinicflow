import { useAuth } from '../../auth/useAuth';

export function IdentityCard() {
  const user = useAuth().session!.user;
  return (
    <section className="identity-panel" aria-labelledby="identity-heading">
      <span className="identity-icon" aria-hidden="true">
        ◎
      </span>
      <div>
        <span className="eyebrow">CONECTADO COMO</span>
        <h2 id="identity-heading">
          {user.first_name} {user.last_name}
        </h2>
        <p>{user.email}</p>
        <small>Conta @{user.username}</small>
      </div>
    </section>
  );
}
