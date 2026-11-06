# Hackathon brief

Condensed from the organizer PDFs (theme briefs and kickoff deck) for the UCLA Anderson MSBA Vibathon 2026.

## Event

- Fri Nov 6 2026, in person, Anderson B301. Judges review from 6:00 to 8:00 PM. Only people in the room can win.
- Hand in: **a working prototype** (runs live, start to finish, on real or realistic data) and **a short document** that explains it and matches the demo.
- Three winning teams present at the UCLA Anderson Data & AI Meetup with DAMA Los Angeles on Wed Nov 18.

## Judging (each 1 to 5, weighted, out of 100)

| Criterion | Weight |
|---|---|
| Problem and user | 15% |
| Business value | 20% |
| Working prototype | 15% |
| Data and analysis | 10% |
| Originality | 10% |
| Smart use of AI | 10% |
| Feasibility and risks | 10% |
| Pitch and document | 10% |

Ties go to the team whose prototype ran live, then to the higher business value score. So the live demo must not break, and a focused problem beats a broad platform.

## Theme 04: Uninsurable

Brief: help California homeowners, insurers, lenders or cities deal with home insurance that is disappearing.

Facts from the brief, usable in the pitch:

- State Farm and Allstate are still closed to new customers in California.
- Dropped homeowners end up on the FAIR Plan, which covers fire only and raised its rates 29.1% on October 15.
- About 41% of homes in the highest-risk ZIP codes are on the FAIR Plan.
- Premiums are up 84% statewide since 2020; FAIR Plan exposure reached $750 billion, more than three times the 2022 level.
- The state rewards specific fire-safety work, "but homeowners have no easy way to find out which work would get them back into the private market." This is the gap we address.

## Our problem

User: a California (LA County) homeowner dropped by their insurer and now on the FAIR Plan.

> Homeowners pushed onto the FAIR Plan pay more for less coverage and want private insurance back. The state rewards specific fire-safety upgrades, but nobody tells them which fixes matter most for their home, what each costs, and what it would save. So they spend on the wrong upgrades or do nothing.

## Core demo flow

1. **Address in.** Geocode it; show the fire hazard zone, nearby fire history, the ZIP's FAIR Plan share and non-renewal trend.
2. **Checklist.** Which Safer from Wildfires measures (`data/processed/measures.csv`) does the home already meet? Optional AI step pre-fills it from an aerial image or home photo; the user confirms each answer.
3. **Ranked fixes out.** Each missing measure with its cost range, what it unlocks (discount or eligibility), and why it ranks where it does.

Steps 1 and 3 are plain code and data. If the AI step fails live, the checklist still carries the demo.

## Known data limits (say them in the doc)

- No public price per fix and no public premium per home: costs and savings are labelled assumptions.
- CDI insurance data ends in 2023 and FAIR Plan share by ZIP is 2022 only, both before the January 2025 fires.
- Aerial imagery shows vegetation near the roof, not vents or gutters: a first screen, not an inspection.
