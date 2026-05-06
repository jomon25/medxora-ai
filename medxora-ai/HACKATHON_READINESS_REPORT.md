# MedXora AI Hackathon Readiness Report

Date: May 7, 2026
Target event: Google Cloud Rapid Agent Hackathon

## Official Submission Requirements

Based on the current Devpost event page, the submission needs:

- A functional agent
- Built with Gemini 3
- Built using Google Cloud Agent Builder
- Meaningful integration with a partner MCP server
- A hosted project URL
- A public source repository URL
- A visible open source license
- A demo video of about 3 minutes
- A selected partner track
- A completed Devpost submission

Judging criteria:

- Technological Implementation
- Design
- Potential Impact
- Quality of the Idea

Important dates currently shown:

- Submission deadline: June 11, 2026 at 2:00 PM PDT
- Judging window: June 22, 2026 to July 6, 2026

## Best Track Recommendation

Recommended track: MongoDB

Why:

- The codebase already includes MongoDB-backed MCP-style memory with SQLite fallback
- The story is easier to explain than trying to pivot to a different partner late
- The app already has a memory/search/mission angle that maps well to an agent competition

## Current Strengths

- Strong product scope
- Real multi-page dashboard
- Mission-style workflow
- Strategy generation, backtesting, evolution, and comparison
- Gemini-backed planning and reasoning flow
- MongoDB memory support already exists
- Logs and integration settings already exist

## Biggest Current Gaps

- Google Cloud Agent Builder is not yet clearly implemented or demonstrated in the repo
- Gemini is present, but not framed as Gemini 3 + Agent Builder in the submission story
- The current product still reads more like a trading platform than a focused hackathon agent
- No hosted production submission path is documented and proven yet
- No demo video exists yet
- No automated test suite exists yet
- The app needs a clearer single flagship workflow for judges

## What Has Already Been Done In This Repo

- Fixed the Evolution flow to use a long-running frontend API request
- Improved retention of before/after comparison data after evolution
- Preserved evaluated evolved metrics when the saved child strategy record is sparse
- Fixed current frontend lint issues
- Verified frontend build passes
- Verified backend import and compile checks pass
- Updated the README with current architecture, setup, known limitations, and remaining work

## Step-by-Step Plan To Improve Winning Chances

### Phase 1: Pick The Exact Submission Story

Goal:
Turn MedXora AI from "many features" into one clear judged story.

What you should submit:

- "An agent that researches, evolves, validates, and remembers trading strategies using Gemini and MongoDB memory under human oversight."

Do not pitch it as:

- a generic trading dashboard
- a broad AI lab
- a collection of unrelated screens

Output of this phase:

- one sentence pitch
- one paragraph problem statement
- one partner-track choice
- one judge demo flow

### Phase 2: Make The Agent Builder Story Real

Goal:
Close the largest compliance gap with the event brief.

You need to add or clearly demonstrate:

- Google Cloud Agent Builder usage
- Vertex AI or related Google Cloud agent infrastructure
- Hosted execution path

Minimum acceptable submission framing:

- Agent Builder handles orchestration, grounding, or agent-facing workflow
- Your custom backend powers domain-specific tools
- MongoDB MCP provides memory/search superpowers

If you skip this:

- the project may look off-brief even if the app itself is impressive

### Phase 3: Make MongoDB Track The Centerpiece

Goal:
Win inside one partner bucket, not across the whole field.

What the demo must show:

- the agent stores strategy memory
- the agent retrieves past similar strategies
- the agent uses that memory to improve or explain future decisions

Judges need to clearly see:

- MongoDB is not decorative
- memory changes the agent's behavior
- the partner integration gives a real advantage

### Phase 4: Reduce The Demo To One Winning Workflow

Recommended judge flow:

1. User gives one goal
2. Mission Control plans the job
3. Strategy gets generated and evaluated
4. Evolution improves or compares variants
5. MongoDB memory is queried and influences the next step
6. Final champion and explanation are shown

Keep the live demo around one story:

- "Create a low-risk EURUSD strategy, evaluate it, evolve it, compare it, search prior memory, and produce a final recommendation."

### Phase 5: Improve Design For Judges

Goal:
Maximize the Design score quickly.

You should do:

- remove confusing pages from the demo path
- make the main flow obvious in 1 click
- ensure loading states are clean
- ensure every major panel explains what it is doing
- highlight before/after strategy comparison visually

What matters:

- judges understand the story in under 30 seconds
- no broken states
- no unexplained technical UI

### Phase 6: Improve Impact Framing

Goal:
Raise the Potential Impact score.

Right now the project sounds like:

- "AI for trading strategy research"

You should reframe it as:

- "an agentic decision-support system for supervised financial strategy research"
- "a human-in-the-loop research agent that reduces manual analysis time"
- "a memory-backed agent for repeatable, auditable evaluation workflows"

You need to explain:

- who benefits
- what time or risk it saves
- why human oversight matters

### Phase 7: Make The Submission Operational

You must have:

- public GitHub repo
- visible MIT license
- hosted app URL
- demo video
- Devpost submission copy
- architecture diagram
- screenshots

Without these, even a strong project can underperform badly.

## What You Need To Do Yourself

These are the parts that likely need your manual ownership:

- choose the final submission story
- create or connect the Google Cloud Agent Builder layer
- deploy the hosted submission version
- record the demo video
- submit on Devpost
- decide which screens stay in the live demo

## What Codex Can Help You Do Next

I can help you with these immediately:

- rewrite the app and README to match a MongoDB-track submission story
- create a hackathon submission page inside the app
- simplify the demo path to one flagship flow
- add a dedicated architecture diagram section
- create a submission checklist file
- create a demo script and spoken narration
- help prepare Devpost answers
- help refactor the UI to feel more polished for judges

## Suggested Priority Order

1. Lock the partner track: MongoDB
2. Lock the one-sentence pitch
3. Add or demonstrate Agent Builder / Vertex usage
4. Make one clean judge demo flow
5. Deploy a hosted version
6. Record the demo video
7. Polish submission copy and screenshots

## Honest Readiness Score

Current hackathon readiness:

- Product strength: 7.5/10
- Submission-fit strength: 4.5/10
- Judge-demo clarity: 5/10
- Technical depth: 8/10
- Compliance with event framing: incomplete

Overall current readiness:

- 5.5/10

If the Agent Builder story, MongoDB track framing, hosting, and demo are completed well:

- possible readiness target: 8/10
