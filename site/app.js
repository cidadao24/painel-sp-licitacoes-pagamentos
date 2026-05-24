async function loadJSON(path) {
  const response = await fetch(path, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return await response.json();
}

function card(html) {
  return `<div class='card'>${html}</div>`;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString('pt-BR');
}

function renderStatus(listaEl, flags) {
  const raw = flags.raw_contracts_loaded || flags.fetch_status?.contracts_collected || 0;
  const filtered = flags.contracts_after_filter || 0;
  const failedChunks = flags.fetch_status?.failed_chunks;
  const totalChunks = flags.fetch_status?.total_chunks;
  const partial = flags.fetch_partial || flags.fetch_status?.partial;

  let html = '';
  if (partial) {
    html += card(`<strong>Coleta PNCP parcial.</strong><br>Foram coletados ${formatNumber(raw)} contratos brutos. ${failedChunks ?? '?'} de ${totalChunks ?? '?'} blocos tiveram falha ou resposta parcial.`);
  }
  if (raw > 0 && filtered === 0) {
    html += card(`<strong>Dados coletados, mas nenhum contrato passou pelo filtro de São Paulo.</strong><br>O problema atual não é falta total de coleta: o backend trouxe ${formatNumber(raw)} contratos brutos, mas o filtro municipal retornou 0. O filtro PNCP precisa ser ajustado aos campos reais retornados pela API.`);
  }
  if (flags.warning) {
    html += card(`<strong>Aviso técnico:</strong><br>${flags.warning}`);
  }
  return html;
}

async function init() {
  const listaEl = document.getElementById('lista');
  const chartEl = document.getElementById('chart_top');
  let flags, contratos;
  try {
    flags = await loadJSON("../data/processed/flags.json");
    contratos = await loadJSON("../data/processed/fatos_contratos.json");
  } catch (err) {
    console.error("Falha ao carregar arquivos de dados:", err);
    listaEl.innerHTML = card("Erro ao carregar dados. Tente novamente mais tarde.");
    if (chartEl) chartEl.innerHTML = card("Gráfico indisponível: arquivos de dados não carregaram.");
    return;
  }

  if (flags && flags.fetch_failed) {
    listaEl.innerHTML = card("Erro ao coletar dados do PNCP. Tente novamente mais tarde.") + renderStatus(listaEl, flags);
    if (chartEl) chartEl.innerHTML = card("Gráfico indisponível por falha de coleta.");
    return;
  }

  if (!contratos || contratos.length === 0) {
    listaEl.innerHTML = renderStatus(listaEl, flags) || card("Sem publicações no período selecionado.");
    if (chartEl) chartEl.innerHTML = card("Sem dados suficientes para gerar o gráfico.");
    return;
  }

  const top = (flags.top_fornecedores_contratados || []).map(item => ({
    nome: item.nome || item.cnpj || "(desconhecido)",
    valor: item.total_contratado || 0
  }));

  if (top.length > 0) {
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
  } else if (chartEl) {
    chartEl.innerHTML = card("Sem fornecedores agregados para exibir.");
  }

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