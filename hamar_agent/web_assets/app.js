"use strict";
const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="hamar-token"]').content;
let runId = null;
function item(parent, tag, text) { const el = document.createElement(tag); el.textContent = text; parent.appendChild(el); return el; }
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Forespørselen feilet.");
  return data;
}
async function load() {
  try {
    const data = await api("/api/sources");
    data.sources.forEach((s) => { const option = item($("source"), "option", s.label); option.value = s.id; });
    $("source").disabled = !data.sources.length; $("run").disabled = !data.sources.length;
    $("status").textContent = data.sources.length ? (data.sources.some((source) => source.kind === "reviewed municipal excerpts") ? "Klar. Kun godkjente kommunale tjenesteutdrag er tilgjengelige." : "Klar. Kun godkjente syntetiske kilder er tilgjengelige.") : "Ingen godkjente kilder.";
  } catch (error) { $("status").textContent = error.message; }
}
$("run").addEventListener("click", async () => {
  $("run").disabled = true; $("result").hidden = true; runId = null; $("status").textContent = "Kjører …";
  try {
    const data = await api("/api/run", { method: "POST", headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: JSON.stringify({ source_id: $("source").value }) });
    runId = data.run_id; const result = data.result;
    ["warnings", "findings", "claims", "paragraphs"].forEach((id) => $(id).replaceChildren());
    $("summary").textContent = `Leverandør: ${result.provider}. ${result.claims.length} påstander. Korreksjon: ${result.correction.status}.`;
    result.warnings.forEach((w) => item($("warnings"), "li", w));
    if (!result.verification.findings.length) item($("findings"), "li", "Ingen funn fra de begrensede kontrollene. Dette beviser ikke sannhet.");
    result.verification.findings.forEach((f) => item($("findings"), "li", `${f.code}: ${f.message} (${f.claim_ids.join(", ")})`));
    result.claims.forEach((c) => { const card = item($("claims"), "article", ""); item(card, "h4", c.id + ": " + c.text); item(card, "p", "Evidensstatus: " + c.evidence_status); item(card, "blockquote", c.evidence_quote); item(card, "p", "Avsnitt: " + c.paragraph_id); });
    result.source.paragraphs.forEach((p) => item($("paragraphs"), "p", p.id + ": " + p.text));
    (result.source_provenance || []).forEach((citation) => { sourceLink($("paragraphs"), citation); provenance($("paragraphs"), citation); });
    $("json").textContent = JSON.stringify(result, null, 2); $("result").hidden = false; $("status").textContent = "Ferdig. Se varsler og evidens.";
  } catch (error) { $("status").textContent = error.message; }
  finally { $("run").disabled = false; }
});
$("download").addEventListener("click", async () => {
  if (!runId) return;
  try {
    const response = await fetch("/api/results/" + runId, { headers: { "X-Hamar-Token": token } });
    if (!response.ok) { const data = await response.json(); throw new Error(data.error); }
    const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a");
    link.href = url; link.download = "hamar-result.json"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { $("status").textContent = error.message; }
});
load();

// Portal search is a separate presentation over the same verified workflow.
const portalWarnings = {
  "Verbatim reviewed excerpts only; not semantic fact-checking or a guarantee of truth.": "Kun ordrette, gjennomg\u00e5tte kildeutdrag. Ikke semantisk faktasjekk eller garanti for riktighet.",
  "Limited source coverage. Consult the official page for context and current conditions.": "Begrenset kildedekning. Les den offisielle siden for sammenheng og gjeldende vilk\u00e5r.",
  "Rejected candidate text omitted from history for privacy.": "Avvist modelltekst er utelatt fra historikken av personvernhensyn.",
  "Synthetic demonstration; not municipal information.": "Syntetisk demo. Dette er ikke kommunal informasjon.",
  "Evidence matching is not semantic fact-checking or a guarantee of truth.": "Sitatsamsvar er ikke semantisk faktasjekk eller en garanti for sannhet.",
  "Review required: verification findings remain unresolved.": "Krever vurdering: kildekontrollen har uløste funn.",
  "Ollama failed. Explicit mock fallback used; this result is not real LLM output.": "Ollama feilet. Avtalt mock-reserve ble brukt; dette er ikke et ekte LLM-svar.",
  "Correction failed; original findings retained for review.": "Korreksjonen feilet. Opprinnelige funn er bevart for vurdering."
};
const findingLabels = {
  invalid_paragraph_id: "Ugyldig avsnittshenvisning", fabricated_evidence: "Sitatet finnes ikke i kilden",
  unsupported_number: "En tallverdi mangler støtte i sitatet", conflicting_claims: "Motstridende tallpåstander",
  missing_citation: "Kildehenvisning mangler", malformed_output: "Ugyldig svarformat", malformed_claim: "Ugyldig påstandsformat",
  potentially_unsupported: "Påstanden kan mangle støtte; krever vurdering", uncertain_claim: "Påstanden er uttrykkelig usikker",
  duplicate_claim_id: "Duplisert påstands-ID"
};
const evidenceLabels = { exact_match: "Sitat funnet i oppgitt avsnitt", missing: "Manglende eller ugyldig evidens", not_checked: "Ikke kontrollert" };

let selectedCategory = null;
let selectedService = null;
let portalRunId = null;
let searchGeneration = 0;
let lastSearch = null;
function sourceLink(parent, citation) {
  if (!citation.url) { item(parent, "p", "Syntetisk demo. Ingen kommunal kildeside.").className = "source-meta"; return; }
  try {
    const url = new URL(citation.url);
    if (url.protocol !== "https:" || url.hostname !== "www.hamar.kommune.no" || url.username || url.password) return;
    const link = item(parent, "a", url.hostname + url.pathname + " ↗");
    link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; link.className = "source-link";
  } catch (_) { /* Invalid citations are not turned into clickable links. */ }
}
function provenance(parent, source) {
  const time = source.retrieved_at ? "Hentet: " + new Date(source.retrieved_at).toLocaleString("nb-NO") : "Ikke hentet fra nettet (syntetisk)";
  item(parent, "p", time + " · Indeksert: " + new Date(source.indexed_at).toLocaleString("nb-NO")).className = "source-meta";
}
function renderSearch(data) {
  $("search-results").replaceChildren();
  $("search-area").hidden = false;
  $("result-count").textContent = `${data.results.length} treff i det avgrensede kildeutvalget${data.category ? " · valgt kategori" : ""}.`;
  if (!data.results.length) {
    const card = item($("search-results"), "article", ""); card.className = "result-card";
    item(card, "h3", "Vi fant ikke et tilstrekkelig kildegrunnlag.");
    item(card, "p", "Prøv andre temaord eller se kommunens offisielle nettsted. Ingen treff betyr ikke at kommunen mangler tjenesten.");
  }
  data.results.forEach((hit) => {
    const card = item($("search-results"), "article", ""); card.className = "result-card";
    item(card, "p", hit.synthetic ? "SYNTETISK EKSEMPEL" : "GJENNOMGÅTT KILDE").className = "eyebrow";
    item(card, "h3", hit.title); item(card, "p", hit.excerpt); sourceLink(card, hit); provenance(card, hit);
  });
  $("answer-button").disabled = !data.results.length || !(lastSearch && lastSearch.query.trim());
}
async function searchPortal() {
  const generation = ++searchGeneration;
  const query = $("query").value.trim();
  const category = selectedCategory;
  lastSearch = { query, category }; portalRunId = null;
  $("portal-download").hidden = true; $("answer-content").replaceChildren(); $("answer-button").disabled = true;
  $("portal-status").textContent = "Søker i lokal indeks …"; $("search-button").disabled = true;
  try {
    const data = await api("/api/search", { method: "POST", headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: JSON.stringify(lastSearch) });
    if (generation !== searchGeneration) return;
    renderSearch(data); $("portal-status").textContent = "Søket er ferdig. Ingen nye nettsider ble hentet.";
    document.querySelectorAll(".category-card").forEach((c) => (c.classList.toggle("active", c.dataset.service === selectedService), c.setAttribute("aria-pressed", String(c.dataset.service === selectedService))));
  } catch (error) { if (generation === searchGeneration) { $("portal-status").textContent = error.message; $("search-area").hidden = true; } }
  finally { if (generation === searchGeneration) $("search-button").disabled = false; }
}
$("search-form").addEventListener("submit", (event) => { event.preventDefault(); searchPortal(); });
$("clear-category").addEventListener("click", () => { selectedCategory = null; selectedService = null; searchPortal(); });
$("answer-button").addEventListener("click", async () => {
  if (!lastSearch) return;
  const generation = searchGeneration;
  $("answer-button").disabled = true; $("portal-status").textContent = "Kontrollerer kildeutdrag …";
  try {
    const data = await api("/api/answer", { method: "POST", headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: JSON.stringify(lastSearch) });
    if (generation !== searchGeneration) return;
    portalRunId = data.run_id;
    const answer = data.answer, container = $("answer-content"); container.replaceChildren();
    item(container, "p", answer.message).className = "notice";
    if (answer.result) {
      const result = answer.result;
      item(container, "p", "Leverandør i dette svaret: " + result.provider).className = "source-meta";
      const warnings = item(container, "ul", ""); result.warnings.forEach((w) => item(warnings, "li", portalWarnings[w] || w));
      result.verification.findings.forEach((finding) => item(warnings, "li", `${findingLabels[finding.code] || finding.code} (${finding.claim_ids.join(", ")}). Se full JSON for detaljer.`));
      if (!result.verification.findings.length) item(container, "p", "Ingen funn fra de begrensede kontrollene. Dette beviser ikke at svaret er sant.").className = "source-meta";
      result.claims.forEach((claim) => {
        const card = item(container, "article", ""); item(card, "h3", claim.text);
        item(card, "p", "Evidensstatus: " + (evidenceLabels[claim.evidence_status] || claim.evidence_status)).className = "source-meta";
        item(card, "blockquote", claim.evidence_quote);
        const citations = answer.citations.filter((c) => c.paragraph_id === claim.paragraph_id);
        if (!citations.length) item(card, "p", "Mangler gyldig kildehenvisning. Krever vurdering.").className = "notice";
        citations.forEach((citation) => { item(card, "p", citation.title).className = "source-meta"; sourceLink(card, citation); provenance(card, citation); });
      });
    }
    const details = item(container, "details", ""); item(details, "summary", "Vis svar og kildegrunnlag som JSON"); item(details, "pre", JSON.stringify(answer, null, 2));
    $("portal-download").hidden = false; $("portal-status").textContent = "Ferdig. Vurder funn og kilder før bruk.";
  } catch (error) { if (generation === searchGeneration) $("portal-status").textContent = error.message; }
  finally { if (generation === searchGeneration) $("answer-button").disabled = false; }
});
$("portal-download").addEventListener("click", async () => {
  if (!portalRunId) return;
  try {
    const response = await fetch("/api/results/" + portalRunId, { headers: { "X-Hamar-Token": token } });
    if (!response.ok) throw new Error("Resultatet er utløpt. Kjør søket på nytt.");
    const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a");
    link.href = url; link.download = "hamar-kildebasert-svar.json"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { $("portal-status").textContent = error.message; }
});
async function loadPortal() {
  try {
    const data = await api("/api/portal");
    const mockMode = data.provider.startsWith("mock");
    $("mode").textContent = data.synthetic ? (mockMode ? "Demomodus · syntetiske kilder" : "Lokal LLM · syntetiske kilder") : "Avgrenset, godkjent kildeutvalg";
    $("answer-help").textContent = mockMode ? "Be om et kildebasert utdrag. Demoen bruker mock, ikke en ekte språkmodell." : "Leverandør: " + data.provider + ". Svar kontrolleres mot kildeutdrag, men er ikke garantert sanne.";
    $("answer-button").textContent = mockMode ? "Lag kildebasert utdrag" : "Lag og kontroller lokalt AI-svar";
    $("coverage").textContent = `${data.documents} indekserte dokumenter · Ikke fullstendig kommunal dekning`;
    const services = [
      { id: "skole", title: "Skole", category: "oppvekst", query: data.synthetic ? "barnehage" : "skole", icon: "school" },
      { id: "bolig", title: "Bolig", category: "bolig", query: "byggesak", icon: "home" },
      { id: "helse", title: "Helse", category: "helse", query: "helse", icon: "health" },
      { id: "vann", title: "Vann", category: "teknisk", query: "vann", icon: "water" },
      { id: "miljo", title: "Miljø", category: "miljo", query: "miljø", icon: "leaf" },
      { id: "transport", title: "Transport", category: "teknisk", query: "parkering", icon: "bus" },
      { id: "kultur", title: "Kultur", category: "kultur", query: "kultur", icon: "culture" },
      { id: "politikk", title: "Politikk", category: "politikk", query: "planer", icon: "politics" }
    ];
    const icons = {
      school: ["M3 9l9-5 9 5-9 5-9-5Z", "M6 11v6l6 3 6-3v-6", "M21 9v7"],
      home: ["m3 11 9-8 9 8", "M5 10v11h14V10", "M10 21v-7h4v7"],
      health: ["M9 3h6v6h6v6h-6v6H9v-6H3V9h6V3Z"],
      water: ["M12 3s-7 8-7 12a7 7 0 0 0 14 0c0-4-7-12-7-12Z", "M8 15c0 2 1 3 3 3"],
      leaf: ["M20 3C9 2 3 8 5 15c2 6 10 5 13-1 2-4 2-8 2-11Z", "M3 21 16 8", "m8 13 6 1"],
      bus: ["M5 17V6c0-3 14-3 14 0v11H5Z", "M5 11h14", "M8 17v3M16 17v3", "M8 14h1M15 14h1"],
      culture: ["M9 18V5l11-2v13", "M9 8l11-2", "M9 18c0 3-6 4-6 1 0-3 6-4 6-1Z", "M20 16c0 3-6 4-6 1 0-3 6-4 6-1Z"],
      politics: ["m3 8 9-5 9 5H3Z", "M5 10v8M10 10v8M14 10v8M19 10v8", "M3 21h18M4 18h16"]
    };
    $("categories").replaceChildren();
    services.forEach((service) => {
      const button = item($("categories"), "button", "");
      button.type = "button"; button.className = "category-card";
      button.dataset.category = service.category; button.dataset.service = service.id;
      button.setAttribute("aria-pressed", "false");
      button.setAttribute("aria-label", service.title + ": søk i godkjente kilder");
      const circle = item(button, "span", ""); circle.className = "category-icon"; circle.setAttribute("aria-hidden", "true");
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.setAttribute("viewBox", "0 0 24 24");
      icons[service.icon].forEach((d) => { const path = document.createElementNS("http://www.w3.org/2000/svg", "path"); path.setAttribute("d", d); svg.appendChild(path); });
      circle.appendChild(svg);
      const label = item(button, "span", service.title); label.className = "category-label";
      item(button, "span", "→").className = "arrow";
      button.disabled = !data.categories.some((category) => category.id === service.category);
      button.addEventListener("click", () => {
        selectedCategory = service.category; selectedService = service.id;
        $("query").value = service.query; searchPortal();
      });
    });
  } catch (error) { $("portal-status").textContent = error.message; }
}
loadPortal();
