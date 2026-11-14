"""A live gate that cannot run fails in CI instead of skipping (review WR-04 of phase 28).

``canary_world.live_env`` and ``canary_world.canary_world`` skip without a live setup, which
is right on a laptop and wrong in the CI step of GATE-02/03: there a renamed container or a
changed ``.env.exapp`` would turn every live test into a skip and the step green.

Plan 32-05b adds the two runs of D-32-11 for the tasks bundle: one step in job ``exapp``
without the Tasks app, and in job ``canary-nc35`` an install step before the canary and a
measuring step after it. The switch stands at steps only, never at a job.
"""

import importlib.util
import re
from pathlib import Path
from typing import ClassVar

import canary_world as cw
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def no_live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in cw.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)


def test_without_the_switch_a_missing_setup_skips(
    monkeypatch: pytest.MonkeyPatch, no_live_env: None
) -> None:
    monkeypatch.delenv(cw.ENV_REQUIRE_LIVE, raising=False)
    with pytest.raises(pytest.skip.Exception, match="no live run configured"):
        cw.live_env()


def test_with_the_switch_a_missing_setup_fails(
    monkeypatch: pytest.MonkeyPatch, no_live_env: None
) -> None:
    monkeypatch.setenv(cw.ENV_REQUIRE_LIVE, "1")
    with pytest.raises(pytest.fail.Exception, match="NC_MCP_REQUIRE_LIVE=1 but no live run"):
        cw.live_env()


def test_the_ci_step_of_the_gates_sets_the_switch() -> None:
    """The step that runs the canary and the pair proofs carries the switch in its env."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    steps = re.split(r"\n      - name: ", workflow)
    gate_steps = [step for step in steps if "tests/integration/test_canary.py" in step]
    assert len(gate_steps) == 1, "exactly one CI step runs the canary"
    step = gate_steps[0]
    assert f'{cw.ENV_REQUIRE_LIVE}: "1"' in step
    # Plan 33-09: the canary calls the modifying task tools, which register only behind it.
    assert 'NC_MCP_TASKS_UPDATE: "on"' in step
    assert "test_pair_equality_live.py" in step
    assert "test_provider_classes_live.py" in step


def _job_blocks(workflow: str) -> list[str]:
    """The job blocks of ci.yml, each starting with its two-space job key."""
    return re.split(r"\n  (?=[a-z][a-z0-9-]*:\n)", workflow)


def test_the_gates_run_on_nextcloud_35_only() -> None:
    """The gate step lives in job canary-nc35, which pins 35.0.1 and checks it.

    Owner decision WR-04 of 2026-09-30: every live proof of phase 28 was measured on
    Nextcloud 35, so the CI gate has to measure the same version. A step moved back into the
    exapp job, or a job that lost its image pin or its version check, would silently measure
    34 and still go green.
    """
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    blocks = _job_blocks(workflow)
    gate_jobs = [block for block in blocks if "tests/integration/test_canary.py" in block]
    assert len(gate_jobs) == 1, "exactly one CI job runs the canary"
    job = gate_jobs[0]
    assert job.startswith("canary-nc35:")
    assert "NC_EXAPP_NEXTCLOUD_IMAGE: nextcloud:35.0.1-apache" in job
    assert "versionstring: 35" in job
    exapp_jobs = [block for block in blocks if block.startswith("exapp:")]
    assert len(exapp_jobs) == 1
    assert "test_canary.py" not in exapp_jobs[0]


TASKS_LIVE = "tests/integration/test_tasks_live.py"
EXPECT = "NC_MCP_EXPECT_TASKS_APP"


def _job(workflow: str, name: str) -> str:
    jobs = [block for block in _job_blocks(workflow) if block.startswith(f"{name}:")]
    assert len(jobs) == 1, f"exactly one job {name}"
    return jobs[0]


def _steps(job: str) -> list[str]:
    """The steps of one job block, the first entry being the job head before its steps."""
    return re.split(r"\n      - name: ", job)


def test_the_exapp_job_runs_the_tasks_live_test_without_the_tasks_app() -> None:
    """D-32-11, first run: Nextcloud 34.0.3 with the switch and without the Tasks app."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = _job(workflow, "exapp")
    steps = [step for step in _steps(job) if TASKS_LIVE in step]
    assert len(steps) == 1, "exactly one step of job exapp runs the tasks live test"
    step = steps[0]
    assert f'{cw.ENV_REQUIRE_LIVE}: "1"' in step
    assert f'{EXPECT}: "0"' in step
    assert "set -a && . ./.env.exapp && set +a" in step
    assert "app:install tasks" not in job, "the job without the Tasks app never installs it"


def test_the_canary_job_installs_the_tasks_app_before_the_canary_and_measures_after() -> None:
    """D-32-11, second run: install, restart and show the version, canary, then the test."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    steps = _steps(_job(workflow, "canary-nc35"))
    install = [i for i, step in enumerate(steps) if "app:install tasks" in step]
    canary = [i for i, step in enumerate(steps) if "tests/integration/test_canary.py" in step]
    measured = [i for i, step in enumerate(steps) if TASKS_LIVE in step]
    assert len(install) == len(canary) == len(measured) == 1, (install, canary, measured)
    assert install[0] < canary[0] < measured[0], "install, canary, tasks live test in order"
    installing = steps[install[0]]
    assert "restart nextcloud" in installing, "a restart, or provider and navigation are stale"
    assert "status.php" in installing, "it waits until Nextcloud answers again"
    assert "grep -E '^  - tasks: '" in installing, "the version of the Tasks app in the log"
    step = steps[measured[0]]
    assert f'{cw.ENV_REQUIRE_LIVE}: "1"' in step
    assert f'{EXPECT}: "1"' in step


def test_no_job_sets_the_switch_for_all_its_steps() -> None:
    """The switch stands at steps only: the job integration has to keep skipping the file."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    head = workflow.split("\njobs:\n", 1)[0]
    assert cw.ENV_REQUIRE_LIVE not in head, "no workflow level switch"
    for block in _job_blocks(workflow)[1:]:
        assert cw.ENV_REQUIRE_LIVE not in _steps(block)[0], block.split(":", 1)[0]
    integration = _job(workflow, "integration")
    assert cw.ENV_REQUIRE_LIVE not in integration
    assert EXPECT not in integration


def test_the_switch_keeps_integration_tests_from_the_skip_of_the_shared_conftest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``NC_MCP_URL`` the shared conftest skips, unless the run demands a live setup.

    Under the switch a missing URL has to reach ``skip_or_fail`` of the test and fail there
    (W3 of phase 31); a skip marker set at collection would turn the step green.
    """
    spec = importlib.util.spec_from_file_location("shared_conftest", ROOT / "tests" / "conftest.py")
    assert spec is not None
    assert spec.loader is not None
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)

    class Item:
        keywords: ClassVar[dict[str, bool]] = {"integration": True}

        def __init__(self) -> None:
            self.markers: list[object] = []

        def add_marker(self, marker: object) -> None:
            self.markers.append(marker)

    monkeypatch.delenv("NC_MCP_URL", raising=False)
    monkeypatch.delenv(cw.ENV_REQUIRE_LIVE, raising=False)
    plain = Item()
    shared.pytest_collection_modifyitems(None, [plain])
    monkeypatch.setenv(cw.ENV_REQUIRE_LIVE, "1")
    demanded = Item()
    shared.pytest_collection_modifyitems(None, [demanded])
    assert len(plain.markers) == 1, "without the switch the run skips"
    assert demanded.markers == [], "with the switch the test decides, and fails"


def test_the_exapp_topology_stays_on_34_0_3_by_default() -> None:
    """Without an override compose.exapp.yml still starts Nextcloud 34.0.3.

    EXAPP-06 is measured on 34.0.3, and the only override is the canary-nc35 job (owner
    decision WR-04 of 2026-09-30); every other job and every local run keeps the default.
    """
    compose = (ROOT / "compose.exapp.yml").read_text(encoding="utf-8")
    assert "${NC_EXAPP_NEXTCLOUD_IMAGE:-nextcloud:34.0.3-apache}" in compose
