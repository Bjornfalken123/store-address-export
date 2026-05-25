export async function onRequestPost(context) {
  try {
    const body = await context.request.json();
    const chain = String(body.chain || '').trim();
    const country = String(body.country || '').trim();
    const format = String(body.format || 'CSV').trim();
    const source = String(body.source || 'OpenStreetMap').trim();

    if (!chain || !country) return json({ error: 'Ange både kedja och land.' }, 400);

    const { GITHUB_OWNER, GITHUB_REPO, GITHUB_TOKEN } = context.env;
    const workflow = context.env.GITHUB_WORKFLOW_FILE || 'export-custom.yml';
    const ref = context.env.GITHUB_REF || 'main';

    if (!GITHUB_OWNER || !GITHUB_REPO || !GITHUB_TOKEN) {
      return json({ error: 'Saknar GitHub-inställningar i Cloudflare: GITHUB_OWNER, GITHUB_REPO eller GITHUB_TOKEN.' }, 500);
    }

    const url = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${workflow}/dispatches`;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        accept: 'application/vnd.github+json',
        authorization: `Bearer ${GITHUB_TOKEN}`,
        'content-type': 'application/json',
        'user-agent': 'retail-address-finder'
      },
      body: JSON.stringify({ ref, inputs: { chain, country, format, source } })
    });

    if (!response.ok) {
      const text = await response.text();
      return json({ error: `GitHub svarade ${response.status}: ${text}` }, 500);
    }

    return json({
      ok: true,
      actionsUrl: `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${workflow}`
    });
  } catch (error) {
    return json({ error: error.message || 'Okänt fel.' }, 500);
  }
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json; charset=utf-8' } });
}
