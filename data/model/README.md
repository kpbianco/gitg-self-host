# Grounded Growth Lever and Archetype Model v1

## What this model does

The refined curriculum contains **27 broad domains** and **383 master competencies**. Those levels are useful for content, but neither is the ideal scoring layer:

- the domains are too broad to rank specific developmental work cleanly;
- the competencies are too granular to function as stable human-development dimensions;
- personality types describe preferred style, not demonstrated mastery.

This model inserts a middle layer of **37 developmental levers**, organized into **7 families**. Every master competency has a weighted mapping to one or more levers, and every mapping sums to `1.0`.

The model also replaces forced personality boxes with six continuous orientation modes:

`discernment`, `agency`, `connection`, `stewardship`, `exploration`, and `transcendence`.

The **15 archetypes** are the complete set of two-mode combinations (`6 choose 2 = 15`). A person may express several archetypes. Archetype fit is used for explanation, engagement, language, and a tightly capped task-order adjustment. It is not mastery and is not moral rank.

## Non-negotiable separation

| Layer | Question answered | Score |
|---|---|---|
| Orientation | How does this person tend to engage? | six 0–1 preferences |
| Archetype | Which two-mode patterns best summarize that style? | normalized mixture |
| Mastery lever | What developmental capacities are demonstrated? | 0–1 plus confidence |
| Context | What matters and is feasible now? | applicability, importance, readiness, urgency, opportunity |
| Task | What should be practiced next? | weighted priority |

Do not infer mastery from archetype. Do not infer worth from mastery. Do not treat missing evidence as zero.

## Mastery scale

- `null`: unassessed or insufficient evidence
- `0.0`: assessed, no demonstrated mastery
- `0.2`: awareness
- `0.4`: conceptual understanding or guided practice
- `0.6`: repeated practice with inconsistent transfer
- `0.8`: reliable independent application in ordinary contexts
- `1.0`: integrated under stress, adaptable across contexts, and able to support or teach others

## Scoring

For competency `q`, lever `l`, and user applicability `a_q`:

```text
M_l = sum(a_q * w_ql * m_q) / sum(a_q * w_ql)
```

Where `w_ql` is the mapping weight and `m_q` is evidence-based competency mastery.

Track **coverage confidence** separately. Task completion records exposure, practice, or evidence; it does not automatically raise `m_q`.

A practical developmental-need score is:

```text
N_l = applicability_l
    * importance_l
    * readiness_l
    * urgency_l
    * confidence_l
    * (1 - M_l)^1.5
```

For task `t`:

```text
P_t = sum(w_tl * N_l)
```

Personality style may change presentation or break ties:

```text
F_t = sum(w_tl * dot(user_orientation, lever_orientation_composition_l))
P_final_t = P_t * (0.95 + 0.10 * F_t)
```

This caps personality influence at roughly ±5%, so actual developmental need remains dominant.

## Developmental levers

### Orientation and Moral Center

- **L01 — Purpose and Direction**: Clarifies what is worth pursuing, why it matters, and how present commitments express a coherent direction.
- **L02 — Values, Integrity, and Moral Courage**: Translates ethical commitments into truthful, reliable, fair, and courageous conduct across contexts.
- **L03 — Spirituality, Reverence, and Transcendence**: Develops relationship to the sacred, ultimate concern, ritual, contemplation, vocation, and realities larger than the isolated self.
- **L04 — Mortality, Suffering, Gratitude, and Hope**: Builds the capacity to face impermanence, tragedy, loss, limitation, received life, and hope without denial.

### Inner Governance

- **L05 — Self-Knowledge, Identity, and Humility**: Improves accurate self-understanding, identity coherence, awareness of limitations and defenses, and proportionate self-regard.
- **L06 — Emotional Awareness and Literacy**: Recognizes, differentiates, names, and communicates emotions and their bodily and situational signals.
- **L07 — Emotional Regulation and Resilience**: Regulates emotion without suppression, recovers from setbacks, seeks help appropriately, and generalizes coping skills under stress.
- **L08 — Attention and Presence**: Directs attention deliberately, sustains contact with the present, and notices distraction, interpretation, and automaticity.
- **L09 — Temperance and Desire Governance**: Uses pleasure, consumption, craving, status, comfort, and impulse without being ruled by them.
- **L10 — Discipline, Habits, and Follow-Through**: Converts intentions into consistent action through habits, planning, accountability, perseverance, and completion.
- **L11 — Adaptability, Uncertainty, and Learning from Failure**: Acts under uncertainty, revises plans, tolerates change, and converts setbacks or disconfirmation into improved behavior.

### Thought, Learning, and Imagination

- **L12 — Critical Reasoning and Logic**: Analyzes claims, arguments, assumptions, contradictions, and alternatives with disciplined reasoning.
- **L13 — Evidence, Truth, and Epistemic Humility**: Evaluates sources and evidence, tracks uncertainty, updates beliefs, and resists bias, misinformation, and overconfidence.
- **L14 — Systems Thinking, Judgment, and Decision-Making**: Understands causality, tradeoffs, risk, feedback, context, and second-order effects to make and revise sound decisions.
- **L15 — Learning Agility, Memory, and Teaching**: Acquires, organizes, practices, retains, transfers, explains, and transmits knowledge and skill.
- **L16 — Creativity, Aesthetics, and Cultural Literacy**: Creates, interprets, refines, and shares meaningful work while developing imagination, taste, cultural context, and attribution ethics.

### Embodied and Practical Agency

- **L17 — Physical Health, Vitality, and Embodiment**: Maintains health, movement capacity, recovery, body literacy, bodily autonomy, and sustainable physical functioning.
- **L18 — Domestic Competence and Material Self-Sufficiency**: Operates and maintains a safe, functional home and everyday material life through practical skills and systems.
- **L19 — Digital Agency, Media Literacy, and Security**: Uses digital tools and AI competently while governing attention, verifying information, protecting identity and data, and participating responsibly online.
- **L20 — Safety, Risk, and Preparedness**: Anticipates hazards, prevents avoidable harm, responds to emergencies, and builds personal and communal resilience.
- **L21 — Financial Stewardship and Provision**: Manages cash flow, debt, saving, investing, protection, consumption, generosity, and material obligations responsibly.
- **L22 — Economic Agency, Entrepreneurship, and Market Literacy**: Understands economic systems and creates, prices, negotiates, operates, and governs value-producing activity responsibly.

### Relationship and Care

- **L23 — Communication and Listening**: Listens attentively and expresses ideas, needs, feedback, stories, and arguments clearly across audiences and contexts.
- **L24 — Empathy, Social Perception, and Perspective-Taking**: Accurately perceives others' experiences, motives, emotions, needs, contexts, and viewpoints without erasing difference.
- **L25 — Boundaries, Assertiveness, and Self-Respect**: States needs and limits, protects autonomy and dignity, resists coercion, and says no or exits responsibly.
- **L26 — Friendship, Belonging, and Hospitality**: Initiates, selects, maintains, and contributes to reciprocal friendships, networks, communities, and inclusive belonging.
- **L27 — Intimacy, Sexuality, and Partnership**: Builds consensual, secure, communicative, mutually responsible intimate relationships across changing stages and forms.
- **L28 — Family, Parenting, and Caregiving**: Participates responsibly in family systems, parenting, reproduction, elder care, disability care, safeguarding, and shared household care.
- **L29 — Conflict, Repair, Forgiveness, and Reconciliation**: Navigates disagreement, de-escalates harm, apologizes, repairs trust, forgives wisely, and supports reconciliation where possible.

### Contribution, Society, and Power

- **L30 — Service, Citizenship, and Civic Agency**: Contributes to community needs, understands civic channels, organizes responsibly, and builds collective capacity.
- **L31 — Justice, Pluralism, and Social Responsibility**: Understands rights, inequality, institutions, power, difference, and shared risk while preserving dignity and peaceful coexistence.
- **L32 — Work, Craft, Professionalism, and Contribution**: Builds reliable, adaptive, ethical competence and delivers useful, high-quality work with appropriate boundaries.
- **L33 — Leadership, Power, Mentorship, and Institutions**: Sets direction, uses power ethically, develops others, designs accountable institutions, and responds to conflict, crisis, corruption, and abuse.

### Integration and Flourishing

- **L34 — Play, Rest, Celebration, and Joy**: Cultivates non-instrumental play, restoration, delight, humor, festivity, and sustainable freedom from constant optimization.
- **L35 — Nature, Exploration, and Adventure**: Builds curiosity, place-awareness, ecological relationship, travel competence, outdoor capability, wonder, and calculated challenge.
- **L36 — Life Design, Balance, and Seasonality**: Integrates competing goods, roles, capacities, seasons, transitions, reviews, ambition, contentment, and multiple legitimate pathways.
- **L37 — Legacy, Generativity, and Transmission**: Invests in people, institutions, traditions, knowledge, works, and provisions that outlast the self without confusing legacy with status.


## Archetypes

### A01 — The Strategist (discernment + agency)

**Core drive:** Turn clear understanding into deliberate, effective action.

**Typical contribution:** Creates direction, chooses priorities, and converts ambiguity into an executable path.

**Shadow:** Can over-control, treat people as variables, or mistake decisiveness for wisdom.

**Strongest affinities:** Critical Reasoning and Logic, Evidence, Truth, and Epistemic Humility, Discipline, Habits, and Follow-Through, Systems Thinking, Judgment, and Decision-Making.

**Balancing development:** Empathy, Social Perception, and Perspective-Taking, Friendship, Belonging, and Hospitality, Play, Rest, Celebration, and Joy, Spirituality, Reverence, and Transcendence.

### A02 — The Counselor (discernment + connection)

**Core drive:** Understand people and situations deeply enough to help them move toward clarity and repair.

**Typical contribution:** Helps others name what is happening, understand competing perspectives, and make humane choices.

**Shadow:** Can over-analyze, absorb others' emotions, become indirect, or substitute insight for action.

**Strongest affinities:** Emotional Awareness and Literacy, Empathy, Social Perception, and Perspective-Taking, Critical Reasoning and Logic, Evidence, Truth, and Epistemic Humility.

**Balancing development:** Boundaries, Assertiveness, and Self-Respect, Discipline, Habits, and Follow-Through, Systems Thinking, Judgment, and Decision-Making, Work, Craft, Professionalism, and Contribution.

### A03 — The Architect (discernment + stewardship)

**Core drive:** Build coherent systems that remain reliable over time.

**Typical contribution:** Designs durable processes, institutions, plans, and safeguards that others can trust.

**Shadow:** Can become rigid, perfectionistic, detached from lived experience, or loyal to systems after they stop serving people.

**Strongest affinities:** Evidence, Truth, and Epistemic Humility, Critical Reasoning and Logic, Financial Stewardship and Provision, Systems Thinking, Judgment, and Decision-Making.

**Balancing development:** Emotional Awareness and Literacy, Adaptability, Uncertainty, and Learning from Failure, Creativity, Aesthetics, and Cultural Literacy, Play, Rest, Celebration, and Joy.

### A04 — The Explorer (discernment + exploration)

**Core drive:** Discover new ideas, patterns, possibilities, and ways of seeing.

**Typical contribution:** Expands the map, questions stale assumptions, and connects knowledge across boundaries.

**Shadow:** Can chase novelty, avoid commitment, intellectualize life, or leave promising work unfinished.

**Strongest affinities:** Critical Reasoning and Logic, Evidence, Truth, and Epistemic Humility, Learning Agility, Memory, and Teaching, Creativity, Aesthetics, and Cultural Literacy.

**Balancing development:** Discipline, Habits, and Follow-Through, Domestic Competence and Material Self-Sufficiency, Financial Stewardship and Provision, Friendship, Belonging, and Hospitality.

### A05 — The Seeker (discernment + transcendence)

**Core drive:** Find truth, meaning, wisdom, and a life worthy of commitment.

**Typical contribution:** Provides moral and existential orientation, challenges superficial goals, and preserves depth.

**Shadow:** Can retreat into abstraction, spiritualize avoidable problems, or wait for certainty before living.

**Strongest affinities:** Spirituality, Reverence, and Transcendence, Purpose and Direction, Evidence, Truth, and Epistemic Humility, Mortality, Suffering, Gratitude, and Hope.

**Balancing development:** Discipline, Habits, and Follow-Through, Physical Health, Vitality, and Embodiment, Domestic Competence and Material Self-Sufficiency, Communication and Listening.

### A06 — The Catalyst (agency + connection)

**Core drive:** Mobilize people toward growth, action, and shared possibility.

**Typical contribution:** Creates momentum, raises confidence, and helps groups cross the gap between intention and action.

**Shadow:** Can rush consent, overpromise, rescue others, or confuse intensity and popularity with progress.

**Strongest affinities:** Intimacy, Sexuality, and Partnership, Emotional Regulation and Resilience, Empathy, Social Perception, and Perspective-Taking, Boundaries, Assertiveness, and Self-Respect.

**Balancing development:** Evidence, Truth, and Epistemic Humility, Safety, Risk, and Preparedness, Boundaries, Assertiveness, and Self-Respect, Leadership, Power, Mentorship, and Institutions.

### A07 — The Builder (agency + stewardship)

**Core drive:** Turn responsibility into concrete capability, provision, and finished results.

**Typical contribution:** Makes plans real, creates stability, solves material problems, and completes difficult work.

**Shadow:** Can overwork, dominate, suppress emotion, or equate human worth with usefulness and output.

**Strongest affinities:** Discipline, Habits, and Follow-Through, Domestic Competence and Material Self-Sufficiency, Safety, Risk, and Preparedness, Temperance and Desire Governance.

**Balancing development:** Emotional Awareness and Literacy, Intimacy, Sexuality, and Partnership, Play, Rest, Celebration, and Joy, Self-Knowledge, Identity, and Humility.

### A08 — The Trailblazer (agency + exploration)

**Core drive:** Open new paths through experimentation, courage, and rapid learning.

**Typical contribution:** Breaks inertia, tests possibilities, creates opportunities, and normalizes intelligent risk.

**Shadow:** Can become impulsive, scattered, bored by maintenance, or leave others carrying the consequences.

**Strongest affinities:** Nature, Exploration, and Adventure, Adaptability, Uncertainty, and Learning from Failure, Physical Health, Vitality, and Embodiment, Creativity, Aesthetics, and Cultural Literacy.

**Balancing development:** Discipline, Habits, and Follow-Through, Safety, Risk, and Preparedness, Financial Stewardship and Provision, Values, Integrity, and Moral Courage.

### A09 — The Reformer (agency + transcendence)

**Core drive:** Act on conviction to align people and institutions with a higher standard.

**Typical contribution:** Names moral failures, organizes meaningful change, and protects ideals from becoming empty language.

**Shadow:** Can become self-righteous, absolutist, punitive, chronically dissatisfied, or consumed by the cause.

**Strongest affinities:** Spirituality, Reverence, and Transcendence, Mortality, Suffering, Gratitude, and Hope, Purpose and Direction, Temperance and Desire Governance.

**Balancing development:** Justice, Pluralism, and Social Responsibility, Self-Knowledge, Identity, and Humility, Conflict, Repair, Forgiveness, and Reconciliation, Play, Rest, Celebration, and Joy.

### A10 — The Guardian (connection + stewardship)

**Core drive:** Protect people, relationships, and the conditions that let them thrive.

**Typical contribution:** Creates safety, continuity, belonging, and dependable care in families and communities.

**Shadow:** Can overfunction, become paternalistic, avoid necessary disruption, or neglect personal needs.

**Strongest affinities:** Friendship, Belonging, and Hospitality, Family, Parenting, and Caregiving, Intimacy, Sexuality, and Partnership, Financial Stewardship and Provision.

**Balancing development:** Boundaries, Assertiveness, and Self-Respect, Purpose and Direction, Adaptability, Uncertainty, and Learning from Failure, Nature, Exploration, and Adventure.

### A11 — The Connector (connection + exploration)

**Core drive:** Create belonging and possibility by linking people, cultures, and experiences.

**Typical contribution:** Builds networks, translates across groups, creates hospitality, and makes life feel larger.

**Shadow:** Can seek approval, diffuse attention, avoid depth, or mistake activity and contact for intimacy.

**Strongest affinities:** Empathy, Social Perception, and Perspective-Taking, Friendship, Belonging, and Hospitality, Creativity, Aesthetics, and Cultural Literacy, Intimacy, Sexuality, and Partnership.

**Balancing development:** Attention and Presence, Evidence, Truth, and Epistemic Humility, Boundaries, Assertiveness, and Self-Respect, Discipline, Habits, and Follow-Through.

### A12 — The Healer (connection + transcendence)

**Core drive:** Relieve suffering and restore dignity, trust, wholeness, and hope.

**Typical contribution:** Supports repair, accompanies people through loss, and keeps mercy connected to human dignity.

**Shadow:** Can become a martyr, blur boundaries, excuse harm, or make being needed central to identity.

**Strongest affinities:** Spirituality, Reverence, and Transcendence, Mortality, Suffering, Gratitude, and Hope, Empathy, Social Perception, and Perspective-Taking, Friendship, Belonging, and Hospitality.

**Balancing development:** Boundaries, Assertiveness, and Self-Respect, Justice, Pluralism, and Social Responsibility, Values, Integrity, and Moral Courage, Financial Stewardship and Provision.

### A13 — The Craftsman (stewardship + exploration)

**Core drive:** Improve reality through disciplined skill, experimentation, and care for quality.

**Typical contribution:** Produces useful and beautiful work, preserves tacit knowledge, and raises the quality of practice.

**Shadow:** Can become perfectionistic, narrow, isolated, or more comfortable with objects and systems than people.

**Strongest affinities:** Creativity, Aesthetics, and Cultural Literacy, Financial Stewardship and Provision, Nature, Exploration, and Adventure, Safety, Risk, and Preparedness.

**Balancing development:** Purpose and Direction, Communication and Listening, Friendship, Belonging, and Hospitality, Service, Citizenship, and Civic Agency.

### A14 — The Steward (stewardship + transcendence)

**Core drive:** Preserve and transmit what is valuable across people, institutions, resources, and generations.

**Typical contribution:** Maintains continuity, protects shared goods, mentors successors, and prevents short-term appetite from consuming the future.

**Shadow:** Can become burdened, conservative by reflex, controlling, or loyal to inherited forms that need reform.

**Strongest affinities:** Spirituality, Reverence, and Transcendence, Purpose and Direction, Values, Integrity, and Moral Courage, Legacy, Generativity, and Transmission.

**Balancing development:** Creativity, Aesthetics, and Cultural Literacy, Adaptability, Uncertainty, and Learning from Failure, Play, Rest, Celebration, and Joy, Mortality, Suffering, Gratitude, and Hope.

### A15 — The Creator (exploration + transcendence)

**Core drive:** Express meaning and reveal possibility through imagination, beauty, and original form.

**Typical contribution:** Gives shape to what others cannot yet articulate and renews culture through art, story, design, and imagination.

**Shadow:** Can romanticize chaos, resist structure, confuse expression with contribution, or abandon work before refinement.

**Strongest affinities:** Spirituality, Reverence, and Transcendence, Creativity, Aesthetics, and Cultural Literacy, Nature, Exploration, and Adventure, Purpose and Direction.

**Balancing development:** Discipline, Habits, and Follow-Through, Critical Reasoning and Logic, Financial Stewardship and Provision, Work, Craft, Professionalism, and Contribution.


## Mapping policy for concrete tasks

The 383 items in the refined YAML are master competencies rather than atomic exercises. Each future concrete task should:

1. inherit its parent competency's lever weights by default;
2. override the mapping only when the exercise clearly trains a narrower subset;
3. keep weights normalized to `1.0`;
4. specify evidence yield, difficulty, effort, applicability, and safety/professional boundaries;
5. log evidence rather than granting mastery merely for completion.

Example:

```yaml
task:
  id: task_example
  parent_competency_id: "16.01"
  name: Conduct a 20-minute listening conversation
  lever_weights:
    L23: 0.65
    L24: 0.35
  evidence_yield: 0.55
  evidence_types:
    - real_world_application
    - external_observer_feedback
```

## File guide

- `grounded_growth_model_v1.yaml`: canonical human-readable object containing levers, orientations, archetypes, formulas, and all 383 competency mappings.
- `grounded_growth_model_v1.json`: language-neutral machine-readable object.
- `grounded_growth_model_v1.js`: directly importable JavaScript object.
- `ideal_person_curriculum_v3_lever_mapped.yaml`: the full refined curriculum with mappings embedded under each competency.
- `competency_lever_mapping_v1.csv`: flat audit/import table for all 383 competencies.
- `archetype_lever_affinity_v1.csv`: all 15 × 37 archetype-to-lever affinity links.
- `developmental_lever_catalog_v1.csv`: lever definitions, orientation composition, coverage counts, and strongest archetype associations.
- `mapping_qa_report_v1.csv`: mapping completeness and normalization checks.

## Validation status

This is a coherent content and ranking architecture, not a psychometrically validated personality or mastery instrument. Before making strong claims, validate the orientation questions, evidence rubrics, lever reliability, fairness across groups, and whether task recommendations actually improve targeted outcomes.
