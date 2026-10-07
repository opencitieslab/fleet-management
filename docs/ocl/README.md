# Open Cities Lab fork notes

Working notes for running the OpenRemote fleet-management custom project for Open Cities Lab (OCL).
Written 2026-09-14 against branch `feat/ocl-local-dev` (based on OpenRemote 1.15.1) with upstream `main` at OpenRemote 1.30.0.

| Document | What it covers |
|---|---|
| [branch-review.md](branch-review.md) | What the `feat/ocl-local-dev` branch changes, what to keep, what to drop, and inherited problems to fix in the same pass |
| [hosting-options-and-costs.md](hosting-options-and-costs.md) | Heroku vs OpenRemote's own CloudFormation vs the CivicView CDK patterns, with monthly cost estimates and the step-by-step AWS deploy |
| [seeding-data.md](seeding-data.md) | The three seeding mechanisms, why `seed_database.py` is not repeatable, and the recommended split |
| [theming.md](theming.md) | Branding the Manager UI, Keycloak login and map to the opencitieslab.org palette |

## Short version

- **Do not use Heroku.** No raw TCP for MQTT on 8883, no persistent disk, and Heroku Postgres has no TimescaleDB. Roughly $550/month for something that still cannot receive tracker data.
- **Deploy on one ARM EC2 in af-south-1 with OpenRemote's own CloudFormation template.** About $46/month on a `t4g.medium`, about $78/month on a `t4g.large`. The repo's GitHub Actions workflow already calls the upstream deploy pipeline.
- **Port to the CivicView CDK only if fleet becomes a product line.** It needs an NLB, path-based routing for Keycloak under `/auth`, and a self-run Postgres because RDS has no TimescaleDB. Roughly three times the cost.
- **Rebase the branch onto upstream `main` first.** It is 1.15.1 versus 1.30.0, and upstream rewrote the Keycloak block the branch edits.
- **Seed assets through the provisioning folder, history through a one-off SQL run, and later through an MQTT replay simulator.** The current script adds 40 duplicate trucks every time it runs.
- **Theme via `deployment/manager/app/manager_config.json`.** Primary `#D66139`, text `#2F3542`, background `#F8F8F8`, straight from the site's Elementor palette.

## Open decisions

- Which hostname fleet lives under (`fleet.opencitieslab.org`, something under `civicview.co.za`, or a client domain). This decides where the Route53 zone goes and who owns Let's Encrypt renewal.
- Whether the AGPL-3.0 obligation to publish modified source is acceptable for the client. The fork is public today, which satisfies it.
