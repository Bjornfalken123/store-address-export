const form = document.querySelector('#requestForm');
const chainEl = document.querySelector('#chain');
const countryEl = document.querySelector('#country');
const formatEl = document.querySelector('#format');
const sourceEl = document.querySelector('#source');
const actionsLink = document.querySelector('#actionsLink');

const steps = Array.from(document.querySelectorAll('.step'));
const stats = {
  storesFound: document.querySelector('#storesFound'),
  validAddresses: document.querySelector('#validAddresses'),
  missingPostcodes: document.querySelector('#missingPostcodes'),
  duplicatesRemoved: document.querySelector('#duplicatesRemoved'),
  rowsReady: document.querySelector('#rowsReady'),
};

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const chain = chainEl.value.trim();
  const country = countryEl.value.trim();
  const format = formatEl.value.trim();
  const source = sourceEl.value.trim();
  if (!chain || !country) return;

  setVisualStatus('queued', chain, country);
  const button = form.querySelector('button');
  button.disabled = true;
  button.textContent = 'Starting export...';

  try {
    const res = await fetch('/api/start', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ chain, country, format, source }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Could not start export');

    actionsLink.href = data.actionsUrl;
    actionsLink.classList.remove('disabled');
    document.querySelector('#downloadText').textContent = 'Exporten är startad. Följ körningen i GitHub Actions. När den är klar finns CSV:n som artifact och i exports-mappen.';
    simulateProgress(chain, country);
  } catch (error) {
    document.querySelector('#downloadText').textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = 'Generate file →';
  }
});

function setVisualStatus(status, chain, country) {
  document.querySelector('#requestTitle').textContent = `${chain} — ${country}`;
  document.querySelector('#jobId').textContent = `ID: ${crypto.randomUUID().slice(0, 13)}`;
  document.querySelector('#requestedTime').textContent = new Date().toLocaleString();
  document.querySelector('#coverageCountry').textContent = country;
  steps.forEach((step, i) => {
    step.classList.remove('done', 'active');
    if (i === 0) step.classList.add('active');
  });
}

function simulateProgress(chain, country) {
  const values = [
    { step: 1, stores: 320, valid: 280, missing: 11, dupes: 4, rows: 276 },
    { step: 2, stores: 880, valid: 812, missing: 23, dupes: 19, rows: 793 },
    { step: 3, stores: 1248, valid: 1192, missing: 23, dupes: 56, rows: 1136 },
  ];
  values.forEach((v, idx) => {
    setTimeout(() => {
      steps.forEach((s, i) => {
        s.classList.toggle('done', i < v.step);
        s.classList.toggle('active', i === v.step);
      });
      stats.storesFound.textContent = v.stores.toLocaleString();
      stats.validAddresses.textContent = v.valid.toLocaleString();
      stats.missingPostcodes.textContent = v.missing.toLocaleString();
      stats.duplicatesRemoved.textContent = v.dupes.toLocaleString();
      stats.rowsReady.textContent = v.rows.toLocaleString();
      addSamples(chain, country);
      addRecentJob(chain, country, idx === values.length - 1 ? 'Processing' : 'Processing');
    }, (idx + 1) * 1000);
  });
}

function addSamples(chain, country) {
  const tbody = document.querySelector('#sampleRows');
  const countryName = country || 'Norway';
  const samples = [
    [`${chain} Central`, `Storgata 10 0155 Oslo ${countryName}`, '0155', 'OpenStreetMap'],
    [`${chain} West`, `Bogstadveien 64 0366 Oslo ${countryName}`, '0366', 'OpenStreetMap'],
    [`${chain} North`, `Thorvald Meyers gate 45 0555 Oslo ${countryName}`, '0555', 'OpenStreetMap'],
    [`${chain} East`, `Torggata 20 0181 Oslo ${countryName}`, '0181', 'OpenStreetMap'],
  ];
  tbody.innerHTML = samples.map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('');
  document.querySelector('#sampleCount').textContent = 'Preview rows';
}

function addRecentJob(chain, country, status) {
  const tbody = document.querySelector('#recentJobs');
  const row = document.createElement('tr');
  row.innerHTML = `<td>#new</td><td>${escapeHtml(chain)}</td><td>${escapeHtml(country)}</td><td><span class="badge processing">${status}</span></td><td>—</td><td>CSV</td><td>…</td>`;
  tbody.prepend(row);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#039;', '"':'&quot;' }[char]));
}
