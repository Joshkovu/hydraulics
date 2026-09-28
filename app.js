const operationOptions = {
  uf: [['critical_depth', 'Critical depth'], ['critical_slope', 'Critical slope'], ['normal_depth', 'Normal depth'], ['froude', 'Froude number'], ['specific_energy', 'Specific energy'], ['general', 'General analysis']],
  weirs: [['transitions', 'Flow transitions'], ['gvf', 'GVF step method']],
  jumps: [['conjugate', 'Conjugate depth']],
  contractions: [['far_upstream', 'Far-upstream depth'], ['critical', 'Critical narrow section'], ['bed_change', 'Bed changes']],
  depressions: [['no_weir', 'Depression without weir'], ['with_weir', 'Depression with weir']]
};

const shape = document.querySelector('#shape');
const category = document.querySelector('#category');
const operation = document.querySelector('#operation');
const fields = document.querySelector('#dynamic-fields');
const form = document.querySelector('#analysis-form');
const resultArea = document.querySelector('#result-area');
const resultTitle = document.querySelector('#result-title');
const resultTag = document.querySelector('#result-tag');
const badge = document.querySelector('#shape-badge');

function inputField(name, label, type = 'number', extra = '') {
  return `<label>${label}<input name="${name}" type="${type}" ${type === 'number' ? 'step="any" min="0"' : ''} ${extra}></label>`;
}

function baseFields() {
  const unitAllowed = ['rectangular', 'wide_rectangular'].includes(shape.value);
  const discharge = `<label>Discharge basis<select name="discharge_kind" id="discharge-kind"><option value="Q">Total discharge Q</option>${unitAllowed ? '<option value="q">Unit discharge q</option>' : ''}</select></label>${inputField('discharge', 'Discharge value')}`;
  let geometry = '';
  if (shape.value === 'rectangular' || shape.value === 'wide_rectangular') geometry = inputField('b', 'Bed width b');
  if (shape.value === 'triangular') geometry = inputField('theta', 'Semi-vertical angle θ', 'number', 'placeholder="degrees"');
  if (shape.value === 'trapezoidal') geometry = inputField('b', 'Bottom width b') + inputField('z', 'Side slope z (H:V)');
  if (shape.value === 'circular' || shape.value === 'semi_circular') geometry = inputField('d', 'Diameter d');
  return discharge + geometry;
}

function roughnessFields() { return `<div class="inline-fields"><label>Roughness law<select name="resistance_kind"><option value="n">Manning n</option><option value="C">Chezy C</option></select></label>${inputField('roughness', 'Coefficient')}</div>`; }
function slopeFields() { return `${inputField('slopes', 'Bed slopes', 'text', 'value="0.001" placeholder="0.001, 0.002"')}<span class="field-note">Enter one or more positive slopes separated by commas.</span>`; }

function renderFields() {
  badge.textContent = shape.options[shape.selectedIndex].text.toUpperCase();
  let markup = baseFields();
  const op = operation.value;
  if (category.value === 'uf') {
    if (['normal_depth', 'general'].includes(op)) markup += roughnessFields() + slopeFields();
    if (['froude', 'specific_energy'].includes(op)) markup += inputField('y', 'Flow depth y');
    if (op === 'critical_slope') markup += roughnessFields();
  } else if (category.value === 'weirs') {
    markup += roughnessFields() + slopeFields() + inputField('weir_height', 'Weir height P');
    if (op === 'gvf') markup += inputField('target_rise', 'Target upstream rise') + inputField('steps', 'Number of steps', 'number', 'step="1" min="1" value="12"');
  } else if (category.value === 'jumps') markup += inputField('y1', 'Initial depth y₁');
  else if (category.value === 'contractions') {
    if (op !== 'far_upstream') markup += `<div class="subsection-label" style="grid-column:1/-1;margin-top:9px">Narrow section</div>` + inputField('narrow_b', 'Narrow bed width') + inputField('narrow_z', 'Narrow side slope z') + inputField('narrow_d', 'Narrow diameter');
    if (op !== 'critical') markup += roughnessFields() + slopeFields();
    if (op === 'bed_change') markup += inputField('bed_changes', 'Bed changes', 'text', 'value="0.1" placeholder="0.1, -0.05"');
  } else if (category.value === 'depressions') {
    markup += roughnessFields() + slopeFields() + inputField('depression', 'Depression depth');
    if (op === 'with_weir') markup += inputField('weir_height', 'Weir height P');
  }
  fields.innerHTML = markup;
}

function updateOperations() {
  operation.innerHTML = operationOptions[category.value].map(([value, label]) => `<option value="${value}">${label}</option>`).join('');
  renderFields();
}

function parseList(formData, key) {
  const raw = formData.get(key);
  if (!raw) return [];
  return String(raw).split(',').map(item => item.trim()).filter(Boolean).map(Number);
}

function payloadFromForm() {
  const data = Object.fromEntries(new FormData(form).entries());
  data.slopes = parseList(new FormData(form), 'slopes');
  data.bed_changes = parseList(new FormData(form), 'bed_changes');
  if (data.steps) data.steps = Number(data.steps);
  return data;
}

function formatValue(value, unit = '') {
  if (typeof value === 'number') return `${value.toFixed(6)}${unit ? ` ${unit}` : ''}`;
  return String(value);
}

function metricMarkup(metrics) { return `<div class="metric-grid">${metrics.map(metric => `<div class="metric"><div class="metric-label">${metric.label}</div><div class="metric-value">${formatValue(metric.value, metric.unit)}</div></div>`).join('')}</div>`; }
function tableMarkup(headers, rows) { return `<div class="table-wrap"><table class="data-table"><thead><tr>${headers.map(header => `<th>${header[1]}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${headers.map(([key]) => `<td>${key === 'choked' ? `<span class="state-pill ${row[key] ? 'choked' : ''}">${row[key] ? 'Choking' : 'Clear'}</span>` : formatValue(row[key] ?? '—')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`; }

function renderResult(result) {
  resultTitle.textContent = result.title;
  resultTag.textContent = 'CALCULATED';
  resultArea.className = 'result-area';
  if (result.type === 'metrics') resultArea.innerHTML = metricMarkup(result.metrics);
  else if (result.type === 'general') resultArea.innerHTML = metricMarkup(result.summary) + '<div style="height:14px"></div>' + tableMarkup([['slope','Slope'],['depth','Normal depth'],['froude','Froude'],['energy','Energy'],['regime','Regime']], result.cases);
  else if (result.type === 'cases') resultArea.innerHTML = tableMarkup(Object.keys(result.cases[0] || {}).map(key => [key, key.replaceAll('_', ' ')]), result.cases);
  else if (result.type === 'weir') resultArea.innerHTML = tableMarkup([['slope','Slope'],['y_up','Upstream depth'],['yw','Crest depth'],['y_down','Downstream depth'],['Fr_up','Fr upstream'],['Fr_w','Fr crest'],['Fr_d','Fr downstream'],['choked','Control']], result.cases);
  else if (result.type === 'contraction') resultArea.innerHTML = tableMarkup([['slope','Slope'],['bed_change','Bed change'],['y_up','Upstream'],['y_narrow','Narrow section'],['y_down','Downstream'],['choked','Control']], result.cases);
  else if (result.type === 'depression') resultArea.innerHTML = tableMarkup([['slope','Slope'],['yA','Station A'],['yB','Station B'],['yC','Station C'],['yD','Station D'],['yE','Station E'],['choked','Control']], result.cases);
  else if (result.type === 'gvf') resultArea.innerHTML = result.cases.map(item => `<div class="subsection-label">Slope ${formatValue(item.slope)} · total distance ${formatValue(item.distance)} m</div>${tableMarkup([['step','Step'],['distance','Distance'],['depth','Depth'],['rise','Rise']], item.rows)}`).join('<div style="height:20px"></div>');
}

function showError(message) { resultTitle.textContent = 'Calculation needs attention'; resultTag.textContent = 'ERROR'; resultArea.className = 'result-area error-state'; resultArea.innerHTML = `<strong>Unable to complete this run.</strong><span>${message}</span>`; }

category.addEventListener('change', updateOperations); shape.addEventListener('change', renderFields); operation.addEventListener('change', renderFields);
document.querySelector('#reset-button').addEventListener('click', () => { form.reset(); updateOperations(); resultTitle.textContent = 'Awaiting a section'; resultTag.textContent = 'READY'; resultArea.className = 'result-area empty-state'; resultArea.innerHTML = '<div class="empty-mark">∿</div><h3>Your result will appear here</h3><p>Set the section and run a calculation to populate the bench.</p>'; });
form.addEventListener('submit', async event => {
  event.preventDefault(); resultTag.textContent = 'RUNNING'; resultArea.className = 'result-area loading-state'; resultArea.innerHTML = '<span class="spinner"></span><span>Solving the section...</span>';
  try { const response = await fetch('/api/calculate', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payloadFromForm()) }); const body = await response.json(); if (!response.ok || !body.ok) throw new Error(body.error || 'The calculation failed.'); renderResult(body.result); } catch (error) { showError(error.message); }
});

updateOperations();