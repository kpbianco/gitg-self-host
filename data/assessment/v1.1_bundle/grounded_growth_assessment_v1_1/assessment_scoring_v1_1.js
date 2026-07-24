
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.GroundedGrowthAssessment = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const clamp = (x, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
  const mean = xs => xs.length ? xs.reduce((a,b)=>a+b,0)/xs.length : null;
  const sd = xs => {
    if (!xs.length) return null;
    const m = mean(xs);
    return Math.sqrt(xs.reduce((s,x)=>s+(x-m)*(x-m),0)/xs.length);
  };
  const median = xs => {
    if (!xs.length) return null;
    const a = [...xs].sort((x,y)=>x-y);
    const n = a.length;
    return n % 2 ? a[(n-1)/2] : (a[n/2-1] + a[n/2]) / 2;
  };
  const normalized = answer => answer == null || answer === "NA" ? null : clamp((Number(answer)-1)/4);
  const round = (x, n=4) => x == null ? null : Number(x.toFixed(n));

  function itemMap(spec) {
    const a = spec.assessment;
    return Object.fromEntries(
      [...a.core_items, ...a.adaptive_capability_clarifiers, ...a.adaptive_orientation_clarifiers]
        .map(x => [x.id, x])
    );
  }

function computeResponseQuality(spec, responseData) {
  const responses = responseData.responses || {};
  const timings = responseData.timings_seconds || {};
  const items = itemMap(spec);
  const capabilityAnswers = Object.entries(responses)
    .filter(([id,v]) => items[id] && (items[id].type === "capability" || items[id].type === "capability_clarifier") && v !== "NA" && v != null)
    .map(([,v]) => Number(v));
  const allTimed = Object.values(timings).map(Number).filter(x => Number.isFinite(x) && x >= 0);
  const qualityAnswer = normalized(responses.Q50);
  let modifier = 0.82 + 0.18 * (qualityAnswer == null ? 0.5 : qualityAnswer);
  const flags = [];

  const med = median(allTimed);
  const constants = spec.assessment.scoring_constants || {};
  const extreme = constants.timing_extreme_seconds || 1.5;
  const fast = constants.timing_fast_seconds || 2.5;
  if (med != null && med < extreme) {
    modifier *= 0.86;
    flags.push("Responses were exceptionally fast; confidence was modestly reduced.");
  } else if (med != null && med < fast) {
    modifier *= 0.94;
    flags.push("Responses were fast; confidence was slightly reduced.");
  }

  const spread = sd(capabilityAnswers);
  const unique = new Set(capabilityAnswers).size;
  if (capabilityAnswers.length >= 20 && unique === 1) {
    modifier *= 0.78;
    flags.push("Nearly all capability responses were identical; possible straight-lining.");
  } else if (capabilityAnswers.length >= 20 && unique <= 2 && spread != null && spread < 0.45) {
    modifier *= 0.90;
    flags.push("Capability responses showed unusually little differentiation.");
  }

  const required = spec.assessment.core_items.filter(x => x.id !== "Q50").length;
  const answered = spec.assessment.core_items.filter(x => x.id !== "Q50" && responses[x.id] != null).length;
  const completion = required ? answered / required : 0;
  modifier *= 0.82 + 0.18 * completion;
  if (completion < 0.90) flags.push("Several core items were skipped; confidence was reduced.");

  const floor = constants.response_quality_floor || 0.45;
  return {
    modifier: clamp(modifier, floor, 1),
    self_honesty: qualityAnswer,
    median_seconds_per_item: med,
    total_timed_seconds: allTimed.reduce((s,x)=>s+x,0),
    response_sd: spread,
    unique_capability_answers: unique,
    core_completion: completion,
    timing_method: "full interval from question display until Next/Back",
    flags
  };
}

function scoreOrientations(spec, responseData, quality) {
  const responses = responseData.responses || {};
  const items = itemMap(spec);
  const slugs = spec.assessment.orientation_catalog.map(x => x.slug);
  const accum = Object.fromEntries(slugs.map(x => [x, {sum:0, weight:0, answers:[]}])) ;
  for (const [id, answer] of Object.entries(responses)) {
    const item = items[id];
    if (!item || !item.orientation_weights) continue;
    const x = normalized(answer);
    if (x == null) continue;
    for (const [slug,w] of Object.entries(item.orientation_weights)) {
      accum[slug].sum += w*x;
      accum[slug].weight += w;
      accum[slug].answers.push(x);
    }
  }
  const raw = {};
  for (const slug of slugs) raw[slug] = accum[slug].weight ? accum[slug].sum/accum[slug].weight : null;
  const vals = Object.values(raw).filter(x => x != null);
  const minV = vals.length ? Math.min(...vals) : 0;
  const maxV = vals.length ? Math.max(...vals) : 1;
  const range = maxV-minV;
  const relative = {};
  for (const slug of slugs) {
    relative[slug] = raw[slug] == null ? null : (range < 0.0001 ? 0.5 : (raw[slug]-minV)/range);
  }
  const result = {};
  for (const slug of slugs) {
    const answers = accum[slug].answers;
    const answerRange = answers.length > 1 ? Math.max(...answers)-Math.min(...answers) : 0.5;
    const agreement = clamp(1 - 0.55*answerRange, 0.55, 1);
    const coverage = clamp(0.22 + 0.23*answers.length, 0, 0.88);
    result[slug] = {
      score: round(raw[slug]),
      relative_expression: round(relative[slug]),
      answered_items: answers.length,
      agreement: round(agreement),
      confidence: round(clamp(coverage * agreement * quality.modifier))
    };
  }
  return {scores: result, differentiation_range: round(range)};
}

  function scoreLevers(spec, responseData, quality) {
    const responses = responseData.responses || {};
    const items = itemMap(spec);
    const constants = spec.assessment.scoring_constants;
    const catalog = spec.assessment.lever_catalog;
    const accum = Object.fromEntries(catalog.map(x => [x.id, {sum:0, weight:0, weight2:0, values:[], direct:0, answered:0}]));

    for (const [id, answer] of Object.entries(responses)) {
      const item = items[id];
      if (!item || !item.lever_weights) continue;
      const x = normalized(answer);
      if (x == null) continue;
      for (const [leverId,w] of Object.entries(item.lever_weights)) {
        const a = accum[leverId];
        a.sum += w*x;
        a.weight += w;
        a.weight2 += w*w;
        a.values.push({x,w,id});
        a.answered += 1;
        if (item.primary_lever_id === leverId) a.direct += 1;
      }
    }

    const out = {};
    for (const lever of catalog) {
      const a = accum[lever.id];
      if (!a.weight) {
        out[lever.id] = {
          name: lever.name, family: lever.family, estimate:null, raw_self_report:null,
          confidence:0, alpha:constants.prior_alpha, beta:constants.prior_beta,
          effective_item_count:0, direct_item_count:0, status:"unassessed"
        };
        continue;
      }
      const raw = a.sum/a.weight;
      const nEff = (a.weight*a.weight)/a.weight2;
      const variance = a.values.reduce((s,v)=>s+v.w*Math.pow(v.x-raw,2),0)/a.weight;
      const consistency = clamp(1 - Math.sqrt(variance)*0.85, 0.55, 1);
      const mass = Math.min(constants.quiz_mass_cap_per_lever,
                            constants.quiz_mass_per_effective_item*nEff) * quality.modifier * consistency;
      const alpha = constants.prior_alpha + mass*raw;
      const beta = constants.prior_beta + mass*(1-raw);
      const estimate = alpha/(alpha+beta);
      const confidence = clamp((mass/(mass+1.5))*quality.modifier*consistency);
      out[lever.id] = {
        name: lever.name,
        family: lever.family,
        estimate: round(estimate),
        raw_self_report: round(raw),
        confidence: round(confidence),
        alpha: round(alpha,6),
        beta: round(beta,6),
        evidence_mass: round(mass),
        effective_item_count: round(nEff),
        direct_item_count: a.direct,
        inconsistency: round(1-consistency),
        status:"provisional_self_report"
      };
    }
    return out;
  }

function scoreArchetypes(spec, orientationResult) {
  const profile = {};
  for (const [slug,v] of Object.entries(orientationResult.scores)) {
    const absolute = v.score == null ? 0.5 : v.score;
    const relative = v.relative_expression == null ? 0.5 : v.relative_expression;
    profile[slug] = {
      component: 0.68*absolute + 0.32*(0.25 + 0.75*relative),
      confidence: v.confidence || 0
    };
  }
  const rows = spec.assessment.archetypes.map(a => {
    const modes = a.orientation_pair || a.orientation_modes || a.orientations ||
      [a.orientation_1, a.orientation_2].filter(Boolean);
    const slugs = modes.map(x => typeof x === "string" ? x : x.slug);
    const p1 = profile[slugs[0]] || {component:0.5,confidence:0};
    const p2 = profile[slugs[1]] || {component:0.5,confidence:0};
    const harmonic = (2*p1.component*p2.component)/(p1.component+p2.component || 1);
    const pairConfidence = Math.sqrt(p1.confidence*p2.confidence);
    return {
      id:a.id,
      name:a.name,
      orientations:slugs,
      raw_fit:harmonic,
      fit_confidence:pairConfidence,
      contribution:a.characteristic_contribution || a.contribution,
      shadow:a.characteristic_shadow || a.shadow,
      display_note:a.display_note || null
    };
  });
  const total = rows.reduce((s,x)=>s+x.raw_fit,0) || 1;
  rows.forEach(x => x.normalized_fit = x.raw_fit/total);
  rows.sort((a,b)=>b.raw_fit-a.raw_fit);
  return rows.map(x => ({...x, raw_fit:round(x.raw_fit), fit_confidence:round(x.fit_confidence), normalized_fit:round(x.normalized_fit)}));
}

  function scoreFamilies(spec, leverScores) {
    const out = {};
    for (const family of spec.assessment.lever_families) {
      const vals = family.lever_ids.map(id => leverScores[id]).filter(x => x && x.estimate != null);
      const weight = vals.reduce((s,x)=>s+x.confidence,0);
      out[family.id] = {
        name: family.name,
        estimate: weight ? round(vals.reduce((s,x)=>s+x.estimate*x.confidence,0)/weight) : null,
        confidence: vals.length ? round(mean(vals.map(x=>x.confidence))) : 0,
        lever_ids: family.lever_ids
      };
    }
    return out;
  }

  function rankLeverNeeds(spec, leverScores) {
    const p = spec.assessment.scoring_constants.need_exponent;
    return Object.entries(leverScores).map(([id,x]) => {
      if (x.estimate == null) return {lever_id:id, name:x.name, score:null, status:"unassessed"};
      const need = Math.pow(1-x.estimate,p) * (0.60+0.40*x.confidence);
      return {lever_id:id, name:x.name, score:round(need), estimate:x.estimate, confidence:x.confidence};
    }).sort((a,b)=>(b.score ?? -1)-(a.score ?? -1));
  }

  function selectCapabilityClarifiers(spec, leverScores, limit=8) {
    return Object.entries(leverScores).map(([id,x]) => {
      const uncertainty = (1-(x.confidence||0)) + (x.inconsistency||0) + (x.direct_item_count ? 0 : 0.5);
      return {lever_id:id, uncertainty, clarifier_id:`C_${id}`};
    }).sort((a,b)=>b.uncertainty-a.uncertainty).slice(0,limit);
  }

  function selectOrientationClarifiers(spec, orientationResult, limit=2) {
    const rows = Object.entries(orientationResult.scores)
      .map(([slug,x])=>({slug, score:x.score ?? 0.5}))
      .sort((a,b)=>b.score-a.score);
    if (orientationResult.differentiation_range >= 0.18) return [];
    const idBySlug = {discernment:"O_DISC",agency:"O_AGEN",connection:"O_CONN",stewardship:"O_STEW",exploration:"O_EXPL",transcendence:"O_TRAN"};
    return rows.slice(0,limit).map(x=>({orientation:x.slug, clarifier_id:idBySlug[x.slug]}));
  }

  function scoreAssessment(spec, model, responseData) {
    const quality = computeResponseQuality(spec,responseData);
    const orientations = scoreOrientations(spec,responseData,quality);
    if (orientations.differentiation_range < 0.12) quality.flags.push("Orientation scores are relatively flat; archetype differentiation is low.");
    const levers = scoreLevers(spec,responseData,quality);
    const archetypes = scoreArchetypes(spec,orientations);
    const families = scoreFamilies(spec,levers);
    const needs = rankLeverNeeds(spec,levers);
    return {
      assessment_version:spec.assessment.version,
      generated_at:new Date().toISOString(),
      response_quality:quality,
      orientations,
      archetypes,
      levers,
      families,
      lever_need_ranking:needs,
      suggested_capability_clarifiers:selectCapabilityClarifiers(spec,levers,8),
      suggested_orientation_clarifiers:selectOrientationClarifiers(spec,orientations,2),
      interpretation_notice:"These are provisional self-report estimates. They are intended to initialize task selection, not prove mastery or define human worth."
    };
  }

  function createEvidenceState(result) {
    const levers = {};
    for (const [id,x] of Object.entries(result.levers)) {
      levers[id] = {
        alpha:Number(x.alpha),
        beta:Number(x.beta),
        practice_count:0,
        evidence_events:[],
        estimate:x.estimate,
        confidence:x.confidence
      };
    }
    return {version:"1.0", levers};
  }

  function applyTaskEvidence(state, task, event, model, constants) {
    if (!event || event.performance == null) throw new Error("Task completion alone does not update mastery; a rubric-scored performance is required.");
    const performance = clamp(Number(event.performance));
    const quality = clamp(event.evidence_quality == null ? 0.7 : Number(event.evidence_quality));
    const independence = clamp(event.independence == null ? 0.7 : Number(event.independence));
    const breadth = clamp(event.context_breadth == null ? 0.7 : Number(event.context_breadth));
    const repeatIndex = Math.max(0, Number(event.repeat_index || 0));
    const repeatMultipliers = constants.task_repeat_multipliers || [1,0.65,0.4,0.25];
    const repeat = repeatMultipliers[Math.min(repeatIndex,repeatMultipliers.length-1)];

    let weights = task.lever_weights;
    if (!weights && task.parent_competency_id) {
      const link = model.competency_lever_links.find(x=>x.competency_id===task.parent_competency_id);
      if (!link) throw new Error("Unknown parent competency.");
      weights = link.lever_weights;
    }
    if (!weights) throw new Error("Task requires lever_weights or parent_competency_id.");

    const leverMeta = Object.fromEntries(model.developmental_levers.map(x=>[x.id,x]));
    const evidenceYield = task.evidence_yield == null ? 1.0 : Math.max(0,Number(task.evidence_yield));
    const updates = {};
    for (const [leverId,wRaw] of Object.entries(weights)) {
      const w = Number(wRaw);
      const denom = leverMeta[leverId]?.coverage?.total_weight || 1;
      const normalizedShare = (w*evidenceYield)/denom;
      let mass = constants.task_mass_budget_per_lever*normalizedShare;
      mass = Math.min(constants.task_event_mass_cap_per_lever,mass);
      mass *= quality*independence*breadth*repeat;
      const slot = state.levers[leverId];
      if (!slot) continue;
      slot.alpha += mass*performance;
      slot.beta += mass*(1-performance);
      slot.practice_count += 1;
      slot.estimate = slot.alpha/(slot.alpha+slot.beta);
      slot.confidence = clamp((slot.alpha+slot.beta-0.7)/(slot.alpha+slot.beta+1.5));
      const record = {task_id:task.task_id || task.parent_competency_id || "unknown", mass, performance, quality, independence, breadth, repeat_index:repeatIndex};
      slot.evidence_events.push(record);
      updates[leverId] = {mass:round(mass), estimate:round(slot.estimate), confidence:round(slot.confidence)};
    }
    return updates;
  }

  function rankCompetencies(model, result, limit=20) {
    const needs = Object.fromEntries(result.lever_need_ranking.filter(x=>x.score!=null).map(x=>[x.lever_id,x.score]));
    return model.competency_lever_links.map(c => {
      const score = Object.entries(c.lever_weights).reduce((s,[id,w])=>s+(needs[id]||0)*Number(w),0);
      return {competency_id:c.competency_id, competency_name:c.competency_name, domain_name:c.domain_name, priority:round(score), lever_weights:c.lever_weights};
    }).sort((a,b)=>b.priority-a.priority).slice(0,limit);
  }

  function encodeShareCode(spec, responseData) {
    const coreOrder = spec.assessment.core_items.map(x=>x.id);
    const core = coreOrder.map(id => {
      const v = responseData.responses?.[id];
      return v === "NA" ? "N" : (v == null ? "0" : String(v));
    }).join("");
    const extras = Object.fromEntries(Object.entries(responseData.responses||{}).filter(([id])=>!coreOrder.includes(id)));
    const payload = {v:spec.assessment.version,r:core,e:extras,t:responseData.total_seconds||null};
    const txt = JSON.stringify(payload);
    if (typeof btoa === "function") return "GGA11."+btoa(unescape(encodeURIComponent(txt)));
    return "GGA11."+Buffer.from(txt,"utf8").toString("base64");
  }

  function decodeShareCode(spec, code) {
    const body = code.replace(/^GGA(?:11|1)\./,"");
    let txt;
    if (typeof atob === "function") txt = decodeURIComponent(escape(atob(body)));
    else txt = Buffer.from(body,"base64").toString("utf8");
    const payload = JSON.parse(txt);
    const coreOrder = spec.assessment.core_items.map(x=>x.id);
    const responses = {};
    [...payload.r].forEach((ch,i) => {
      if (!coreOrder[i] || ch==="0") return;
      responses[coreOrder[i]] = ch==="N" ? "NA" : Number(ch);
    });
    Object.assign(responses,payload.e||{});
    return {responses,total_seconds:payload.t||null};
  }

  return {
    scoreAssessment,
    computeResponseQuality,
    selectCapabilityClarifiers,
    selectOrientationClarifiers,
    createEvidenceState,
    applyTaskEvidence,
    rankCompetencies,
    encodeShareCode,
    decodeShareCode
  };
});
