"use strict";
const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="hamar-token"]').content;
function item(parent, tag, text) { const el = document.createElement(tag); el.textContent = text; parent.appendChild(el); return el; }
async function api(path, options = {}) {
  const response = await fetch(path, options);
  let data;
  try { data = await response.json(); }
  catch (_) { throw new Error("Tjenesten returnerte et uleselig svar. Prøv igjen, eller oppdater siden."); }
  if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("Tjenesten returnerte et ugyldig svar. Prøv igjen senere.");
  if (!response.ok) {
    const error = new Error(typeof data.error === "string" ? data.error : "Forespørselen feilet. Prøv igjen senere.");
    error.code = data.error_code; error.retryable = data.retryable !== false;
    throw error;
  }
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
let officialMunicipalHosts = new Set(["www.hamar.kommune.no"]);
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
let providerBusy = true;
let lastSearch = null;
let providerChoices = [];
let answerAbort = null;
let conversationActive = false;
let chosenProvider = null;
let chosenModel = null;
let municipalSelectionKey = "";
let municipalResetRequired = false;
function sourceLink(parent, citation) {
  if (!citation.url) { item(parent, "p", "Syntetisk demo. Ingen kommunal kildeside.").className = "source-meta"; return; }
  try {
    const url = new URL(citation.url);
    if (url.protocol !== "https:" || !officialMunicipalHosts.has(url.hostname) || url.username || url.password || (url.port && url.port !== "443")) return;
    const link = item(parent, "a", url.hostname + url.pathname + " ↗");
    link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; link.className = "source-link";
  } catch (_) { /* Invalid citations are not turned into clickable links. */ }
}
function officialMenuLink(parent, url = officialMenuUrl) {
  try {
    const official = new URL(url);
    if ((official.href !== "https://www.hamar.kommune.no/meny/" && !(officialMunicipalHosts.has(official.hostname) && official.pathname === "/"))
        || official.protocol !== "https:" || official.username || official.password || (official.port && official.port !== "443")) return;
    const wrapper = item(parent, "p", ""); wrapper.className = "official-menu-fallback";
    const link = item(wrapper, "a", official.hostname === "www.hamar.kommune.no" ? "Se Hamar kommunes offisielle tjenestemeny" : "Se kommunens offisielle nettside");
    link.href = official.href; link.target = "_blank"; link.rel = "noopener noreferrer";
  } catch (_) { /* Only the fixed official menu URL can be presented. */ }
}
function sourceDate(value, includeTime = false) {
  if (typeof value !== "string" || !value.trim()) return "ikke oppgitt";
  const text = value.trim();
  const calendarOnly = /^\d{4}-\d{2}-\d{2}$/.test(text);
  const date = new Date(calendarOnly ? text + "T00:00:00Z" : text);
  if (!Number.isFinite(date.getTime())) return "ikke oppgitt";
  if (calendarOnly) {
    if (date.toISOString().slice(0, 10) !== text) return "ikke oppgitt";
    return date.toLocaleDateString("nb-NO", { timeZone: "UTC" });
  }
  return includeTime ? date.toLocaleString("nb-NO") : date.toLocaleDateString("nb-NO");
}
function provenance(parent, source) {
  if (source.synthetic === true) {
    item(parent, "p", "Syntetisk eksempel; ikke hentet fra kommunen").className = "source-meta";
    return;
  }
  if (source.historical_warning || source.approval_status === "historical_expired") {
    item(parent, "p", "Opplysningene kan ha endret seg. Se kommunens nettside for siste informasjon.").className = "notice";
  }
  // Full retrieval/publication/modification timestamps stay in API evidence.
  // A date alone does not prove a fresh observation in this request.
}
function renderSearch(data) {
  $("search-results").replaceChildren();
  $("search-area").hidden = false;
  $("search-area").setAttribute("aria-busy", "false");
  const count = data.results.length;
  $("result-count").textContent = count === 0 ? "Ingen treff" : count === 1 ? "Vi fant én side som kan hjelpe deg." : `Vi fant ${count} sider som kan hjelpe deg.`;
  if (!data.results.length) {
    const card = item($("search-results"), "article", ""); card.className = "result-card";
    item(card, "h3", "Vi fant ikke informasjon om dette.");
    item(card, "p", data.query_status === "input_rejected" ? "Skriv et søkeord uten personopplysninger." : "Prøv et annet søkeord eller se kommunens tjenestemeny.");
    officialMenuLink(card, data.official_menu_url || officialMenuUrl);
  }
  data.results.forEach((hit) => {
    const card = item($("search-results"), "article", ""); card.className = "result-card";
    item(card, "p", hit.synthetic ? "SYNTETISK EKSEMPEL" : "Kilde").className = "eyebrow";
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
  $("search-area").setAttribute("aria-busy", "true");
  $("search-area").hidden = false;
  $("portal-status").textContent = "Søker i gjennomgåtte kommunale utdrag …"; $("search-button").disabled = true; $("search-button").querySelector(".button-label").textContent = "Søker …";
  try {
    const data = await api("/api/search", { method: "POST", headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: JSON.stringify(lastSearch) });
    if (generation !== searchGeneration) return;
    renderSearch(data); $("portal-status").textContent = "Søket er ferdig.";
    revealInView($("search-area"));
    document.querySelectorAll(".category-card").forEach((c) => (c.classList.toggle("active", c.dataset.service === selectedService), c.setAttribute("aria-pressed", String(c.dataset.service === selectedService))));
  } catch (error) { if (generation === searchGeneration) {
    const message = visibleRequestError(error, "Kan ikke kontakte den lokale tjenesten. Kontroller at Aisha Agent fortsatt kjører.");
    $("portal-status").textContent = message; renderSearchMessage("Søket kunne ikke fullføres", message); revealInView($("search-area"));
  } }
  finally { if (generation === searchGeneration) { $("search-area").setAttribute("aria-busy", "false"); $("search-button").disabled = false; $("search-button").querySelector(".button-label").textContent = "Søk"; } }
}
$("search-form").addEventListener("submit", (event) => { event.preventDefault(); searchPortal(); });
$("query").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.isComposing) { event.preventDefault(); $("search-form").requestSubmit(); }
});
$("clear-category").addEventListener("click", () => { selectedCategory = null; selectedService = null; searchPortal(); });
function showMunicipalMenu() {
  $("municipal-topic-menu").hidden = false;
  $("municipal-back-to-menu").hidden = true;
  $("categories-title").focus();
  revealInView($("municipal-topic-menu"));
}
$("municipal-back-to-menu").addEventListener("click", showMunicipalMenu);
function addTechnicalDetails(container, answer) {
  const details = item(container, "details", ""); details.className = "technical-details";
  item(details, "summary", "Teknisk kontroll og kildesporing");
  const body = item(details, "div", ""); body.className = "technical-body";
  if (answer.result) {
    const result = answer.result;
    item(body, "p", "Leverandør: " + result.provider).className = "source-meta";
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
  $("ai-result").hidden = false;
  const container = $("answer-content"); container.replaceChildren();
  if (answer.is_follow_up) item(container, "p", "Oppfølgingsspørsmål: Kildene er søkt på nytt; tidligere svar brukes ikke som evidens.").className = "verification-note";
  // Timing, provider IDs and full verifier records remain in developer/API evidence.
  const result = answer.result;
  const findings = result?.verification?.findings || [];
  const claims = result?.claims || [];
  let stateText = "Krever vurdering", stateClass = "answer-state warning";
  if (answer.answer_status === "demo" && !findings.length) { stateText = "Syntetisk demo"; stateClass = "answer-state"; }
  if (answer.answer_status === "evidence_checked" && claims.length && !findings.length) {
    stateText = "Svar med kilder"; stateClass = "answer-state checked";
  } else if (answer.answer_status === "insufficient_evidence") {
    stateText = "Utilstrekkelig kildegrunnlag"; stateClass = "answer-state warning";
  } else if (answer.answer_status === "clarification_required") {
    stateText = "Kan du presisere sp\u00f8rsm\u00e5let?"; stateClass = "answer-state warning";
  } else if (answer.answer_status === "provider_unavailable") {
    stateText = "AI-leverandør utilgjengelig"; stateClass = "answer-state warning";
  } else if (answer.answer_status === "input_rejected") {
    stateText = "Spørsmålet ble avvist"; stateClass = "answer-state warning";
  }
  $("answer-state").textContent = stateText; $("answer-state").className = stateClass;
  item(container, "p", answer.answer_status === "insufficient_evidence"
    ? "Vi fant ikke nok informasjon til å svare. Prøv et annet spørsmål eller se kommunens nettside."
    : answer.message).className = "answer-message";
  if (!result || !claims.length) {
    item(container, "p", answer.answer_status === "insufficient_evidence" ? "Vi har ikke nok informasjon i kildene til å svare." : "Vi har ikke et svar med kilder å vise for dette spørsmålet.").className = "empty-answer";
    if (answer.citations.length) {
      const sources = item(container, "section", ""); sources.className = "answer-citations";
      item(sources, "h3", "Kilder for videre lesning");
      const linkedUrls = new Set();
      answer.citations.forEach((citation) => {
        if (citation.url && linkedUrls.has(citation.url)) return;
        if (citation.url) linkedUrls.add(citation.url);
        sourceLink(sources, citation); provenance(sources, citation);
      });
    }
    if (answer.answer_status === "insufficient_evidence" || answer.answer_status === "clarification_required") {
      officialMenuLink(container, answer.official_menu_url || officialMenuUrl);
    }
    // Refusal diagnostics remain in the separate API/CLI evidence.
    return;
  }
  if (findings.length) item(container, "p", "Automatisk kontroll fant forhold som må vurderes. Påstandene nedenfor er ikke bekreftet som riktige.").className = "notice";
  else item(container, "p", "Kildene vises sammen med svaret. Les kilden for mer informasjon.").className = "verification-note";
  const linkedUrls = new Set();
  claims.forEach((claim) => {
    const article = item(container, "article", ""); article.className = "answer-claim";
    item(article, "p", findings.length ? "AI-SVAR · KREVER VURDERING" : result.evidence_policy === "whole_reviewed_paragraph_verbatim" ? "KILDEUTDRAG VALGT AV AI" : "AI-SVAR").className = "answer-label";
    item(article, "p", claim.text).className = "answer-text";
    const sources = answer.citations.filter((citation) => citation.paragraph_id === claim.paragraph_id);
    if (claim.evidence_quote) {
      const excerpt = item(article, "section", ""); excerpt.className = "source-excerpt";
      item(excerpt, "h3", "Fra kilden"); item(excerpt, "blockquote", claim.evidence_quote);
    }
    const citationGroup = item(article, "div", ""); citationGroup.className = "answer-citations";
    if (!sources.length) item(citationGroup, "p", "Kildehenvisning mangler. Svaret må vurderes.").className = "notice";
    sources.forEach((citation) => {
      if (!citation.url || linkedUrls.has(citation.url)) return;
      const citationCard = item(citationGroup, "div", ""); citationCard.className = "citation-card"; linkedUrls.add(citation.url);
      item(citationCard, "p", "Kilde").className = "answer-label";
      item(citationCard, "p", citation.title).className = "citation-title"; sourceLink(citationCard, citation);
      provenance(citationCard, citation);
    });
  });
  // Full technical records remain available through the existing owned JSON API/CLI.
}
function providerDescription(choice) {
  if (!choice) return "Velg et AI-alternativ for å fortsette. OpenAI brukes bare når du velger det selv.";
  if (choice.provider === "mock") return choice.reason;
  if (choice.provider === "openai") return "Valgfri betalt AI fra OpenAI. Kommunale kildeutdrag sendes bare når du spør.";
  return "Lokal AI behandler spørsmålet på denne PC-en. Kildene vises sammen med svaret.";
}
function populateProviders(data, preferredProvider) {
  providerChoices = Array.isArray(data.choices) ? data.choices : [];
  const select = $("provider-model"); select.replaceChildren();
  let localIndex = 0;
  providerChoices.forEach((choice) => {
    const label = friendlyAiName(choice, choice.provider === "ollama" ? localIndex++ : 0);
    const option = item(select, "option", choice.provider === "openai" ? chatOptionLabel(choice, 0, false) : choice.available ? label : label + " · ikke klar");
    option.value = `${choice.provider}|${choice.model}`; option.disabled = !choice.available;
  });
  const previous = municipalSelectionKey || (chosenProvider && chosenModel ? chosenProvider + "|" + chosenModel : "");
  const retained = providerChoices.find((choice) => choice.available && choice.provider + "|" + choice.model === previous);
  const preferred = !previous && !conversationActive ? providerChoices.find((choice) => choice.available && choice.provider !== "openai" &&
    (`${choice.provider}:${choice.model}` === preferredProvider || (preferredProvider === "mock" && choice.provider === "mock"))) : null;
  const selected = municipalResetRequired ? null : retained || (!previous && !conversationActive ? preferred || providerChoices.find((choice) => choice.available && choice.provider === "ollama") ||
    providerChoices.find((choice) => choice.available && choice.provider === "mock") : null);
  if (selected) {
    select.value = `${selected.provider}|${selected.model}`;
    chosenProvider = selected.provider; chosenModel = selected.model;
    municipalSelectionKey = select.value;
    select.disabled = false;
    $("provider-processing").textContent = providerDescription(selected);
    $("answer-help").textContent = "Kildene vises sammen med svaret.";
  } else {
    chosenProvider = chosenModel = null;
    const selectable = providerChoices.some((choice) => choice.available);
    select.disabled = !selectable;
    if (providerChoices.length) {
      const placeholder = document.createElement("option"); placeholder.value = "";
      placeholder.textContent = "Velg AI …"; placeholder.disabled = true;
      select.prepend(placeholder); select.value = "";
    }
    $("provider-processing").textContent = selectable ? "Velg OpenAI selv hvis du ønsker betalt ekstern behandling." : "Lokal AI er ikke klar. Start Ollama og trykk Oppdater. Kommunalt søk kan fortsatt brukes.";
  }
  const paused = providerChoices.find((c) => c.provider === "openai" && !c.available);
  $("provider-openai-help").hidden = !paused;
  $("provider-openai-help").textContent = paused ? paused.reason || "OpenAI må aktiveres av eier før betalt bruk." : "";
  $("refresh-providers").hidden = Boolean(selected);
  renderMunicipalChoices();
  $("ai-button").disabled = !portalReady || !selected || !$("ai-query").value.trim();
}
$("provider-model").addEventListener("change", async () => {
  if (providerBusy) return;
  providerBusy = true; $("provider-model").disabled = true; $("reset-conversation").disabled = true;
  renderMunicipalChoices();
  ++answerGeneration; if (answerAbort) answerAbort.abort(); answerAbort = null; aiBusy = false;
  $("refresh-providers").disabled = true; $("retry-answer").hidden = true;
  $("ai-query").disabled = true; $("ai-result").setAttribute("aria-busy", "false");
  lastAnsweredQuery = null; $("answer-content").replaceChildren();
  const [provider, ...modelParts] = $("provider-model").value.split("|");
  const model = modelParts.join("|");
  const choice = providerChoices.find((item) => item.available && item.provider === provider && item.model === model);
  chosenProvider = choice?.provider || null; chosenModel = choice?.model || null;
  if (choice) municipalSelectionKey = provider + "|" + model;
  $("provider-processing").textContent = providerDescription(choice);
  $("answer-help").textContent = choice ? "Kildene vises sammen med svaret." : "Velg et AI-alternativ for å fortsette.";
  $("answer-state").textContent = "Nullstiller samtalen før modellbytte …"; $("answer-state").className = "answer-state loading";
  $("ai-button").disabled = true;
  try {
    await api("/api/conversation/reset", { method: "POST", headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: "{}" });
    conversationActive = false;
    municipalResetRequired = false;
    $("answer-state").textContent = "Modell valgt · samtalen nullstilt";
    $("refresh-providers").hidden = Boolean(choice);
    $("answer-state").className = "answer-state";
    $("ai-button").disabled = !portalReady || !choice || !$("ai-query").value.trim();
  } catch (error) {
    chosenProvider = chosenModel = null;
    municipalResetRequired = true;
    $("provider-model").disabled = true;
    $("provider-processing").textContent = "Kunne ikke nullstille den forrige samtalen. Bruk Oppdater modellvalg for å prøve igjen.";
    $("refresh-providers").hidden = false;
    $("answer-state").textContent = "Modellbyttet ble ikke fullført"; $("answer-state").className = "answer-state warning";
    $("portal-status").textContent = visibleRequestError(error, "Samtalen ble ikke nullstilt.");
  } finally {
    providerBusy = false; $("ai-query").disabled = false; $("reset-conversation").disabled = false; $("refresh-providers").disabled = false;
    if (chosenProvider) $("provider-model").disabled = false;
    $("ai-button").disabled = !portalReady || !chosenProvider || !$("ai-query").value.trim();
    renderMunicipalChoices();
  }
});
async function refreshMunicipalOptions() {
  if (!portalReady || providerBusy || aiBusy) return;
  providerBusy = true; $("ai-query").disabled = true; $("ai-button").disabled = true;
  $("provider-model").disabled = true;
  $("reset-conversation").disabled = true; $("refresh-providers").disabled = true; renderMunicipalChoices();
  try {
    const data = await api("/api/providers");
    populateProviders(data, "");
  } catch (_) {
    chosenProvider = chosenModel = null; $("provider-model").value = "";
    providerChoices = providerChoices.map((c) => ({ ...c, available: false }));
    $("provider-processing").textContent = "AI-valgene kunne ikke kontrolleres. Prøv Oppdater. Kommunalt søk kan fortsatt brukes.";
    $("refresh-providers").hidden = false;
  } finally {
    providerBusy = false; $("ai-query").disabled = false; $("reset-conversation").disabled = false; $("refresh-providers").disabled = false;
    $("ai-button").disabled = !portalReady || !chosenProvider || !$("ai-query").value.trim(); renderMunicipalChoices();
  }
}
async function askAi() {
  if (aiBusy || providerBusy || municipalResetRequired) return;
  $("retry-answer").hidden = true;
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
    $("portal-status").textContent = "Aisha er ikke klar ennå. Ingen tekst ble sendt.";
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
  aiBusy = true; answerAbort = new AbortController(); $("ai-query").disabled = true; $("ai-button").disabled = true; $("refresh-providers").disabled = true; $("ai-result").setAttribute("aria-busy", "true");
  conversationActive = true; // A submitted request may retain server context even if its response is lost.
  renderMunicipalChoices();
  $("ai-result").hidden = false;
  const processing = providerChoices.find((choice) => choice.provider === chosenProvider && choice.model === chosenModel)?.processing;
  $("answer-state").textContent = "Søker, lager og kontrollerer svar …"; $("answer-state").className = "answer-state loading";
  item($("answer-content"), "p", processing === "external" ? "OpenAI lager et svar med kommunale kilder …" : "Lokal AI lager et svar med kommunale kilder …").className = "loading-message";
  $("portal-status").textContent = "Aisha søker og kontrollerer kildehenvisningene …";
  revealInView($("ai-result"));
  try {
    const data = await api("/api/answer", { method: "POST", signal: answerAbort.signal, headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: JSON.stringify({ query, provider: chosenProvider, model: chosenModel }) });
    if (generation !== answerGeneration) return;
    lastAnsweredQuery = query;
    conversationActive = true;
    renderAnswer(data.answer);
    $("portal-status").textContent = data.answer.answer_status === "demo" ? "Det syntetiske demosvaret er ferdig. Dette er ikke et ekte AI-svar." : "AI-svaret er ferdig. Vurder kildeutdrag og kontrollstatus før bruk.";
    revealInView($("ai-result"));
  } catch (error) {
    if (generation === answerGeneration) {
      $("portal-status").textContent = visibleRequestError(error, "Kunne ikke lage et kontrollert svar. Kontroller at lokal modell og kildekatalog er tilgjengelige.");
      $("answer-state").textContent = "Svarfeil"; $("answer-state").className = "answer-state warning";
      $("refresh-providers").hidden = false;
      $("answer-content").replaceChildren(); item($("answer-content"), "p", "Ikke noe nytt svar ble lagret.").className = "empty-answer";
      item($("answer-content"), "p", visibleRequestError(error, "Kontroller forbindelsen til den lokale tjenesten og prøv igjen.")).className = "notice";
      $("retry-answer").hidden = error.retryable === false;
      revealInView($("ai-result"));
    }
  } finally { if (generation === answerGeneration) { aiBusy = false; $("ai-query").disabled = false; $("refresh-providers").disabled = false; $("ai-button").disabled = providerBusy || !chosenProvider || !$("ai-query").value.trim(); $("ai-result").setAttribute("aria-busy", "false"); renderMunicipalChoices(); } }
}
$("ai-form").addEventListener("submit", (event) => { event.preventDefault(); askAi(); });
$("retry-answer").addEventListener("click", () => askAi());
$("refresh-providers").addEventListener("click", async () => {
  if (aiBusy || providerBusy) return;
  if (!portalReady) { await loadPortal(); return; }
  if (municipalResetRequired) await resetMunicipalConversation();
  if (!municipalResetRequired) await refreshMunicipalOptions();
});
$("ai-query").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.isComposing) { event.preventDefault(); $("ai-form").requestSubmit(); }
});
$("ai-query").addEventListener("input", () => {
  if (aiBusy || providerBusy) return;
  $("retry-answer").hidden = true;
  $("ai-button").disabled = !portalReady || !$("ai-query").value.trim();
  if (lastAnsweredQuery !== null && $("ai-query").value.trim() !== lastAnsweredQuery) {
    lastAnsweredQuery = null; $("answer-content").replaceChildren();
    $("ai-result").hidden = true;
    $("answer-state").textContent = "Klar for et nytt spørsmål"; $("answer-state").className = "answer-state";
  }
});
$("ai-query").addEventListener("input", () => {
  $("ai-button").disabled = aiBusy || providerBusy || !portalReady || !chosenProvider || !$("ai-query").value.trim();
});
async function resetMunicipalConversation() {
  if (providerBusy) return;
  providerBusy = true; $("provider-model").disabled = true; $("reset-conversation").disabled = true; $("ai-button").disabled = true;
  renderMunicipalChoices();
  ++answerGeneration; if (answerAbort) answerAbort.abort(); answerAbort = null; aiBusy = false;
  $("refresh-providers").disabled = true;
  $("ai-query").disabled = true; $("answer-content").replaceChildren(); $("retry-answer").hidden = true;
  lastAnsweredQuery = null; $("ai-result").setAttribute("aria-busy", "false");
  $("answer-state").textContent = "Nullstiller samtalen …"; $("answer-state").className = "answer-state loading";
  try {
    await api("/api/conversation/reset", { method: "POST", headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: "{}" });
    conversationActive = false;
    municipalResetRequired = false;
    $("ai-result").hidden = true;
    populateProviders({ choices: providerChoices }, "");
    $("answer-state").textContent = "Samtalen er nullstilt"; $("answer-state").className = "answer-state";
    $("portal-status").textContent = "Samtalekonteksten er slettet.";
  } catch (error) {
    chosenProvider = chosenModel = null;
    municipalResetRequired = true;
    $("answer-state").textContent = "Samtalen kunne ikke nullstilles"; $("answer-state").className = "answer-state warning";
    $("refresh-providers").hidden = false;
    $("portal-status").textContent = visibleRequestError(error, "Kunne ikke nullstille samtalen. Bruk Oppdater modellvalg for å prøve igjen.");
  } finally {
    providerBusy = false; $("ai-query").disabled = false; $("reset-conversation").disabled = false; $("refresh-providers").disabled = false;
    if (chosenProvider) $("provider-model").disabled = false;
    $("ai-button").disabled = !portalReady || !chosenProvider || !$("ai-query").value.trim();
    renderMunicipalChoices();
  }
}
$("reset-conversation").addEventListener("click", resetMunicipalConversation);
// Category rendering keeps the original source-search mapping and click behavior.
function renderCategories(data) {
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
    button.setAttribute("aria-label", service.title + ": søk i kommunale kilder");
    const circle = item(button, "span", ""); circle.className = "category-icon"; circle.setAttribute("aria-hidden", "true");
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.setAttribute("viewBox", "0 0 24 24");
    icons[service.icon].forEach((d) => { const path = document.createElementNS("http://www.w3.org/2000/svg", "path"); path.setAttribute("d", d); svg.appendChild(path); });
    circle.appendChild(svg);
    const label = item(button, "span", service.title); label.className = "category-label";
    button.disabled = !data.categories.some((category) => category.id === service.category);
    button.addEventListener("click", () => {
      selectedCategory = service.category; selectedService = service.id;
      $("municipal-topic-menu").hidden = true;
      $("municipal-back-to-menu").hidden = false;
      $("query").value = service.query; searchPortal();
    });
  });
}

async function loadPortal() {
  providerBusy = true; $("refresh-providers").disabled = true; $("reset-conversation").disabled = true; $("ai-button").disabled = true;
  try {
    const data = await api("/api/portal");
    if (data.query_contract_version !== 1 || !Array.isArray(data.allowed_query_terms)
        || !Array.isArray(data.query_stopwords) || !Array.isArray(data.query_followup_modifiers)
        || !data.query_aliases || typeof data.query_aliases !== "object") {
      throw new Error("Serverversjonen for s\u00f8k er utdatert. Start Aisha Agent p\u00e5 nytt.");
    }
    officialMenuUrl = data.category_reference === "https://www.hamar.kommune.no/meny/"
      ? data.category_reference : "https://www.hamar.kommune.no/meny/";
    allowedRealQueryTerms = new Set(data.allowed_query_terms);
    queryStopwords = new Set(data.query_stopwords || []);
    queryFollowupModifiers = new Set(data.query_followup_modifiers || []);
    queryAliases = new Map(Object.entries(data.query_aliases || {}));
    officialMunicipalHosts = new Set(["www.hamar.kommune.no"]);
    if (Array.isArray(data.municipalities)) data.municipalities.forEach((municipality) => {
      try {
        const url = new URL("https://" + municipality.official_host + "/");
        if (!/^[a-z0-9.-]+$/u.test(municipality.official_host) || url.hostname !== municipality.official_host
            || url.username || url.password || url.port || !url.hostname.includes(".")) return;
        officialMunicipalHosts.add(url.hostname);
        [municipality.name, ...(municipality.aliases || [])].forEach((name) => {
          const normalized = name.normalize("NFC").toLocaleLowerCase("nb-NO").replaceAll("æ", "ae").replaceAll("ø", "o").replaceAll("å", "a");
          (normalized.match(/[\p{L}\p{N}]+/gu) || []).forEach((term) => queryStopwords.add(term));
        });
      } catch (_) { /* Only the backend's reviewed host identities become links. */ }
    });
    portalReady = true; $("search-button").disabled = false;
    let providerData = { choices: [] };
    try { providerData = await api("/api/providers"); } catch (_) { /* Ordinary search remains usable if model discovery fails. */ }
    populateProviders(providerData, data.provider);
    const mockMode = data.provider.startsWith("mock");
    $("answer-help").textContent = mockMode ? "Dette er en syntetisk demo, ikke ekte kommunale svar." : "Kildene vises sammen med svaret.";
    renderCategories(data);
  } catch (error) {
    portalReady = false;
    $("search-button").disabled = true; $("ai-button").disabled = true; $("provider-model").disabled = true;
    $("portal-status").textContent = error.message;
    renderSearchMessage("Serveren m\u00e5 startes p\u00e5 nytt", error.message);
    $("answer-state").textContent = "Tjenesten er ikke klar"; $("answer-state").className = "answer-state warning";
    item($("answer-content"), "p", error.message).className = "empty-answer";
  } finally {
    providerBusy = false; $("refresh-providers").disabled = false; $("reset-conversation").disabled = !portalReady;
    $("ai-button").disabled = !portalReady || !chosenProvider || !$("ai-query").value.trim();
    renderMunicipalChoices();
  }
}
loadPortal();

// General AI chat never shares municipal answers, sources or conversation state.
let chatReady = false, chatLoading = false, chatBusy = false, chatGeneration = 0;
let chatRevision = 0, chatChoices = [], chatSearchAllowed = false, chatAbort = null, chatLastRequest = null;
let chatMenuRequested = true;
let chatResetting = false, chatChecking = false, chatResetQueue = Promise.resolve();
let chatSelectionKey = "";
const chatProviderErrors = new Set();
function renderModelChoices(groupId, selectId, choices, blocked) {
  const group = $(groupId), select = $(selectId), known = new Map([...group.children].map((b) => [b.dataset.value, b]));
  let localIndex = 0;
  const buttons = choices.map((choice) => {
    const key = choice.provider + "|" + choice.model;
    let button = known.get(key);
    if (!button) {
      button = document.createElement("button"); button.type = "button"; button.className = "model-choice"; button.dataset.value = key;
      button.addEventListener("click", () => {
        if (button.disabled || select.value === key) return;
        select.value = key; return select.dispatchEvent(new Event("change", { bubbles: true }));
      });
    }
    button.textContent = choice.provider === "openai" ? chatOptionLabel(choice, 0, groupId === "chat-model-choices") : friendlyAiName(choice, choice.provider === "ollama" ? localIndex++ : 0) + (choice.available ? "" : " · ikke klar");
    button.disabled = blocked || !choice.available;
    button.setAttribute("aria-pressed", String(choice.available && key === select.value));
    return button;
  });
  if (buttons.length !== group.children.length || buttons.some((b, i) => b !== group.children[i])) group.replaceChildren(...buttons);
}
function renderMunicipalChoices() {
  renderModelChoices("municipal-model-choices", "provider-model", providerChoices, providerBusy || aiBusy || !portalReady);
  $("reset-conversation").hidden = !conversationActive && !municipalResetRequired;
  $("reset-conversation").disabled = providerBusy || !portalReady;
}
function friendlyAiName(choice, localIndex = 0) {
  if (choice.provider === "ollama") return localIndex ? `Lokal AI – alternativ ${localIndex + 1}` : "Lokal AI (Ollama)";
  if (choice.provider === "mock") return "Syntetisk demo";
  return choice.variant === "advanced" ? "OpenAI – utvidet modell" : choice.model === "gpt-4.1-mini" ? "OpenAI GPT-4.1 mini" : "OpenAI";
}
function chatOptionLabel(choice, localIndex = 0, chat = true) {
  const name = friendlyAiName(choice, localIndex);
  if (choice.provider !== "openai") return name + (choice.available ? "" : " · ikke klar");
  if (!choice.available) return name + (choice.availability_status === "paused" ? " · deaktivert av eier" : " · må klargjøres");
  return name + (chat && chatProviderErrors.has(choice.provider + "|" + choice.model) ? " · utilgjengelig etter feil" : " · konfigurert");
}
function refreshChatLabels() {
  let localIndex = 0;
  chatChoices.forEach((choice) => {
    const option = [...$("chat-provider").children].find((o) => o.value === choice.provider + "|" + choice.model);
    if (option) option.textContent = chatOptionLabel(choice, choice.provider === "ollama" ? localIndex++ : 0);
  });
}
function chatChoice() { return chatChoices.find((c) => c.available && c.provider + "|" + c.model === $("chat-provider").value); }
function updateChatControls() {
  const choice = chatChoice();
  $("chat-send").disabled = !chatReady || chatLoading || chatResetting || chatChecking || chatBusy || !choice || !$("chat-message").value.trim();
  $("chat-send").querySelector(".chat-send-label").textContent = chatBusy ? "Sender …" : "Send";
  $("chat-send").setAttribute("aria-label", chatBusy ? "Venter på svar fra Aisha" : choice?.provider === "openai" ? "Send melding til OpenAI, betalt ekstern behandling" : "Send melding");
  $("chat-provider").disabled = chatLoading || chatResetting || chatChecking || !chatChoices.length;
  $("chat-refresh").disabled = chatLoading || chatResetting || chatChecking || chatBusy;
  $("chat-refresh").hidden = chatReady && Boolean(choice) && !chatProviderErrors.has($("chat-provider").value);
  $("chat-retry").disabled = chatLoading || chatResetting || chatChecking || chatBusy;
  $("chat-web-search").disabled = !chatSearchAllowed || !choice?.available || chatBusy || chatLoading || chatResetting || chatChecking;
  $("chat-search-control").hidden = !chatSearchAllowed;
  if (!chatSearchAllowed) $("chat-web-search").checked = false;
  $("chat-processing").textContent = choice?.provider === "openai"
    ? "Valgfri betalt AI · meldinger behandles av OpenAI."
    : "";
  $("chat-processing").hidden = !choice || choice.provider !== "openai";
  renderModelChoices("chat-model-choices", "chat-provider", chatChoices, chatLoading || chatResetting || chatChecking);
}
function scrollChat() { $("chat-log").scrollTop = chatMenuRequested ? 0 : $("chat-log").scrollHeight; }
function renderChatMessage(message) {
  if (message.role === "user" || message.pending || !chatMenuRequested) {
    chatMenuRequested = false;
    const menu = $("chat-log").querySelector(".chat-empty");
    if (menu) menu.hidden = true;
    $("chat-back-to-menu").hidden = false;
  }
  const row = item($("chat-log"), "article", ""); row.className = "chat-row " + (message.role === "user" ? "user" : "assistant");
  if (message.role !== "user") {
    const avatar = document.querySelector(".chat-heading .robot-avatar").cloneNode(true); row.appendChild(avatar);
  }
  const bubble = item(row, "div", ""); bubble.className = "chat-bubble";
  item(bubble, "span", message.role === "user" ? "Du" : "Aisha").className = "chat-author";
  item(bubble, "p", message.text).className = "chat-text";
  if (message.pending) {
    row.classList.add("pending");
    const dots = item(bubble, "span", ""); dots.className = "typing-dots"; dots.setAttribute("aria-hidden", "true");
    for (let i = 0; i < 3; i++) item(dots, "i", "");
  }
  if (message.role !== "user" && !message.pending) {
    item(bubble, "p", message.ai_generated === false ? "Veiledning fra Aisha · ikke kildekontrollert" : "AI-generert svar · kan inneholde feil").className = "chat-answer-label";
    if (message.web_search_used) item(bubble, "p", message.research_verified === true
      ? "Kontrollert mot oppgitte kilder · ikke kommunal verifisering eller sannhetsgaranti"
      : "Kilder fra nettsøk · ikke kommunalt kildekontrollert").className = "chat-answer-label";
    if (message.web_search_used && Array.isArray(message.citations)) {
      const list = item(bubble, "ul", ""); list.className = "chat-citations";
      message.citations.forEach((citation) => {
        try {
          const url = new URL(citation.url);
          const host = url.hostname.replace(/[\u3002\uff0e\uff61]/gu, ".").replace(/\.+$/u, "").toLowerCase(), labels = host.split(".");
          if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443") || !host.includes(".")
              || /(^|\.)(localhost|local|internal|lan|home)$|\.home\.arpa$/u.test(host)
              || labels.some((label) => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/u.test(label))
              || /^(?:0x[0-9a-f]+|[0-9]+)$/u.test(labels.at(-1))) return;
          url.hostname = host;
          const li = item(list, "li", ""), link = item(li, "a", citation.title || url.hostname);
          link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer";
        } catch (_) { /* Never turn untrusted schemes into links. */ }
      });
    }
  }
  scrollChat(); return row;
}
function emptyChat() {
  $("chat-log").replaceChildren();
  showChatMenu(false);
}
function showChatMenu(focus = true) {
  chatMenuRequested = true;
  $("chat-back-to-menu").hidden = true;
  const existing = $("chat-log").querySelector(".chat-empty");
  if (existing) {
    existing.hidden = false;
    if (focus) existing.focus();
    scrollChat(); return;
  }
  const welcome = document.createElement("div"); welcome.className = "chat-empty";
  welcome.setAttribute("tabindex", "-1"); welcome.setAttribute("aria-label", "Forslag til samtaletema");
  $("chat-log").prepend(welcome);
  const avatar = document.querySelector(".chat-heading .robot-avatar").cloneNode(true);
  avatar.className = "robot-avatar chat-welcome-avatar"; avatar.setAttribute("aria-hidden", "true"); welcome.appendChild(avatar);
  const prompts = item(welcome, "div", ""); prompts.className = "chat-prompts";
  [["Forklar et tema", "Kan du forklare et tema på en enkel måte? Temaet er …", ["M3 4h7l2 2 2-2h7v15h-7l-2 2-2-2H3V4Z", "M12 6v15"]],
   ["Hjelp meg å skrive", "Hjelp meg å skrive en kort, generell tekst om …", ["m4 16 12-12 4 4-12 12-5 1 1-5Z", "m13 7 4 4"]],
   ["Hjelp med læring", "Kan du hjelpe meg å lære om …, steg for steg?", ["m2 8 10-5 10 5-10 5L2 8Z", "M6 10v7l6 3 6-3v-7"]],
   ["Still et spørsmål", "Jeg lurer på …", ["M3 4h18v13H9l-6 4V4Z", "M9 8a3 3 0 0 1 6 0c0 2-3 2-3 4", "M12 14v.1"]]].forEach(([label, text, paths]) => {
    const button = item(prompts, "button", ""); button.type = "button";
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg"); icon.setAttribute("viewBox", "0 0 24 24"); icon.setAttribute("aria-hidden", "true");
    paths.forEach((d) => { const path = document.createElementNS("http://www.w3.org/2000/svg", "path"); path.setAttribute("d", d); icon.appendChild(path); });
    button.appendChild(icon); item(button, "span", label);
    button.addEventListener("click", () => {
      chatMenuRequested = false; welcome.hidden = true; $("chat-back-to-menu").hidden = false;
      $("chat-message").value = text; updateChatControls(); $("chat-message").focus();
    });
  });
  if (focus) welcome.focus();
  scrollChat();
}
$("chat-back-to-menu").addEventListener("click", () => showChatMenu());
async function syncChatState(generation = chatGeneration) {
  const state = await api("/api/chat/state", { headers: { "X-Hamar-Token": token } });
  if (generation !== chatGeneration || state.revision < chatRevision) return null;
  chatRevision = state.revision;
  emptyChat(); state.messages.forEach(renderChatMessage);
  return state;
}
async function loadChat() {
  if (chatLoading || chatResetting || chatChecking || chatBusy) return;
  const generation = ++chatGeneration;
  chatLoading = true; updateChatControls();
  try {
    const previous = chatSelectionKey || $("chat-provider").value;
    const data = await api("/api/chat/options");
    if (generation !== chatGeneration) return;
    chatChoices = Array.isArray(data.choices) ? data.choices : []; chatSearchAllowed = data.web_search_allowed === true;
    const state = await syncChatState(generation);
    if (!state || generation !== chatGeneration) return;
    $("chat-provider").replaceChildren();
    const placeholder = item($("chat-provider"), "option", "Velg AI …"); placeholder.value = "";
    let localIndex = 0;
    chatChoices.forEach((choice) => {
      const option = item($("chat-provider"), "option", chatOptionLabel(choice, choice.provider === "ollama" ? localIndex++ : 0));
      option.value = choice.provider + "|" + choice.model; option.disabled = !choice.available;
    });
    const retained = chatChoices.find((c) => c.available && c.provider + "|" + c.model === previous);
    const local = !previous && state.messages.length === 0 ? chatChoices.find((c) => c.available && c.provider === "ollama" && c.default)
      || chatChoices.find((c) => c.available && c.provider === "ollama") : null;
    const selected = retained || local;
    $("chat-provider").value = selected ? selected.provider + "|" + selected.model : "";
    if (selected) chatSelectionKey = $("chat-provider").value;
    // Only an available local model can become the automatic default. Cloud is always manual.
    const pausedCloud = chatChoices.find((c) => c.provider === "openai" && c.variant !== "advanced" && !c.available);
    const pausedAdvanced = chatChoices.some((c) => c.variant === "advanced" && !c.available);
    $("chat-openai-help").hidden = !pausedCloud && !pausedAdvanced;
    $("chat-openai-help").textContent = pausedCloud ? pausedCloud.availability_status === "paused"
      ? friendlyAiName(pausedCloud) + " er deaktivert av eier. Aktivering av betalt bruk krever eierens godkjenning. Du kan fortsatt bruke lokal AI."
      : pausedCloud.reason || "OpenAI må klargjøres av den som drifter tjenesten. Du kan fortsatt bruke lokal AI."
      : pausedAdvanced ? "Utvidet AI er ikke aktivert. OpenAI-alternativet i listen kan fortsatt velges." : "";
    $("chat-search-help").textContent = chatSearchAllowed
      ? "Bruk bare godkjente offentlige kilder når du trenger oppdatert informasjon."
      : "";
    $("chat-search-help").hidden = !chatSearchAllowed;
    chatReady = true;
    $("chat-status").textContent = selected ? "" : state.messages.length ? "Velg AI for å starte en ny samtale." : "Lokal AI er ikke klar. Start Ollama og trykk Oppdater, eller velg et annet aktivert alternativ.";
  } catch (_) {
    if (generation !== chatGeneration) return;
    chatReady = false; $("chat-status").textContent = "Vi fikk ikke kontakt med Aisha. Prøv Oppdater om et øyeblikk.";
  } finally { if (generation === chatGeneration) { chatLoading = false; updateChatControls(); } }
}
async function resetChat() {
  const generation = ++chatGeneration;
  chatAbort?.abort(); chatBusy = false; chatLastRequest = null;
  chatResetting = true; chatLoading = false; chatChecking = false;
  $("chat-retry").hidden = true; $("chat-message").value = ""; emptyChat();
  $("chat-log").setAttribute("aria-busy", "false"); chatReady = false; updateChatControls();
  try {
    const operation = chatResetQueue.catch(() => {}).then(() => api("/api/chat/reset", { method: "POST", headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: "{}" }));
    chatResetQueue = operation.catch(() => {});
    const state = await operation;
    if (generation !== chatGeneration) return;
    chatRevision = state.revision; chatReady = true;
    $("chat-status").textContent = state.busy ? "Ny samtale er gjort klar. Aisha arbeider fortsatt med forrige melding; vent litt før du sender en ny." : "Ny samtale er klar. Ingen tidligere meldinger sendes videre.";
  } catch (_) { if (generation === chatGeneration) $("chat-status").textContent = "Nullstilling kunne ikke bekreftes. Trykk Oppdater før du sender noe nytt."; }
  finally { if (generation === chatGeneration) { chatResetting = false; updateChatControls(); } }
}
async function sendChat(retry = false) {
  if (!chatReady || chatBusy || chatLoading || chatResetting || chatChecking) return;
  const choice = chatChoice(); if (!choice) return;
  const generation = ++chatGeneration;
  if (retry && chatLastRequest) {
    const previousRequest = chatLastRequest;
    chatChecking = true; updateChatControls();
    try {
      const state = await syncChatState(generation);
      if (!state || generation !== chatGeneration || chatBusy || chatLoading || chatResetting || choice !== chatChoice()) return;
      if (state.revision !== previousRequest.revision) {
        chatLastRequest = null; $("chat-retry").hidden = true;
        $("chat-status").textContent = "Samtalen er hentet på nytt. Ingen ny betalt forespørsel ble sendt."; return;
      }
    } catch (_) { if (generation === chatGeneration) $("chat-status").textContent = "Kunne ikke kontrollere samtalen. Ingen ny forespørsel ble sendt."; return; }
    finally { if (generation === chatGeneration) { chatChecking = false; updateChatControls(); } }
  }
  if (generation !== chatGeneration || chatBusy || chatLoading || chatResetting || !chatReady) return;
  const message = retry && chatLastRequest ? chatLastRequest.message : $("chat-message").value.trim();
  if (!message) return;
  if (message.length > 1000 || /[\u0000-\u0008\u000b\u000c\u000e-\u001f]|@|https?:\/\/|\bsk-[A-Za-z0-9_-]{12,}/iu.test(message)) {
    $("chat-message").value = ""; $("chat-status").textContent = "Bruk maksimalt 1000 tegn uten personopplysninger, kontaktdata eller hemmeligheter."; return;
  }
  chatBusy = true; chatAbort = new AbortController();
  chatLastRequest = { message, provider: choice.provider, model: choice.model, web_search: $("chat-web-search").checked, revision: chatRevision };
  $("chat-retry").hidden = true; $("chat-message").value = "";
  renderChatMessage({ role: "user", text: message });
  const pending = renderChatMessage({ role: "assistant", text: "Aisha skriver", pending: true });
  $("chat-log").setAttribute("aria-busy", "true"); $("chat-status").textContent = "Aisha skriver …"; updateChatControls();
  try {
    const response = await api("/api/chat", { method: "POST", signal: chatAbort.signal,
      headers: { "Content-Type": "application/json", "X-Hamar-Token": token }, body: JSON.stringify(chatLastRequest) });
    if (generation !== chatGeneration) return;
    pending.remove(); renderChatMessage(response.reply); chatRevision = response.revision; chatLastRequest = null;
    chatProviderErrors.delete(choice.provider + "|" + choice.model); refreshChatLabels();
    $("chat-status").textContent = response.turns >= 8 ? "Start en ny samtale når du vil fortsette." : response.reply.web_search_used ? "Aisha har svart med kilder fra nettsøk." : "Du kan gjerne stille et oppfølgingsspørsmål.";
  } catch (error) {
    if (generation !== chatGeneration) return;
    pending.remove();
    if (choice.provider === "openai" && ["provider_authentication", "provider_quota", "provider_timeout", "provider_rate_limit", "provider_unavailable", "provider_model_unavailable", "provider_configuration", "provider_response_invalid", "provider_response_incomplete"].includes(error.code)) {
      chatProviderErrors.add(choice.provider + "|" + choice.model); refreshChatLabels();
    }
    $("chat-status").textContent = visibleRequestError(error, "Tilkoblingen ble brutt. Kontroller samtalen før du prøver igjen.");
    $("chat-retry").hidden = error.retryable === false;
    if (error.code === "chat_stale") { await syncChatState(generation); if (generation === chatGeneration) { chatLastRequest = null; $("chat-retry").hidden = true; } }
  } finally {
    if (generation === chatGeneration) { chatBusy = false; $("chat-log").setAttribute("aria-busy", "false"); updateChatControls(); }
  }
}
function selectAishaMode(chat) {
  $("municipal-mode").hidden = chat; $("chat-mode").hidden = !chat;
  $("mode-chat").setAttribute("aria-pressed", String(chat)); $("mode-municipal").setAttribute("aria-pressed", String(!chat));
  document.querySelector(".skip").href = chat ? "#chat-message" : "#query";
  if (chat) { $("chat-message").focus(); if (!chatLoading && !chatBusy && !chatResetting && !chatChecking) return loadChat(); }
  else return refreshMunicipalOptions();
}
$("mode-chat").addEventListener("click", () => selectAishaMode(true));
$("mode-municipal").addEventListener("click", () => selectAishaMode(false));
$("chat-refresh").addEventListener("click", loadChat);
$("chat-reset").addEventListener("click", resetChat);
$("chat-provider").addEventListener("change", async () => { const choice=chatChoice(); if (!choice) return; chatSelectionKey=choice.provider+"|"+choice.model; if (chatRevision || chatBusy || chatLastRequest) await resetChat(); updateChatControls(); });
$("chat-web-search").addEventListener("change", async () => { if (chatRevision || chatBusy || chatLastRequest) await resetChat(); updateChatControls(); });
$("chat-message").addEventListener("input", updateChatControls);
$("chat-message").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); $("chat-form").requestSubmit(); } });
$("chat-form").addEventListener("submit", (event) => { event.preventDefault(); sendChat(); });
$("chat-retry").addEventListener("click", () => sendChat(true));
document.addEventListener("DOMContentLoaded", () => selectAishaMode(true), { once: true });
