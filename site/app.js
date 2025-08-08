async function loadJSON(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return await response.json();
}

async function init() {
  const listaEl = document.getElementById('lista');
  let flags, contratos;
  try {
    flags = await loadJSON("../data/processed/flags.json");
    contratos = await loadJSON("../data/processed/fatos_contratos.json");
  } catch (err) {
    console.error("Falha ao carregar arquivos de dados:", err);
    // Erro ao carregar dados (por exemplo, 404 ou rede). Não exibimos "sem publicações".
    listaEl.innerHTML = "<div class='card'>Erro ao carregar dados. Tente novamente mais tarde.</div>";
    return;
  }
  // Se a coleta falhou no backend, sinalizado em flags
  if (flags && flags.fetch_failed) {
    listaEl.innerHTML = "<div class='card'>Erro ao coletar dados do PNCP. Tente novamente mais tarde.</div>";
    return;
  }
  // Se não há contratos no período, informar ausência de publicações
  if (!contratos || contratos.length === 0) {
    listaEl.innerHTML = "<div class='card'>Sem publicações no período selecionado.</div>";
    return;
  }
  // Gráfico Top fornecedores
  const top = (flags.top_fornecedores_contratados || []).map(item => ({
    nome: item.nome || item.cnpj || "(desconhecido)",
    valor: item.total_contratado || 0
  }));
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
  contratos.slice(0, 100).forEach(c => {
    const div = document.createElement('div');
    div.className = 'card';
    const valor = (c.valor_contratado || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    div.innerHTML = `<strong>${c.fornecedor_nome || '(fornecedor não informado)'} — R$ ${valor}</strong><br>
                      ${c.objeto || ''}<br>
                      <small>${c.orgao || ''} • Publicado em: ${c.data_publicacao || ''}</small>`;
    listaEl.appendChild(div);
  });
}

init().catch(err => {
  console.error('Erro ao inicializar o painel:', err);
});