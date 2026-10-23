"use strict";
const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="hamar-token"]').content;
function item(parent, tag, text) { const el = document.createElement(tag); el.textContent = text; parent.appendChild(el); return el; }
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Forespørselen feilet.");
  return data;
}
function visibleRequestError(error, fallback) {
  return error instanceof TypeError ? fallback : (error.message || fallback);
}
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
let selectedCategory = null;
let selectedService = null;
let portalReady = false;
let allowedRealQueryTerms = new Set();
let queryStopwords = new Set();
let queryFollowupModifiers = new Set();
let queryAliases = new Map();
let officialMenuUrl = "https://www.hamar.kommune.no/meny/";
function revealInView(element) {
  element.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}
function isAllowedRealQuery(query, allowFollowup = false) {
  const folded = query.normalize("NFC").toLocaleLowerCase("nb-NO").replaceAll("æ", "ae").replaceAll("ø", "o").replaceAll("å", "a");
  const terms = (folded.match(/[\p{L}\p{N}]+/gu) || [])
    .filter((term) => !queryStopwords.has(term) && !(allowFollowup && queryFollowupModifiers.has(term)))
    .map((term) => queryAliases.get(term) || term);
  return terms.length <= 16 && terms.every((term) => allowedRealQueryTerms.has(term));
}
function queryInputProblem(query) {
  if (query.length > 160 || /[\u0000-\u001f]/u.test(query)) return "Skriv et spørsmål på maksimalt 160 tegn uten kontrolltegn.";
  const contact = /@|https?:\/\/|\d[\d ()+-]{5,}\d|\b(?:jeg\s+heter|navnet\s+mitt\s+er|mitt\s+navn\s+er|fødselsnummer|personnummer|telefonnummer|e-?postadresse|min\s+adresse|jeg\s+bor\s+i)\b/i;
  const address = /\b(?:[\p{L}.'-]*?(?:gata|vei|veien)|[\p{L}.'-]+\s+(?:gate|street|road)|gate|gata|vei|veien|street|road)\s+\d{1,4}[a-z]?\b/iu;
  return contact.test(query) || address.test(query) ? "Spørsmålet ble avvist av hensyn til personvernet. Ikke skriv personopplysninger, kontaktdata eller adresser." : "";
}
let searchGeneration = 0;
let answerGeneration = 0;
let lastAnsweredQuery = null;
let aiBusy = false;
let lastSearch = null;
let providerChoices = [];
let answerAbort = null;
let conversationActive = false;
let chosenProvider = null;
let chosenModel = null;
function sourceLink(parent, citation) {
  if (!citation.url) { item(parent, "p", "Syntetisk demo. Ingen kommunal kildeside.").className = "source-meta"; return; }
  try {
    const url = new URL(citation.url);
    if (url.protocol !== "https:" || url.hostname !== "www.hamar.kommune.no" || url.username || url.password) return;
    const link = item(parent, "a", url.hostname + url.pathname + " ↗");
    link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; link.className = "source-link";
  } catch (_) { /* Invalid citations are not turned into clickable links. */ }
}
function officialMenuLink(parent, url = officialMenuUrl) {
  try {
    const official = new URL(url);
    if (official.href !== "https://www.hamar.kommune.no/meny/" || official.username || official.password) return;
    const wrapper = item(parent, "p", ""); wrapper.className = "official-menu-fallback";
    const link = item(wrapper, "a", "Se Hamar kommunes offisielle tjenestemeny");
    link.href = official.href; link.target = "_blank"; link.rel = "noopener noreferrer";
  } catch (_) { /* Only the fixed official menu URL can be presented. */ }
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
    item(card, "h3", data.query_status === "unsupported_topic" ? "Temaet ble ikke gjenkjent" : "Vi fant ikke et tilstrekkelig kildegrunnlag.");
    item(card, "p", data.message || "Pr\u00f8v andre temaord. Ingen treff betyr ikke at kommunen mangler tjenesten.");
    officialMenuLink(card, data.official_menu_url || officialMenuUrl);
  }
  data.results.forEach((hit) => {
    const card = item($("search-results"), "article", ""); card.className = "result-card";
    item(card, "p", hit.synthetic ? "SYNTETISK EKSEMPEL" : "GJENNOMGÅTT KILDE").className = "eyebrow";
    item(card, "h3", hit.title); item(card, "p", hit.excerpt); sourceLink(card, hit); provenance(card, hit);
  });
}
function renderSearchMessage(title, message) {
  $("search-area").hidden = false;
  $("search-results").replaceChildren();
  $("result-count").textContent = title;
  const card = item($("search-results"), "article", ""); card.className = "result-card";
  item(card, "h3", title); item(card, "p", message);
}
async function searchPortal() {
  const generation = ++searchGeneration;
  const query = $("query").value.trim();
  const category = selectedCategory;
  if (!portalReady) {
    $("query").value = "";
    $("portal-status").textContent = "Søket er ikke klart ennå. Ingen tekst ble sendt.";
    renderSearchMessage("Søket er ikke klart", "Vent litt og prøv igjen. Spørsmålet ble ikke sendt.");
    revealInView($("search-area"));
    return;
  }
  const inputProblem = queryInputProblem(query);
  if (inputProblem) {
    $("query").value = "";
    lastSearch = { query: "", category };
    renderSearchMessage("S\u00f8ket ble avvist", inputProblem);
    $("search-button").disabled = false;
    $("portal-status").textContent = inputProblem;
    revealInView($("search-area"));
    return;
  }
  lastSearch = { query, category };
  $("search-results").replaceChildren(); $("result-count").textContent = "Søker i gjennomgåtte utdrag …";
  $("search-area").hidden = false;
  $("portal-status").textContent = "Søker i gjennomgåtte kommunale utdrag …"; $("search-button").disabled = true; $("search-button").querySelector(".button-label").textContent = "Søker …";
  try {
    const data = await api("/api/search", { method: "POST", headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: JSON.stringify(lastSearch) });
    if (generation !== searchGeneration) return;
    renderSearch(data); $("portal-status").textContent = "Søket er ferdig. Ingen nye nettsider ble hentet.";
    revealInView($("search-area"));
    document.querySelectorAll(".category-card").forEach((c) => (c.classList.toggle("active", c.dataset.service === selectedService), c.setAttribute("aria-pressed", String(c.dataset.service === selectedService))));
  } catch (error) { if (generation === searchGeneration) {
    const message = visibleRequestError(error, "Kan ikke kontakte den lokale tjenesten. Kontroller at Hamar-agenten fortsatt kjører.");
    $("portal-status").textContent = message; renderSearchMessage("Søket kunne ikke fullføres", message); revealInView($("search-area"));
  } }
  finally { if (generation === searchGeneration) { $("search-button").disabled = false; $("search-button").querySelector(".button-label").textContent = "Søk"; } }
}
$("search-form").addEventListener("submit", (event) => { event.preventDefault(); searchPortal(); });
$("query").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.isComposing) { event.preventDefault(); $("search-form").requestSubmit(); }
});
$("clear-category").addEventListener("click", () => { selectedCategory = null; selectedService = null; searchPortal(); });
function addTechnicalDetails(container, answer) {
  const details = item(container, "details", ""); details.className = "technical-details";
  item(details, "summary", "Teknisk kontroll og kildesporing");
  const body = item(details, "div", ""); body.className = "technical-body";
  if (answer.result) {
    const result = answer.result;
    item(body, "p", "Lokal leverandør: " + result.provider).className = "source-meta";
    if (result.claims.length) {
      const claims = item(body, "ul", "");
      result.claims.forEach((claim) => item(claims, "li", `${claim.id} · ${claim.paragraph_id} · ${claim.evidence_status}`));
    }
    if (result.verification.findings.length) {
      const findings = item(body, "ul", "");
      result.verification.findings.forEach((finding) => item(findings, "li", `${finding.code}: ${finding.message} (${finding.claim_ids.join(", ")})`));
    }
    if (result.warnings.length) {
      const warnings = item(body, "ul", ""); result.warnings.forEach((warning) => item(warnings, "li", portalWarnings[warning] || warning));
    }
    if (answer.citations.length) {
      const citations = item(body, "ul", "");
      answer.citations.forEach((citation) => item(citations, "li", `${citation.source_id} · ${citation.paragraph_id} · ${citation.url || "ingen URL"} · hentet ${citation.retrieved_at || "ukjent"} · godkjenning utløper ${citation.approval_expires || "ukjent"}`));
    }
  }
}
function renderAnswer(answer) {
  const container = $("answer-content"); container.replaceChildren();
  if (answer.is_follow_up) item(container, "p", "Oppfølgingsspørsmål: Kildene er søkt på nytt; tidligere svar brukes ikke som evidens.").className = "verification-note";
  if (Number.isFinite(answer.provider_latency_ms)) item(container, "p", `Arbeidsflyttid inkl. kontroll: ${answer.provider_latency_ms} ms`).className = "source-meta";
  const result = answer.result;
  const findings = result?.verification?.findings || [];
  const claims = result?.claims || [];
  let stateText = "Krever vurdering", stateClass = "answer-state warning";
  if (answer.answer_status === "evidence_checked" && claims.length && !findings.length) {
    stateText = "Sitatkontroll utført"; stateClass = "answer-state checked";
  } else if (answer.answer_status === "insufficient_evidence") {
    stateText = "Utilstrekkelig kildegrunnlag"; stateClass = "answer-state warning";
  } else if (answer.answer_status === "clarification_required") {
    stateText = "Kan du presisere sp\u00f8rsm\u00e5let?"; stateClass = "answer-state warning";
  } else if (answer.answer_status === "provider_unavailable") {
    stateText = "Lokal modell utilgjengelig"; stateClass = "answer-state warning";
  } else if (answer.answer_status === "input_rejected") {
    stateText = "Spørsmålet ble avvist"; stateClass = "answer-state warning";
  }
  $("answer-state").textContent = stateText; $("answer-state").className = stateClass;
  item(container, "p", answer.message).className = "answer-message";
  if (!result || !claims.length) {
    item(container, "p", answer.answer_status === "insufficient_evidence" ? "Ingen AI-påstand vises fordi de gjennomgåtte kildene ikke gir nok grunnlag." : "Det finnes ikke et kildekontrollert svar å vise for dette søket.").className = "empty-answer";
    if (answer.citations.length) {
      const sources = item(container, "section", ""); sources.className = "answer-citations";
      item(sources, "h3", "Gjennomgått kilde for videre lesning");
      const linkedUrls = new Set();
      answer.citations.forEach((citation) => {
        if (citation.url && linkedUrls.has(citation.url)) return;
        if (citation.url) linkedUrls.add(citation.url);
        sourceLink(sources, citation);
      });
    }
    if (answer.answer_status === "insufficient_evidence" || answer.answer_status === "clarification_required") {
      officialMenuLink(container, answer.official_menu_url || officialMenuUrl);
    }
    addTechnicalDetails(container, answer);
    return;
  }
  if (findings.length) item(container, "p", "Automatisk kontroll fant forhold som må vurderes. Påstandene nedenfor er ikke bekreftet som riktige.").className = "notice";
  else item(container, "p", "Ordlyden samsvarer med et gjennomgått kildeutdrag. Dette er ikke en garanti for at opplysningen er sann eller oppdatert.").className = "verification-note";
  const linkedUrls = new Set();
  claims.forEach((claim) => {
    const article = item(container, "article", ""); article.className = "answer-claim";
    item(article, "p", findings.length ? "AI-SVAR · KREVER VURDERING" : "AI-SVAR").className = "answer-label";
    item(article, "p", claim.text).className = "answer-text";
    const sources = answer.citations.filter((citation) => citation.paragraph_id === claim.paragraph_id);
    if (claim.evidence_quote) {
      const excerpt = item(article, "section", ""); excerpt.className = "source-excerpt";
      item(excerpt, "h3", "Kildeutdrag brukt til kontroll"); item(excerpt, "blockquote", claim.evidence_quote);
    }
    const citationGroup = item(article, "div", ""); citationGroup.className = "answer-citations";
    if (!sources.length) item(citationGroup, "p", "Kildehenvisning mangler. Svaret må vurderes.").className = "notice";
    sources.forEach((citation) => {
      if (!citation.url || linkedUrls.has(citation.url)) return;
      const citationCard = item(citationGroup, "div", ""); citationCard.className = "citation-card"; linkedUrls.add(citation.url);
      item(citationCard, "p", "OFFISIELL KILDE").className = "answer-label";
      item(citationCard, "p", citation.title).className = "citation-title"; sourceLink(citationCard, citation);
      item(citationCard, "p", citation.retrieved_at ? "Kildematerialet ble gjennomgått " + new Date(citation.retrieved_at).toLocaleDateString("nb-NO") + "." : "Tidspunkt for gjennomgang er ikke oppgitt.").className = "source-meta";
    });
  });
  addTechnicalDetails(container, answer);
}
function populateProviders(data, preferredProvider) {
  providerChoices = Array.isArray(data.choices) ? data.choices : [];
  const select = $("provider-model"); select.replaceChildren();
  providerChoices.forEach((choice) => {
    const option = item(select, "option", choice.available ? choice.label : `${choice.label} — ${choice.reason}`);
    option.value = `${choice.provider}|${choice.model}`; option.disabled = !choice.available;
  });
  const preferred = providerChoices.find((choice) => choice.available &&
    (`${choice.provider}:${choice.model}` === preferredProvider || (preferredProvider === "mock" && choice.provider === "mock")));
  const selected = preferred || providerChoices.find((choice) => choice.available && choice.provider === "ollama") ||
    providerChoices.find((choice) => choice.available && choice.provider === "mock");
  if (selected) {
    select.value = `${selected.provider}|${selected.model}`;
    chosenProvider = selected.provider; chosenModel = selected.model;
    select.disabled = false;
    $("provider-processing").textContent = selected.processing === "external" ? "Ekstern behandling er aktivert for godkjente kildeutdrag." : selected.provider === "mock" ? selected.reason : "Lokal behandling på denne maskinen.";
    $("answer-help").textContent = `Valgt: ${selected.label}. Alle svar går gjennom samme kildeverifisering.`;
  } else {
    chosenProvider = chosenModel = null; select.disabled = true;
    $("provider-processing").textContent = providerChoices.map((choice) => choice.reason).filter(Boolean).join(" ") || "Ingen modell er tilgjengelig.";
  }
  $("ai-button").disabled = !portalReady || !selected || !$("ai-query").value.trim();
}
$("provider-model").addEventListener("change", async () => {
  ++answerGeneration; if (answerAbort) answerAbort.abort(); answerAbort = null; aiBusy = false;
  $("ai-query").disabled = false; $("ai-result").setAttribute("aria-busy", "false");
  lastAnsweredQuery = null; $("answer-content").replaceChildren();
  const [provider, ...modelParts] = $("provider-model").value.split("|");
  const model = modelParts.join("|");
  const choice = providerChoices.find((item) => item.available && item.provider === provider && item.model === model);
  chosenProvider = choice?.provider || null; chosenModel = choice?.model || null;
  $("provider-processing").textContent = !choice ? "Valgt modell er ikke tilgjengelig." : choice.processing === "external" ? "Ekstern behandling: bare godkjente kildeavsnitt sendes." : choice.provider === "mock" ? choice.reason : "Lokal behandling på denne maskinen.";
  $("answer-help").textContent = choice ? `Valgt: ${choice.label}. Alle svar går gjennom samme kildeverifisering.` : "Ingen tilgjengelig modell valgt.";
  $("answer-state").textContent = "Modell endret · klar for nytt spørsmål"; $("answer-state").className = "answer-state";
  $("ai-button").disabled = true;
  try {
    await api("/api/conversation/reset", { method: "POST", headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: "{}" });
    conversationActive = false;
    $("answer-state").textContent = "Modell valgt · samtalen nullstilt";
    $("ai-button").disabled = !portalReady || !choice || !$("ai-query").value.trim();
  } catch (error) {
    chosenProvider = chosenModel = null;
    $("provider-model").disabled = true;
    $("provider-processing").textContent = "Kunne ikke nullstille den forrige samtalen; velg modellen på nytt etter omlasting.";
    $("portal-status").textContent = visibleRequestError(error, "Samtalen ble ikke nullstilt.");
  }
});
async function askAi() {
  const generation = ++answerGeneration;
  const query = $("ai-query").value.trim();
  if (!chosenProvider || !chosenModel) {
    $("answer-state").textContent = "Ingen modell tilgjengelig"; $("answer-state").className = "answer-state warning";
    $("provider-processing").textContent = "Ingen tilgjengelig leverandør er valgt. Kontroller serveroppsettet.";
    return;
  }
  $("answer-content").replaceChildren();
  if (!portalReady) {
    $("ai-query").value = "";
    $("answer-state").textContent = "Tjenesten er ikke klar"; $("answer-state").className = "answer-state warning";
    $("portal-status").textContent = "AI-agenten er ikke klar ennå. Ingen tekst ble sendt.";
    return;
  }
  const inputProblem = queryInputProblem(query);
  if (inputProblem) {
    $("ai-query").value = "";
    $("answer-state").textContent = inputProblem.includes("personvernet") ? "Personvernfilter" : "Ugyldig sp\u00f8rsm\u00e5l";
    $("answer-state").className = "answer-state warning";
    item($("answer-content"), "p", inputProblem).className = "empty-answer";
    $("portal-status").textContent = inputProblem;
    revealInView($("ai-result"));
    return;
  }
  aiBusy = true; answerAbort = new AbortController(); $("ai-query").disabled = true; $("ai-button").disabled = true; $("ai-result").setAttribute("aria-busy", "true");
  const processing = providerChoices.find((choice) => choice.provider === chosenProvider && choice.model === chosenModel)?.processing;
  $("answer-state").textContent = "Søker, lager og kontrollerer svar …"; $("answer-state").className = "answer-state loading";
  item($("answer-content"), "p", processing === "external" ? "Ekstern leverandør behandler bare godkjente kildeutdrag …" : "Lokal leverandør arbeider med gjennomgåtte kildeutdrag …").className = "loading-message";
  $("portal-status").textContent = "AI-agenten søker og kontrollerer kildehenvisningene …";
  revealInView($("ai-result"));
  try {
    const data = await api("/api/answer", { method: "POST", signal: answerAbort.signal, headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: JSON.stringify({ query, provider: chosenProvider, model: chosenModel }) });
    if (generation !== answerGeneration) return;
    lastAnsweredQuery = query;
    conversationActive = true;
    renderAnswer(data.answer);
    $("portal-status").textContent = "AI-svaret er ferdig. Vurder kildeutdrag og kontrollstatus før bruk.";
    revealInView($("ai-result"));
  } catch (error) {
    if (generation === answerGeneration) {
      $("portal-status").textContent = visibleRequestError(error, "Kunne ikke lage et kontrollert svar. Kontroller at lokal modell og kildekatalog er tilgjengelige.");
      $("answer-state").textContent = "Svarfeil"; $("answer-state").className = "answer-state warning";
      $("answer-content").replaceChildren(); item($("answer-content"), "p", "Ingen nytt svar ble lagret.").className = "empty-answer";
      revealInView($("ai-result"));
    }
  } finally { if (generation === answerGeneration) { aiBusy = false; $("ai-query").disabled = false; $("ai-button").disabled = !$("ai-query").value.trim(); $("ai-result").setAttribute("aria-busy", "false"); } }
}
$("ai-form").addEventListener("submit", (event) => { event.preventDefault(); askAi(); });
$("ai-query").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.isComposing) { event.preventDefault(); $("ai-form").requestSubmit(); }
});
$("ai-query").addEventListener("input", () => {
  if (aiBusy) return;
  $("ai-button").disabled = !portalReady || !$("ai-query").value.trim();
  if (lastAnsweredQuery !== null && $("ai-query").value.trim() !== lastAnsweredQuery) {
    lastAnsweredQuery = null; $("answer-content").replaceChildren();
    $("answer-state").textContent = "Klar for et nytt spørsmål"; $("answer-state").className = "answer-state";
  }
});
$("ai-query").addEventListener("input", () => {
  $("ai-button").disabled = !portalReady || !chosenProvider || !$("ai-query").value.trim();
});
$("reset-conversation").addEventListener("click", async () => {
  ++answerGeneration; if (answerAbort) answerAbort.abort(); answerAbort = null; aiBusy = false;
  $("ai-query").disabled = false; $("answer-content").replaceChildren();
  lastAnsweredQuery = null; $("ai-result").setAttribute("aria-busy", "false");
  try {
    await api("/api/conversation/reset", { method: "POST", headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: "{}" });
    conversationActive = false;
    $("answer-state").textContent = "Samtalen er nullstilt"; $("answer-state").className = "answer-state";
    $("portal-status").textContent = "Samtalekonteksten er slettet.";
  } catch (error) { $("portal-status").textContent = visibleRequestError(error, "Kunne ikke nullstille samtalen."); }
  $("ai-button").disabled = !portalReady || !chosenProvider || !$("ai-query").value.trim();
});
async function loadPortal() {
  try {
    const data = await api("/api/portal");
    if (data.query_contract_version !== 1 || !Array.isArray(data.allowed_query_terms)
        || !Array.isArray(data.query_stopwords) || !Array.isArray(data.query_followup_modifiers)
        || !data.query_aliases || typeof data.query_aliases !== "object") {
      throw new Error("Serverversjonen for s\u00f8k er utdatert. Start Hamar-agenten p\u00e5 nytt.");
    }
    officialMenuUrl = data.category_reference === "https://www.hamar.kommune.no/meny/"
      ? data.category_reference : "https://www.hamar.kommune.no/meny/";
    allowedRealQueryTerms = new Set(data.allowed_query_terms);
    queryStopwords = new Set(data.query_stopwords || []);
    queryFollowupModifiers = new Set(data.query_followup_modifiers || []);
    queryAliases = new Map(Object.entries(data.query_aliases || {}));
    portalReady = true; $("search-button").disabled = false; $("ai-button").disabled = !$("ai-query").value.trim();
    let providerData = { choices: [] };
    try { providerData = await api("/api/providers"); } catch (_) { /* Ordinary search remains usable if model discovery fails. */ }
    populateProviders(providerData, data.provider);
    const mockMode = data.provider.startsWith("mock");
    $("answer-help").textContent = mockMode ? "Demoen bruker mock, ikke en ekte språkmodell. Resultatene er syntetiske." : "Leverandør: " + data.provider + ". Ordrette kildeutdrag kontrolleres; samsvar er ikke semantisk faktasjekk.";
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
  } catch (error) {
    portalReady = false;
    $("search-button").disabled = true; $("ai-button").disabled = true; $("provider-model").disabled = true;
    $("portal-status").textContent = error.message;
    renderSearchMessage("Serveren m\u00e5 startes p\u00e5 nytt", error.message);
    $("answer-state").textContent = "Tjenesten er ikke klar"; $("answer-state").className = "answer-state warning";
    item($("answer-content"), "p", error.message).className = "empty-answer";
  }
}
loadPortal();
