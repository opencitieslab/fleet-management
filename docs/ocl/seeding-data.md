# Seeding data

OpenRemote offers three ways to get initial data in. The branch currently uses the least supported one.

## The three mechanisms

| Mechanism | Where | When it runs | Notes |
|---|---|---|---|
| **Java setup tasks** | `setup/src/main/java/org/openremote/manager/setup/custom/` | Once, on a clean install (empty database) | `CustomSetupTasks` returns `CustomKeycloakSetup` (creates realm `custom`, user `custom`) and `CustomManagerSetup` (empty stub). Good for realms, users and agents. Heavy for 40 vehicles. `OR_SETUP_TYPE` is a free string handed to your tasks; only `production` has meaning in this repo. |
| **JSON provisioning** | `deployment/manager/provisioning/assets/` (one `Asset` JSON per file) | Once, on a clean install, in filename order | Loaded by `ManagerSetup.provisionAssets()` through `AssetStorageService.merge`, so caches, rules and MQTT subscribers all see the assets. Idempotent by construction, no database access, ships inside the deployment image. The folder exists in this repo and is empty. |
| **Direct SQL** | `seed_database.py` | Whenever you run it | Inserts into `asset` and `asset_datapoint`, bypassing the manager. Nothing notices new assets until the manager restarts. |

Also available: the REST API (`POST /api/{realm}/asset`, `POST /api/{realm}/asset/attributes` for values) with a Keycloak service-user token, and the Teltonika MQTT handler, which auto-creates a `CarAsset` the first time a message arrives on `{realm}/{clientId}/teltonika/{IMEI}/data`. That MQTT path is how the upstream project expects vehicles to appear.

## What `seed_database.py` does

A 965-line Python 3 script (`psycopg2-binary`) modelling **eThekwini Municipality, Durban Solid Waste**. Defaults to `127.0.0.1:5999`, database `openremote`, user `postgres`, password `postgres`.

- **9 facilities** as `ThingAsset` in realm `master`: 3 landfills (Bisasar Road, Mariannhill, Buffelsdraai), 4 depots (Springfield, KwaMashu, Chatsworth, Isipingo), 2 transfer stations (Umlazi, Phoenix). Attributes: `location`, `facilityType`, `status`, `dailyCapacityTonnes`, `currentLoadPercentage`, `operatingHours`, `notes`.
- **40 vehicles** as `CarAsset` across 9 fleet groups (residential north/south/central/outer-west, commercial, skip trucks, illegal dumping response, landfill ops, supervisors). Real SA truck makes and KZN plates. Each gets a Luhn-valid IMEI, `modelNumber=FMC003` matching `deployment/manager/fleet/FMC003.json`, and the full Teltonika attribute set the Java model declares (`location`, `IMEI`, `lastContact`, `239` ignition, `240` movement, `16` odometer, `sp`, `alt`, `sat`, `pr`, `evt`, and so on) with `storeDataPoints`, `ruleState` and `readOnly` meta.
- **7 days of history** into `asset_datapoint`: depot to collection leg (stop-and-go, 4 to 18 km/h) to landfill (35 to 65 km/h), a dwell, a return leg, two trips per shift, six hand-drawn polylines with real bearings. Hourly `currentLoadPercentage` for facilities.

The attribute set mirrors `model/src/main/java/org/openremote/model/custom/CarAsset.java` correctly. The dataset itself is worth keeping.

## Why it is not repeatable

- Facilities **are** idempotent: IDs derive from a seeded random keyed on the facility name, and the insert is `ON CONFLICT (id) DO UPDATE`.
- Vehicles **are not**: the asset ID derives from the IMEI, and the IMEI comes from an unseeded `random`. Every run creates 40 brand-new vehicles.
- Datapoints **are not**: timestamps are randomised per run, so `ON CONFLICT DO NOTHING` almost never fires. Roughly 100k rows added per run.
- `random.seed()` is never called. There is no delete or reset path.
- Assets have `parent_id = NULL`, so nothing is grouped, and the running manager does not see them until restart.

## Recommended split

1. **Assets via provisioning JSON.** Refactor the facility and vehicle generators to write 49 JSON files into `deployment/manager/provisioning/assets/` instead of issuing inserts. Seed the random generator from a fixed string so IMEIs and IDs are stable across runs. Consider a `GroupAsset` per fleet group and set `parent_id` accordingly. These ship in the deployment image and load on clean install.
2. **History via SQL, once.** Keep the shift simulator, make its timestamps deterministic from the same seed, and target the IDs the JSON files carry. Run it over an SSH tunnel to the loopback port 5999 after the first deploy, then restart the manager. Add a `--reset` flag that deletes only rows for the seeded IDs.
3. **Phase two: an MQTT replay simulator.** A small script that publishes FMC003 JSON payloads to `master/<clientId>/teltonika/<IMEI>/data` over MQTTS exercises the real ingest path, creates vehicles through the handler, needs no database access, and doubles as a live demo. `test/src/test/resources/teltonikaValidPayload1.json` and `SortedPayloads.json` are usable payload templates.

## Gotchas

- `OR_SETUP_RUN_ON_RESTART=true` (or `OR_DEV_MODE=true`) forces a Flyway clean on every boot: the schema and all data are dropped and setup re-runs. `profile/dev-ui.yml` sets it deliberately. Never set it in production.
- `TeltonikaConfigurationFactory` lazily creates a "Teltonika Device Configuration" asset with an FMC003 child in `master` on first start, and hard-fails if more than one exists. Do not seed a second one.
- `CustomKeycloakSetup` creates user `custom` with password `custom` unless `CUSTOM_USER_PASSWORD` is set. In production mode it only throws if the variable is empty, which the default never is.
- Direct SQL never touches Keycloak, realms, users or asset links. Anything beyond assets and datapoints needs the setup tasks or the API.
