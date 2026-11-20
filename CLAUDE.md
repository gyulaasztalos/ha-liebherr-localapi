# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Unofficial Home Assistant custom integration (domain `liebherr_localapi`) for Liebherr
Professional fridges/freezers with a **SmartModule**, talking to the appliance's own
unauthenticated REST API on port 8080 (the "LocalAPI"). Distributed through the HA
Marketplace / HACS default catalog. Not for consumer appliances or the cloud
SmartDevice HomeAPI (that is HA core's `liebherr` integration).

## Commands

Tests use `pytest-homeassistant-custom-component`, which pins the Home Assistant
version (`requirements_test.txt`, kept current by Renovate). Python ≥ 3.14.

```bash
uv venv --python 3.14 .venv && VIRTUAL_ENV=.venv uv pip install -r requirements_test.txt ruff
.venv/bin/pytest                                            # whole suite, < 2 s
.venv/bin/pytest tests/test_entities.py::test_set_target_temperature   # one test
.venv/bin/ruff check custom_components tests
.venv/bin/ruff format custom_components tests               # CI runs --check
```

CI (`.github/workflows/`): `tests.yml` (Ruff, pytest, and Breakage Radar for HA APIs
scheduled for removal, pinned rules, any finding fails), `validate.yml` (`hacs/action`
with no `ignore`, plus hassfest). Both must pass: the catalog requires them.
hassfest only runs in CI (it needs an HA core checkout).

The real appliance (owner's BRPSvh 6501) answers on `http://10.10.20.21:8080`, e.g.
`curl -s 10.10.20.21:8080/zones/0/state | jq`. Treat it as production: it holds food
under HACCP. Read freely, and never PUT/DELETE against it without the owner's go-ahead.

## Architecture

- **`api.py`**: thin aiohttp client. One `asyncio.Lock` serializes every request
  (the SmartModule's HTTP server copes badly with concurrency). `allowed_methods()`
  sends `OPTIONS` and returns the `Allow` header; that is how route support is probed.
- **`coordinator.py`**: `_async_setup` runs once per config entry load: reads
  `/appliance/info`, `/zones/{n}/info` and probes every route in `const.py`
  (`APPLIANCE_ROUTES`, `ZONE_ROUTES`) into `coordinator.routes`. `_async_update_data`
  polls `/appliance/state` + each `/zones/{n}/state` every 30 s. `async_write()` sends
  a control request and requests a refresh. Info and routes only refresh on reload, so
  firmware updates need an integration reload.
- **`entity.py`**: a device per appliance (serial number = identifier), plus one
  child device per zone only for multi-zone appliances (`ChildDeviceInfo`, HA ≥
  2026.9; the parent is `coordinator.device_id`, registered first in
  `async_setup_entry`). `supported(cap, state_key)` is **cap flag == 1 OR field
  present in state**, because the caps under-report.
- **Platforms are description-driven.** A **control** (switch/number/select/button) is
  created only if `supported(...)` **and** its route is in `coordinator.routes`. Where
  the state field exists but the route doesn't, `binary_sensor.py` creates a read-only
  fallback (`fallback_for`), e.g. child lock on the BRPSvh 6501.
- Details that look odd but are deliberate:
  - the temperature sensor uses `force_update=True`: the value can sit unchanged for
    hours, and exports like InfluxDB must still get a point every poll;
  - the door alarm delay is write-only in the API, so it is a `RestoreNumber` showing
    the last written value;
  - alarm states are `0` inactive, `1` active, `2` active and confirmed; alarm binary
    sensors are on for 1 and 2 with a `confirmed` attribute;
  - confirm buttons only send `DELETE` when the alarm state is `1` and otherwise succeed
    as a no-op. Confirming an already-cleared alarm makes the appliance report it as
    active-and-confirmed until its next update. Buttons must stay available:
    `unavailable` is reserved for "appliance unreachable".
- `strings.json` and `translations/en.json` are kept identical. Brand images live in
  `custom_components/liebherr_localapi/brand/` (original artwork, never a Liebherr
  logo). `manifest.json` keys: `domain`, `name`, then alphabetical (hassfest).

## LocalAPI facts (verified on firmware 3.2.4.0; see also README "Limitations")

- The official spec is `https://developer.liebherr.com/apis/smartmodule-localapi/openapi.json`
  (login required; v1.22.10). `GET /api/info` returns that version from the appliance.
- Status codes: **404** = route not registered on this firmware, **406** = route exists
  but the appliance lacks the feature, **400** = route works but the body is wrong. An
  empty-body `PUT` distinguishes them without changing anything.
- Many undocumented routes are registered (they answer `OPTIONS`), e.g.
  `/zones/0/air-sensor`, `/zones/0/light`, `/zones/0/fan`, but every GET outside the
  four documented reads returns 404 "LocalAPI is currently deactivated", even with the
  LocalAPI on. That message is the generic "not exposed" answer, not the real state.
- `temperature.displayed` is the **display** value: 1/16 °C steps, it converges to the
  setpoint (τ ≈ 9 min) and holds there; it does not show door openings. It is not the
  air temperature. SuperCool drives it to the zone's minimum (−5 °C).
- `temperatureAlarm.{upper,lower}.limit` are the alarm **temperatures**, not offsets.
  The appliance menu (Settings → Alarms) takes them as an offset from the setpoint
  (factory ±3 K) and the absolute limit moves with the setpoint: setpoint 5 → 8/2,
  setpoint 3 → 6/0. The threshold sensors report them as is.
- The physical appliance can have features its caps deny (SuperCool, humidity fan,
  light). Check routes and ask the owner before calling a feature unsupported.

## Tests

`tests/conftest.py` serves a fake appliance through HA's `aioclient_mock`, built from
JSON captured on the real fridge (`tests/fixtures/`, serial numbers anonymised).
`REAL_ROUTES` is the set of control routes that firmware answers `OPTIONS` for; every
other candidate route returns 404. Mutate the `appliance` fixture, then call `serve()`
to re-register the endpoints. `test_real_appliance_entities` pins the exact entity set
of the real fridge, so a change that adds or drops an entity must update it.

## Releases

Automatic (`auto-release.yml`): when a **merged PR** changes `custom_components/`,
`README.md` or `hacs.json`, it waits for Tests and Validate on the merge commit, bumps
the patch version in `manifest.json` (bot commit `Release X.Y.Z (#PR)`), tags `vX.Y.Z`
and publishes a GitHub release listing the commit subjects since the previous tag. For
minor/major, set `version` by hand in the PR. CI-only PRs and direct pushes to `main`
don't release. `release.yml` handles tags pushed by hand and refuses a tag that doesn't
match `manifest.json`. HACS/the Marketplace serve releases, so a change reaches users
only through a release.
