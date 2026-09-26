ARG PODMAN_IMAGE=quay.io/podman/stable:v5.7.1
FROM ${PODMAN_IMAGE}

USER root

# The image intentionally uses Podman's native Fedora userspace.
# Hurl is installed from Fedora repositories when available.
RUN dnf install -y --setopt=install_weak_deps=False \
      bash \
      ca-certificates \
      curl \
      findutils \
      git \
      git-lfs \
      gzip \
      hurl \
      iproute \
      jq \
      openssh-clients \
      python3 \
      python3-pip \
      shadow-utils \
      tar \
      unzip \
      which \
    && dnf clean all

# Install uv without adding another package manager to the target repository.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ARG QUALITY_EXTRAS=all
WORKDIR /opt/quality-bundle
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN uv sync --no-dev --extra "${QUALITY_EXTRAS}"

COPY bin ./bin
COPY containers ./containers
COPY SKILL.md ./

# Rootless runner identity. Standard mode can use these subordinate IDs when the
# outer runtime exposes the required user-namespace capabilities. Restricted mode
# does not depend on them and uses VFS + ignore_chown_errors.
RUN useradd --create-home --uid 1000 --shell /bin/bash e2e \
    && echo 'e2e:100000:65536' >> /etc/subuid \
    && echo 'e2e:100000:65536' >> /etc/subgid \
    && mkdir -p /workspace /home/e2e/.config/containers /home/e2e/.local/share/containers/storage \
    && chown -R e2e:e2e /workspace /home/e2e /opt/quality-bundle

ENV HOME=/home/e2e \
    XDG_CONFIG_HOME=/home/e2e/.config \
    XDG_DATA_HOME=/home/e2e/.local/share \
    XDG_RUNTIME_DIR=/tmp/podman-run-1000 \
    E2E_PODMAN_MODE=restricted \
    E2E_CONTAINER_RUNTIME=podman \
    PATH=/opt/quality-bundle/.venv/bin:/opt/quality-bundle/bin:${PATH}

WORKDIR /workspace
USER e2e

ENTRYPOINT ["/opt/quality-bundle/containers/entrypoint.sh"]
CMD ["quality", "doctor"]
