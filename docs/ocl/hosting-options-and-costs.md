# Hosting options and costs

Assessed 2026-09-14. Prices are AWS on-demand for **af-south-1 (Cape Town)**, 730 hours a month, USD, ex VAT. ZAR figures use 16.6 ZAR/USD. Ireland is 10 to 20 percent cheaper but adds latency for Durban trackers and puts data outside South Africa.

## What the stack needs

Four containers from `docker-compose.yml`:

| Container | Image | Needs |
|---|---|---|
| manager | `openremote/manager:1.30.0` | Java 21, about 2 GB RAM (JVM takes 75% of the container by default), `/storage` and `/deployment` volumes |
| keycloak | `openremote/keycloak` | About 1 GB RAM, must be served from the **same hostname** under `/auth` |
| postgresql | `openremote/postgresql` | Postgres with **TimescaleDB** and PostGIS. The manager refuses to start without TimescaleDB 2.21 or later. 512 MB to 1 GB RAM |
| proxy | `openremote/proxy` | HAProxy with Let's Encrypt. Ports 80, 443 and **8883 (MQTT over TLS)** |

OpenRemote staff run small deployments on 2 GB and recommend 4 GB or more for real use. The 40-vehicle demo dataset plus a rules engine wants the larger figure.

## Options compared

| Option | Verdict | USD/month | Why |
|---|---|---|---|
| **Heroku** | Not viable | 550+ | Web dynos accept HTTP on one `$PORT` only, so no MQTTS. Filesystem is discarded on every restart, so `/storage` (uploaded logos, saved config, tiles) is lost daily. Heroku Postgres has PostGIS but **no TimescaleDB**. Keycloak on the same host under `/auth` means bundling manager, Keycloak and a proxy into one container. The closest workaround is two Performance-M dynos ($500) plus a third-party Postgres add-on with TimescaleDB, and the trackers still have nothing to connect to. |
| **OpenRemote CloudFormation, single EC2** | **Recommended** | 46 to 78 | Purpose-built for this compose file. Creates the instance, encrypted root and data disks, daily and weekly snapshots, CloudWatch alarms, a Route53 updater, S3 backups and SES SMTP credentials. This repo's GitHub workflow already calls the upstream pipeline that deploys onto it. |
| **CivicView CDK patterns, ECS on EC2** | Later, if productised | 220 to 240 | Foundation, edge, secrets, CI/CD and cdk-nag discipline port over nearly verbatim. New work: an NLB for 8883, path-based routing for `/auth`, and Postgres as a container on a retained EBS volume because **RDS and Aurora have no TimescaleDB**. The NAT gateway and two load balancers are most of the cost. |
| **ECS Fargate** | Poor database story | 225 to 280 | Cleanest compute, but Postgres would sit on EFS, which is slow and expensive for a time-series database. |
| **Co-locate on the CivicView staging host** | No | — | That `m6i.large` already reserves 5.7 of 7.7 GB, and its IAM guardrails are prefix-scoped to `civicview*` by design. |

## Recommended shape, line by line

| Item | t4g.medium (4 GB) | t4g.large (8 GB) |
|---|---:|---:|
| EC2 instance, ARM | 31.68 | 63.29 |
| EBS gp3, root 16 GB + data 32 GB | 5.03 | 5.03 |
| Elastic IP | 3.65 | 3.65 |
| Snapshots, daily 7 days + weekly 4 weeks | ~3.00 | ~3.00 |
| Route53 hosted zone | 0.50 | 0.50 |
| CloudWatch logs and alarms | ~2.00 | ~2.00 |
| S3 backups, SES email, egress under 100 GB | ~0.50 | ~0.50 |
| **Total USD** | **~46** | **~78** |
| **Total ZAR ex VAT** | **~R 770** | **~R 1,300** |

Start on `t4g.large` and step down if it idles. Stopping the instance outside working hours saves about 60 percent of the EC2 line; the upstream template ships `start_stop_host.sh`.

Unit prices used (af-south-1): t4g.medium $0.0434/h, t4g.large $0.0867/h, gp3 $0.1047/GB-month, public IPv4 $0.005/h, ALB $0.03/h + $0.0095/LCU-h, NLB $0.03/h + $0.0071/NLCU-h, Fargate $0.0546/vCPU-h + $0.0060/GB-h, EFS $0.39/GB-month, RDS db.t4g.small $0.041/h. NAT gateway rates were not verified against the price list and are quoted at about 10 percent tolerance.

## Deploying with OpenRemote's own tooling

`.ci_cd/` in this repo is a stub: a README, an empty `env/` and `host_init/`, and one line `ENV_COMPOSE_FILE=profile/prod_cicd.yml`. Everything real lives in `openremote/openremote/.ci_cd/` and is pulled at workflow time by `.github/workflows/ci_cd.yml`, which calls `openremote/openremote/.github/workflows/ci_cd.yml@master` with `secrets: inherit`.

What the upstream `cloudformation-create-ec2.yml` provisions: an ARM AL2023 instance (`t4g.medium` default, constrained to t4g/m6g), encrypted gp3 root and data disks, a security group opening 80/443/8883, a DLM snapshot policy (7 daily, 4 weekly), a CloudWatch log group and five alarms, an SNS email topic, a Route53 DNS-updater service, a daily S3 backup timer, 2 GB of swap, Docker and Compose, and SES SMTP credentials written to `/etc/environment`.

### Steps

1. **Clean up the branch.** Follow [branch-review.md](branch-review.md). Rebase onto upstream `main`, drop the hardcoded passwords, pin image tags, rename the deployment image to an OCL registry, set the map centre to Durban.
2. **Prepare the AWS account** in af-south-1: a hosted zone for the fleet hostname, an EC2 key pair named `openremote`, the five security groups the template expects (`http-access`, `mqtt-access`, `ping-access`, `snmp-access`, `ssh-access`), and a verified SES sender if you want email alerts. The account also hosts CivicView and Metabase, so tag everything `Project=fleet` for cost allocation.
3. **Create the host.** Run `cloudformation-create-ec2.yml` from the upstream repo with `InstanceType=t4g.large`, `ElasticIP=true`, `DataDiskSize=32`. Let's Encrypt needs the hostname resolving before the proxy first starts.
4. **Wire GitHub Actions.** Secret names are dictated by the upstream workflow, so read `openremote/openremote/.github/workflows/ci_cd.yml` first. Expect AWS credentials or a role, the SSH private key, Docker Hub login, `OR_ADMIN_PASSWORD`, `CUSTOM_USER_PASSWORD`. Add `.ci_cd/env/production.env` with `OR_HOSTNAME`, `OR_EMAIL_ADMIN` and the deployment image tag. Trigger with `workflow_dispatch`, environment `production`, `CLEAN_INSTALL=true` for the first run only.
5. **Fix the tiles.** Build or download a South Africa or KwaZulu-Natal MBTiles extract (Protomaps and OpenMapTiles both offer regional builds). Copy it to the data disk and set `OR_MAP_TILES_PATH`, or upload it through Settings, then Appearance once the manager is up. Remove the EFS volume block from `profile/prod_cicd.yml`.
6. **Verify MQTTS.** Trackers connect to `<hostname>:8883` with the reversed Let's Encrypt fullchain, publishing to `master/<clientId>/teltonika/<IMEI>/data`. The handler auto-creates a vehicle asset on the first message, so one real or simulated FMC003 is the end-to-end smoke test.

> **Never set `OR_SETUP_RUN_ON_RESTART=true` in production.** It runs a Flyway clean on every boot, which drops the schema and every datapoint. `profile/dev-ui.yml` sets it on purpose; `prod_cicd.yml` must not.

## If fleet moves into the CivicView CDK later

Fork `iac/` from `civic-view-platform` into this repo rather than adding a seventh stack there. Its execution role, secret paths and IAM policies are prefix-scoped to `civicview*` to keep projects apart.

| Layer | Reuse | Change |
|---|---|---|
| Six-stack split, environment config, tagging, cdk-nag | Verbatim | Rename prefixes and the bootstrap qualifier |
| Foundation (VPC, NAT, security groups, flow logs) | ~95% | New CIDR. Ingress rule for MQTT from the NLB |
| Edge (ALB, ACM, Route53, health checks) | ~80% | Host-header routing becomes path-based: Keycloak on `/auth/*` at a lower priority number than the manager catch-all. Keep the port 9000 `/health/ready` health check. The HAProxy container disappears |
| Secrets Manager inventory pattern | Pattern only | New inventory: DB password, Keycloak bootstrap, OR admin, service user |
| `AppService` construct | Yes | Add EFS or reuse the EBS bind-mount volumes |
| EBS volume via ASG lifecycle hook, hourly dump to S3 | Yes, the most useful piece | This is the MariaDB pattern. Run `openremote/postgresql` on it instead, since RDS lacks TimescaleDB |
| Four GitHub workflows and OIDC roles | Rename and go | Environment-claim trust, read-only PR diffs, immutable ECR tags all apply |
| Network Load Balancer on 8883 | New | TLS at the NLB with the existing ACM cert, forwarding to the manager on 1883. About $27/month |

Do not put `awsvpc` tasks on a T-family instance in that design. ENI trunking does not apply to burstable instances, which is why CivicView moved to `m6i.large`.
