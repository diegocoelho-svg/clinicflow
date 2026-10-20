export function ClinicIndexPage() {
  return (
    <section className="panel selected-panel" aria-labelledby="selected-heading">
      <div className="panel-heading">
        <span className="eyebrow">ESPAÇO DA CLÍNICA</span>
      </div>
      <div className="workspace-empty">
        <div className="workspace-clinic-icon" aria-hidden="true">
          ✚
        </div>
        <h2 id="selected-heading">Um espaço para cada clínica</h2>
        <p>Selecione uma clínica na lista ao lado para consultar seus dados e começar por aqui.</p>
        <span className="empty-footnote">Seu acesso é confirmado a cada seleção.</span>
      </div>
    </section>
  );
}
