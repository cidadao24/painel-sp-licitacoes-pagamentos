async function loadJSON(path) {
  const response = await fetch(path);
  return await response.json();
}

async function init() {
  // Carregar dados processados
  const flags = await loadJSON("../data/processed/flags.json");
  const contratos = await loadJSON("../data/processed/fatos_contratos.json");

  // Gráfico Top fornecedores
  const top = (flags.top_fornecedores_contratados || []).map(item => {
    return {
      nome: item.nome || item.cnpj || "(desconhecido)",
      valor: item.total_contratado || 0
    };
  });
  const trace = {
    x: top.map(x => x.nome),
    y: top.map(x => x.valor),
    type: 'bar'
  };
  const layout = {
    margin: { t: 30 },
    yaxis: { title: 'Valor contratado (R$)' }
  };
  Plotly.newPlot('chart_top', [trace], layout, { displayModeBar: false });

  // Lista de contratos (primeiros 100)
  const listaEl = document.getElementById('lista');
  contratos.slice(0, 100).forEach(c => {
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `<strong>${c.fornecedor_nome || '(fornecedor não informado)'} — R$ ${c.valor_contratado.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong><br>
                      ${c.objeto || ''}<br>
                      <small>${c.orgao || ''} • Publicado em: ${c.data_publicacao || ''}</small>`;
    listaEl.appendChild(div);
  });
}

init().catch(err => {
  console.error('Erro ao inicializar o painel:', err);
});