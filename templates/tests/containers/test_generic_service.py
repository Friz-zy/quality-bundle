import pytest
from testcontainers.core.container import DockerContainer

@pytest.mark.container
def test_generic_http_dependency(testcontainers_podman):
    with DockerContainer("docker.io/library/nginx:alpine").with_exposed_ports(80) as nginx:
        host = nginx.get_container_host_ip()
        port = nginx.get_exposed_port(80)
        assert host
        assert int(port) > 0
