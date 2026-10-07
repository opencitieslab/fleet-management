# Branch review: `feat/ocl-local-dev`

Reviewed 2026-09-14. The branch is one commit (`c6cec9f`) on top of `813b91f`, a February checkout of upstream at **OpenRemote 1.15.1**. Upstream `main` (`bfae0e0`, 2026-09-04) is at **OpenRemote 1.30.0** and rewrote the Keycloak environment block in `docker-compose.yml` that the branch also edits. Rebase before anything else.

## What the branch changes

| Change | Verdict | Notes |
|---|---|---|
| Postgres bound to `127.0.0.1:5999` in `docker-compose.yml` | Keep | Loopback only. Right for local dev and for an SSH-tunnelled seed run on the server. Matches the IDE datasource in `.idea/dataSources.xml`. |
| `OR_ADMIN_PASSWORD: admin` and `KEYCLOAK_ADMIN_PASSWORD: admin` hardcoded | Drop | Replaces the fail-fast `${OR_ADMIN_PASSWORD:?must be set}` guards in a tracked file on a public fork. Upstream 1.30 already sets `OR_ADMIN_PASSWORD=secret` in `.env`, so the guards pass locally without this edit. On 1.30 the Keycloak variable is `KC_BOOTSTRAP_ADMIN_PASSWORD` anyway. |
| `deployment/map/mapsettings.json` | Drop | 29 bytes of trailing whitespace on one line. Editor artefact. |
| `seed_database.py` (965 lines) | Rework | A good Durban Solid Waste demo dataset (9 facilities, 40 trucks, 7 days of shift history) written straight into Postgres. Not idempotent. See [seeding-data.md](seeding-data.md). |

The two files `git status` lists as modified on a Windows checkout (`README.md`, `CustomManagerSetup.java`) are line-ending noise only. `git diff` shows zero hunks. `.editorconfig` mandates LF but `.gitattributes` has no `* text=auto`, which is why they appear.

## What changed upstream between 1.15.1 and 1.30.0

Three commits, 27 files, most of the churn in `yarn.lock`.

- `openremoteVersion` 1.15.1 to 1.30.0, Gradle wrapper 9.6.1, Yarn 4.17.1, Jackson 2.21.5, typescript-generator 4.1.1, Java 21.
- Keycloak: `KEYCLOAK_ADMIN_PASSWORD` became `KC_BOOTSTRAP_ADMIN_PASSWORD`, and `KC_HOSTNAME` is now the full URL `https://${OR_HOSTNAME}/auth` with `KC_HOSTNAME_PORT` removed. Keycloak 26.7 or later is required and custom themes need updates.
- Postgres default tag moved to `latest-slim`. `profile/deploy.yml` now tunes Postgres memory explicitly (`OR_DB_RAM`, `shared_buffers=128MB`, and so on).
- Manager images from 1.29.0 need an x86-64-v3 (AVX2) CPU. Fine on AWS, matters on old on-prem hardware.
- `TeltonikaMQTTHandler` migrated from `KeycloakSecurityContext` to `AuthContext` and from `Date` to `Instant` on `createdOn`. No functional change.
- `.github/workflows/publish-release.yml` was deleted. No workflow in this repo builds a manager image any more. `ci_cd.yml` now uses `secrets: inherit`.
- `build_and_publish_to_docker.sh` switched from `docker compose down -v` to removing only the `deployment-data` volume, so Postgres and cert volumes survive a redeploy.

## Inherited problems to fix in the same pass

1. **Image namespaces are personal.** `docker-compose.yml` pulls `pankalog/fleet-deployment`. `docker-compose-test.yml` pulls `pankalog/fleet-management`, an image with no Dockerfile in this repo. `profile/prod_cicd.yml` pulls `openremote/deployment`. Pick one registry (GHCR under `opencitieslab`, or ECR) and use it everywhere, including `build_and_publish_to_docker.sh`.
2. **Only the manager is pinned.** `proxy`, `keycloak` and `postgresql` float on `latest`. Pin them to the tags that shipped with 1.30.0.
3. **A default user with a default password.** `setup/.../CustomKeycloakSetup.java` creates realm `custom` with user `custom`, password from `CUSTOM_USER_PASSWORD` defaulting to `custom`. In production mode it only throws if the variable is *empty*, which the literal default never is. Either set the variable in the deploy environment or delete the realm setup.
4. **`CustomManagerSetup.onStart()` seeds nothing.** It is the template stub with a comment. That is why the SQL seed script exists.
5. **The production profile mounts EFS for a Europe tileset.** `profile/prod_cicd.yml` declares an NFS volume and sets `OR_MAP_TILES_PATH=/efs/europe.mbtiles`. Wrong continent and an extra monthly bill. Replace with a South Africa extract on the data disk.
6. **The map opens on Brussels.** `mapsettings.json` centres on `[4.374355, 50.839134]` at zoom 7. Durban is `[31.0218, -29.8587]` at about zoom 11. No `.mbtiles` file is committed (`*.mbtiles` is gitignored), so a working map needs one dropped in.
7. **`docker-compose-test.yml` is stale.** It still uses the 1.15 Keycloak variable names and sets a tiles path with no volume mounted. Either update it or delete it.
8. **Housekeeping.** `.idea/` is force-committed despite the ignore rule and leaks the AWS region and a Python 3.8 project SDK. `*.sh` is gitignored, so any `.ci_cd/host_init/*.sh` scripts must be force-added. `.env` still carries `KC_HOSTNAME_PORT` and `WEBSERVER_LISTEN_HOST`, which nothing reads any more. `test/src/logging-test.properties` is referenced by the test config but does not exist.

## Rebase plan

```bash
git fetch upstream
git checkout feat/ocl-local-dev
git rebase upstream/main
# resolve docker-compose.yml: keep the 127.0.0.1:5999 port mapping, take upstream's Keycloak block
git push --force-with-lease origin feat/ocl-local-dev
```

Then apply the fixes above as separate commits so they are easy to review.
