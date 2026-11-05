const REPOSITORY = "idealab2026/laboratorio-cuantitativo";
const ACTIONS_API = "https://api.github.com/repos/" + REPOSITORY + "/actions/runs";
const ACTIONS_WEB = "https://github.com/" + REPOSITORY + "/actions/runs/";
const CAPTURE = "market_data_xnys.yml";
export const LIVE_REFRESH_MS = 180_000;
const labels = {
  [CAPTURE]: "Captura de mercado",
  classic_sp500: "Clásicos S&P 500",
  weekly_ml_daily: "ML semanal · valoración",
  weekly_ml: "ML semanal · señal",
  tfg_ahp: "AHP",
  capital_cycle: "Capital Cycle",
  buy_the_dip_strategy: "Buy The Dip",
  timesfm_daily: "TimesFM",
  timesfm_weekly: "TimesFM · señal semanal",
  timesfm_one_day: "TimesFM · 1 día",
  genetic_sp500: "Genético S&P 500",
};
const statuses = {
  waiting: "Previsto",
  queued: "En cola",
  running: "En curso",
  success: "Completado",
  failure: "Con incidencias",
  unknown: "Sin confirmar",
};
const madrid = new Intl.DateTimeFormat("es-ES", {
  timeZone: "Europe/Madrid", hour: "2-digit", minute: "2-digit",
});
const madridDate = new Intl.DateTimeFormat("sv-SE", {timeZone: "Europe/Madrid", dateStyle: "short"});
const newYorkDate = new Intl.DateTimeFormat("sv-SE", {timeZone: "America/New_York", dateStyle: "short"});
const longDate = new Intl.DateTimeFormat("es-ES", {timeZone: "UTC", dateStyle: "full"});
const dayMs = 86_400_000;
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const escape = value => String(value ?? "").replace(/[&<>"']/g, c =>
  ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[c]);
const labelFor = workflow => {
  if (typeof workflow !== "string") return undefined;
  const key = workflow === CAPTURE ? CAPTURE : workflow.replace(/\.yml$/, "");
  return Object.hasOwn(labels, key) ? labels[key] : undefined;
};
const dayAfter = day => new Date(Date.parse(day) + dayMs).toISOString().slice(0, 10);

export function sessionToday(plan, now = Date.now()) {
  const date = newYorkDate.format(now);
  if (!plan || !datePattern.test(plan.from) || !datePattern.test(plan.through) ||
      date < plan.from || date > plan.through || !plan.days) return {date, phase: "unavailable"};
  const session = plan.days[date];
  if (!session) {
    const next = Object.keys(plan.days).sort().find(day => day > date);
    return {date, phase: "closed", next: plan.days[next]?.open};
  }
  const open = Date.parse(session.open), close = Date.parse(session.close);
  if (!(open < close) || !Array.isArray(session.lanes) ||
      !session.lanes.length || session.lanes.some(lane =>
        !labelFor(lane.workflow) || !Array.isArray(lane.slots) ||
        lane.slots.some(slot => !/^IL-\d{3}$/.test(slot)) ||
        !Array.isArray(lane.due) || !lane.due.length ||
        lane.due.some(time => !Number.isFinite(Date.parse(time))))) {
    return {date, phase: "unavailable"};
  }
  return {date, open, close, lanes: session.lanes,
    phase: now < open ? "before" : now < close ? "open" : "after"};
}

function outcome(record, accountingStep) {
  if (record.status === "in_progress") return "running";
  if (["queued", "requested", "pending", "waiting"].includes(record.status)) return "queued";
  if (["failure", "cancelled", "timed_out", "action_required", "startup_failure"].includes(record.conclusion)) return "failure";
  if (record.status === "completed" && record.conclusion === "success" &&
      (!accountingStep || record.steps?.some(step => step.name === accountingStep && step.conclusion === "success"))) return "success";
  return "unknown";
}

async function getJSON(url, fetcher) {
  const response = await fetcher(url, {cache: "no-store", credentials: "omit", signal: AbortSignal.timeout(12000)});
  if (!response.ok) throw new Error("GitHub Actions unavailable");
  return response.json();
}

export async function readLiveAttempts(session, fetcher = fetch, finishedJobs = new Map()) {
  const nextDay = dayAfter(session.date);
  const url = new URL(ACTIONS_API);
  url.search = new URLSearchParams({event: "schedule", created: session.date + ".." + nextDay, per_page: "100"});
  const data = await getJSON(url, fetcher);
  if (!Array.isArray(data.workflow_runs) || !Number.isInteger(data.total_count) ||
      data.total_count > data.workflow_runs.length) throw new Error("Incomplete run list");
  const lanes = new Map(session.lanes.map(lane => [lane.workflow, lane]));
  const end = Date.parse(nextDay + "T12:00:00Z");
  const runs = data.workflow_runs.filter(run => run.event === "schedule" && run.head_branch === "main" &&
    Number.isSafeInteger(run.id) && run.id > 0 && Date.parse(run.created_at) >= session.close &&
    Date.parse(run.created_at) < end && lanes.has(run.path?.split("/").at(-1)));
  const attempts = [];
  let partial = false;
  const add = (workflow, record, run, job = false) => {
    const time = Date.parse(job ? record.started_at || run.created_at : run.created_at);
    if (!Number.isFinite(time)) return;
    const status = outcome(record, job ? lanes.get(workflow)?.accounting_step : null);
    attempts.push({workflow, status, time, url: ACTIONS_WEB + run.id + (job ? "/job/" + record.id : "")});
  };
  await Promise.all(runs.map(async run => {
    const workflow = run.path.split("/").at(-1);
    if (workflow !== CAPTURE) {
      add(workflow, run, run);
      return;
    }
    try {
      const key = run.id + "/" + run.run_attempt;
      let jobs = finishedJobs.get(key);
      if (!jobs) {
        const result = await getJSON(ACTIONS_API + "/" + run.id + "/jobs?per_page=100", fetcher);
        if (!Array.isArray(result.jobs) || result.total_count > result.jobs.length) throw new Error("Incomplete job list");
        jobs = result.jobs;
        if (run.status === "completed") {
          if (finishedJobs.size >= 10) finishedJobs.clear();
          finishedJobs.set(key, jobs);
        }
      }
      let sawCapture = false;
      for (const job of jobs) {
        if (!Number.isSafeInteger(job.id) || job.id <= 0) continue;
        const name = job.name?.split(" / ")[0];
        if (name === "capture") {
          sawCapture = true;
          add(CAPTURE, job, run, true);
        } else if (name?.startsWith("consume-")) {
          const child = name.slice(8) + ".yml";
          if (lanes.get(child)?.accounting_step) add(child, job, run, true);
        }
      }
      if (!sawCapture) attempts.push({workflow: CAPTURE, time: Date.parse(run.created_at),
        status: run.status === "completed" ? "unknown" : outcome(run), url: ACTIONS_WEB + run.id});
    } catch {
      partial = true;
      attempts.push({workflow: CAPTURE, time: Date.parse(run.created_at), status: "unknown", url: ACTIONS_WEB + run.id});
    }
  }));
  return {attempts: attempts.sort((a, b) => a.time - b.time), partial};
}

function laneStatus(attempts, due, now, verified) {
  if (attempts.some(attempt => attempt.status === "running")) return "running";
  if (attempts.some(attempt => attempt.status === "queued")) return "queued";
  if (attempts.some(attempt => attempt.status === "success")) return "success";
  if (attempts.some(attempt => attempt.status === "failure")) return "failure";
  if (attempts.length || (!verified && now >= due[0]) || now > due.at(-1) + 150 * 60_000) return "unknown";
  return "waiting";
}

function clock(time, session) {
  const next = madridDate.format(time) !== madridDate.format(session.open);
  return madrid.format(time) + (next ? " (+1)" : "");
}

export function renderLiveSession(session, live, now = Date.now(), loadingPlan = false, competingStrategies = null) {
  const date = longDate.format(new Date(session.date + "T12:00:00Z"));
  const phase = {before: "Antes de la apertura", open: "Mercado abierto",
    after: "Mercado cerrado", closed: "Sin sesión bursátil", unavailable: "Calendario pendiente"};
  const button = '<button type="button" class="smallbtn" data-action="live-session-refresh">Actualizar</button>';
  const header = '<div class="session-live-heading"><div><h3>' + escape(date) +
    '</h3><p>' + phase[session.phase] + ' · Mercado de Nueva York</p></div>' + button + '</div>';
  if (session.phase === "unavailable") {
    return header + '<p role="status" class="session-live-note">' +
      (loadingPlan ? "Cargando el calendario oficial de la sesión…" : "No hay un calendario publicado que cubra esta fecha.") + '</p>';
  }
  if (session.phase === "closed") {
    return header + '<p class="session-live-note">' + (session.next ?
      'Próxima apertura: ' + escape(new Intl.DateTimeFormat("es-ES", {timeZone:"Europe/Madrid",
        dateStyle:"long", timeStyle:"short"}).format(new Date(session.next))) + ' (Madrid).' : "La próxima apertura se publicará con el calendario.") + '</p>';
  }
  const latest = live?.date === session.date ? live : null;
  const attempts = latest?.attempts ?? [];
  const verified = latest?.status === "ok" && !latest.partial;
  const rows = [...session.lanes].sort((a, b) => a.workflow === CAPTURE ? -1 :
    b.workflow === CAPTURE ? 1 : Date.parse(a.due[0]) - Date.parse(b.due[0])).map(lane => {
    const observed = attempts.filter(attempt => attempt.workflow === lane.workflow);
    const due = lane.due.map(Date.parse);
    return {...lane, observed, due, status: laneStatus(observed, due, now, verified)};
  });
  const slots = new Set(rows.flatMap(row => row.slots));
  const active = rows.filter(row => row.slots.length);
  const done = [...slots].filter(slot => active.filter(row => row.slots.includes(slot))
    .every(row => row.status === "success")).length;
  const running = new Set(active.filter(row => ["queued", "running"].includes(row.status)).flatMap(row => row.slots)).size;
  const failures = active.filter(row => row.status === "failure").length;
  const end = Math.max(session.close, ...rows.flatMap(row => row.due), ...attempts.map(a => a.time));
  const position = time => Math.max(0, Math.min(100, 100 * (time - session.open) / (end - session.open)));
  const style = time => "left:" + position(time).toFixed(2) + "%";
  const statusText = latest?.status === "error" ? (latest.checked ?
    "GitHub no responde. Última lectura a las " + madrid.format(latest.checked) + " (Madrid)." : "GitHub no responde. El horario previsto sigue disponible.") :
    latest?.partial ? "Lectura parcial de GitHub Actions." :
    latest?.checked ? "Última consulta " + madrid.format(latest.checked) + " (Madrid)." : "Consultando GitHub Actions…";
  const marketWidth = position(session.close).toFixed(2);
  const nowMarker = now >= session.open && now <= end ? '<i class="session-live-now" style="' + style(now) + '" aria-hidden="true"></i>' : "";
  const chartRows = rows.map(row => {
    const planned = row.due.map(time => '<i class="session-live-marker planned" style="' + style(time) +
      '" title="Previsto ' + clock(time, session) + '" aria-hidden="true"></i>').join("");
    const observed = row.observed.map(a => '<a class="session-live-marker ' + a.status + '" style="' + style(a.time) +
      '" href="' + escape(a.url) + '" target="_blank" rel="noopener noreferrer" title="' + statuses[a.status] + ' · ' +
      clock(a.time, session) + '" aria-label="' + labelFor(row.workflow) + ', ' + statuses[a.status] + ', ' +
      clock(a.time, session) + '"></a>').join("");
    return '<div class="session-live-lane"><div class="session-live-lane-name"><strong>' + labelFor(row.workflow) +
      '</strong><small>' + (row.slots.length ? row.slots.length + (row.slots.length === 1 ? " algoritmo" : " algoritmos") : "Fuente compartida") +
      '</small></div><div class="session-live-track" style="--market-width:' + marketWidth + '%">' +
      nowMarker + planned + observed + '</div><span class="session-live-status ' + row.status + '">' +
      statuses[row.status] + '<small>' + clock(row.observed.at(-1)?.time ?? row.due[0], session) + '</small></span></div>';
  }).join("");
  const counts = latest?.checked ? '<strong>' + done + ' / ' + slots.size +
    '</strong><span>estrategias con sus flujos completados hoy</span><span>' + running + ' en cola o en curso</span>' :
    '<strong>' + slots.size + '</strong><span>estrategias previstas hoy</span>';
  // The comparison cohort is defined by the verified roster. The plan alone
  // cannot prove how many strategies are active but not scheduled today.
  const hasCohort = Number.isInteger(competingStrategies) && competingStrategies >= slots.size;
  const unscheduled = hasCohort ? competingStrategies - slots.size : null;
  const cohortLine = hasCohort ?
    '<div class="session-live-cohort" role="note" aria-label="Desglose de estrategias en competición para esta sesión">' +
    '<span><strong>' + competingStrategies + '</strong> en competición</span>' +
    '<span class="session-live-cohort-equals">=</span>' +
    '<span><strong>' + slots.size + '</strong> programadas hoy</span>' +
    '<span class="session-live-cohort-equals">+</span>' +
    '<span><strong>' + unscheduled + '</strong> sin ejecución prevista hoy</span></div>' :
    '<p class="session-live-cohort-pending">Mostrando solo las programadas para esta sesión; comprobando el catálogo activo.</p>';
  return header + '<div class="session-live-summary">' + counts +
    (failures ? '<span class="session-live-status failure">' + failures + (failures === 1 ? ' flujo con incidencias' : ' flujos con incidencias') + '</span>' : "") +
    '</div>' + cohortLine + '<p class="session-live-freshness" role="status">' + statusText + ' Actualización cada 3 min.</p>' +
    '<div class="session-live-scroll" tabindex="0" role="region" aria-label="Cronología de ejecuciones">' +
    '<div class="session-live-chart"><div class="session-live-lane session-live-axis"><span>Motor</span><div class="session-live-track">' +
    '<span class="session-live-open">Apertura ' + clock(session.open, session) + '</span>' +
    '<span class="session-live-close" style="' + style(session.close) + '">Cierre ' + clock(session.close, session) + '</span>' +
    '<span class="session-live-end">' + clock(end, session) + '</span></div><span>Estado</span></div>' + chartRows + '</div></div>' +
    '<div class="session-live-legend"><span><i class="legend-planned"></i>Horario previsto</span>' +
    '<span><i class="legend-run"></i>Ejecución observada</span><span><i class="legend-market"></i>Mercado abierto</span>' +
    '<span><i class="legend-now"></i>Ahora</span><span>Hora de Madrid · (+1) día siguiente</span></div>' +
    '<p class="session-live-note">El gráfico sigue los procesos programados de GitHub Actions. Las valoraciones y las operaciones se verifican en sus diarios.</p>';
}
