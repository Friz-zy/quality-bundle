"""E2E-077/078/079: testcontainers-over-podman fixture and journeys (T2)."""
import os, shutil, subprocess, time
from pathlib import Path
import httpx, pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _get_settled(url: str, attempts: int = 10) -> httpx.Response:
    """GET with bounded retry for the rootlessport first-connection race.

    The rootless port proxy accepts TCP before the container backend is up and
    resets the first request(s); generic_container's PortWaitStrategy cannot
    see past the proxy accept, so tolerate transient transport errors briefly.
    """
    for attempt in range(attempts):
        try:
            return httpx.get(url, timeout=15)
        except (httpx.TransportError, OSError):
            if attempt == attempts - 1:
                raise
            time.sleep(1)


@pytest.mark.container
def test_e2e_077_testcontainers_podman_fixture(podman_service, monkeypatch, request):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(podman_service))
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("TESTCONTAINERS_RYUK_DISABLED", raising=False)
    docker_host = request.getfixturevalue("testcontainers_podman")
    assert docker_host == f"unix://{podman_service}/podman/podman.sock"
    assert os.environ["TESTCONTAINERS_RYUK_DISABLED"] == "true"  # setdefault semantics
    assert (podman_service / "podman" / "podman.sock").is_socket()


@pytest.mark.container
def test_e2e_078_generic_container_publishes_and_serves(podman_service, monkeypatch,
                                                        sut_image):
    """generic_container resolves host/port without the Docker-compat HostConfig
    lookup: PodmanDockerContainer overrides the narrow host/IP/port methods for
    its explicitly published ports."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(podman_service))
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    from quality_bundle.testcontainers_runtime import generic_container
    with generic_container(sut_image, port=8080) as container:
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(8080))
        response = _get_settled(f"http://{host}:{port}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        networks = container.get_wrapped_container().attrs["NetworkSettings"]["Networks"]
        assert "podman" in networks


@pytest.mark.container
def test_e2e_079_containers_template_journey(podman_service, monkeypatch, invoke_cli,
                                             make_project, toxiproxy_pulled, tmp_path):
    _ = toxiproxy_pulled  # proves image pulls work before spending time on the journey
    root = make_project(tmp_path, {})
    shutil.copytree(REPO_ROOT / "templates/tests/containers", root / "tests/e2e/containers")
    for pulled in ("docker.io/library/busybox:latest", "docker.io/library/nginx:alpine"):
        pull = subprocess.run(["podman", "pull", pulled], capture_output=True,
                              text=True, timeout=300)
        if pull.returncode != 0:
            pytest.skip(f"template image pull failed: {pulled} {pull.stderr[-200:]}")
    env = {"XDG_RUNTIME_DIR": str(podman_service),
           "QUALITY_ARTIFACTS_DIR": str(tmp_path / "artifacts")}
    r = invoke_cli(["test", "tests/e2e/containers"], cwd=root, env_overrides=env, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
