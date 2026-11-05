import test from "node:test";
import assert from "node:assert/strict";
import {readLiveAttempts, renderLiveSession, sessionToday} from "../src/live-session.mjs";

const date = "2026-11-05";
const capture = "market_data_xnys.yml";
const classic = "classic_sp500.yml";
const plan = {from: date, through: "2026-11-08", days: {
  [date]: {open: date + "T14:30:00Z", close: date + "T21:00:00Z", lanes: [
    {workflow: capture, slots: [], due: [date + "T23:07:00Z"]},
    {workflow: classic, slots: ["IL-010"], due: ["2026-11-06T00:30:00Z"],
      accounting_step: "Record next-open paper ledger"},
  ]},
}};

test("Today follows the NYSE date and the published exchange calendar", () => {
  assert.equal(sessionToday(plan, Date.parse(date + "T14:00:00Z")).phase, "before");
  assert.equal(sessionToday(plan, Date.parse(date + "T20:00:00Z")).phase, "open");
  assert.equal(sessionToday(plan, Date.parse("2026-11-06T01:20:00Z")).date, date);
  assert.equal(sessionToday(plan, Date.parse("2026-11-07T16:00:00Z")).phase, "closed");
  assert.equal(sessionToday(plan, Date.parse("2026-11-09T16:00:00Z")).phase, "unavailable");
});

test("Shared capture success and skipped accounting do not certify an algorithm", async () => {
  const now = Date.parse("2026-11-06T02:00:00Z");
  const session = sessionToday(plan, now);
  const run = {id: 7, run_attempt: 1, head_branch: "main", event: "schedule", path: ".github/workflows/" + capture,
    created_at: "2026-11-06T00:03:00Z", status: "completed", conclusion: "success"};
  const job = {id: 32, name: "consume-classic_sp500 / classic", started_at: "2026-11-06T00:15:00Z",
    status: "completed", conclusion: "success", steps: [{name: "Record next-open paper ledger", conclusion: "skipped"}]};
  const fetcher = async url => ({ok: true, json: async () => String(url).includes("/jobs") ?
    {total_count: 2, jobs: [{id: 31, name: "capture", status: "completed", conclusion: "success"}, job]} :
    {total_count: 2, workflow_runs: [run, {...run, id: 8, created_at: date + "T02:00:00Z"}]}});
  const live = await readLiveAttempts(session, fetcher);
  assert.deepEqual(live.attempts.map(a => [a.workflow, a.status]), [[capture, "success"], [classic, "unknown"]]);
  assert.match(renderLiveSession(session, {date, status:"ok", checked:now, ...live}, now), /0 \/ 1/);
  job.steps[0].conclusion = "success";
  const verified = await readLiveAttempts(session, fetcher);
  assert.match(renderLiveSession(session, {date, status:"ok", checked:now, ...verified}, now), /1 \/ 1/);
});

test("Unavailable and truncated data show the plan without a fabricated execution count", async () => {
  const now = Date.parse(date + "T22:00:00Z");
  const session = sessionToday(plan, now);
  await assert.rejects(readLiveAttempts(session, async () => ({ok:true, json:async () =>
    ({total_count:101, workflow_runs:[]})})), /Incomplete/);
  const html = renderLiveSession(session, {date, status:"error"}, now);
  assert.match(html, /algoritmos previstos/);
  assert.doesNotMatch(html, /0 \/ 1/);
  assert.match(html, /GitHub no responde/);
});


test("Today's headline explains active cohort versus scheduled and unscheduled strategies", () => {
 const now=Date.parse("2026-11-05T14:10:00Z");
 const session=sessionToday(plan,now);
 const sample={date,status:"ok",checked:now,attempts:[],partial:false};
 const html=renderLiveSession(session,sample,now,false,35);
 assert.match(html,/0 \/ 1/);
 assert.match(html,/<strong>35<\/strong> en competición/);
 assert.match(html,/<strong>1<\/strong> programadas hoy/);
 assert.match(html,/<strong>34<\/strong> sin ejecución prevista hoy/);
 assert.match(html,/class="session-live-cohort"/);
 assert.match(html,/estrategias con sus flujos completados hoy/);
 const withoutRoster=renderLiveSession(session,sample,now,false,null);
 assert.doesNotMatch(withoutRoster,/<strong>35<\/strong> en competición/);
 assert.match(withoutRoster,/comprobando el catálogo activo/);
 const badRoster=renderLiveSession(session,sample,now,false,0);
 assert.doesNotMatch(badRoster,/sin ejecución prevista hoy/);
});

test("The session count is calculated from the actual slots, not hardcoded at 25", () => {
 const many=structuredClone(plan);
 many.days[date].lanes[1].slots=Array.from({length:25},(_,i)=>"IL-"+String(10+i).padStart(3,"0"));
 const session=sessionToday(many,Date.parse("2026-11-05T14:00:00Z"));
 const now=Date.parse("2026-11-05T14:00:00Z");
 const html=renderLiveSession(session,{date,status:"ok",checked:now,attempts:[],partial:false},now,false,35);
 assert.match(html,/0 \/ 25/);
 assert.match(html,/<strong>35<\/strong> en competición/);
 assert.match(html,/<strong>25<\/strong> programadas hoy/);
 assert.match(html,/<strong>10<\/strong> sin ejecución prevista hoy/);
});
