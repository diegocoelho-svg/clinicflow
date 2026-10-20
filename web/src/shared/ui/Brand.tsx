export function Brand({ light = false }: { light?: boolean }) {
  return (
    <div className={`brand ${light ? 'brand-light' : ''}`}>
      <span className="brand-mark" aria-hidden="true">
        ✚
      </span>
      <span>
        Clinic<span className="brand-flow">Flow</span>
        <small>ESPAÇO DA CLÍNICA</small>
      </span>
    </div>
  );
}
