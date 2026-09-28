ARG PODMAN_IMAGE=quay.io/podman/stable:v5.7.1
FROM ${PODMAN_IMAGE}

USER root

# The image intentionally uses Podman's native Fedora userspace.
# Hurl is no longer packaged in Fedora 43 repositories; it is installed below
# from the official upstream release binaries. libxml2 is their runtime
# library dependency (libcurl/libssl already come with curl).
RUN dnf install -y --setopt=install_weak_deps=False \
      bash \
      ca-certificates \
      curl \
      findutils \
      git \
      git-lfs \
      gzip \
      iproute \
      jq \
      libxml2 \
      openssh-clients \
      python3 \
      python3-pip \
      shadow-utils \
      tar \
      unzip \
      which \
    && dnf clean all

# Install hurl/hurlfmt from the official Hurl release. The official Docker
# image is Alpine/musl-based, so its binaries cannot run on this glibc image.
# SHA-256 values are the upstream-published checksums of the release tarballs:
# https://github.com/Orange-OpenSource/hurl/releases/tag/8.0.1
ARG TARGETARCH
ARG HURL_VERSION=8.0.1
RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) hurl_arch=x86_64; hurl_sha256=cac7c4670d69444db120edb21fe06c97ba8c80dcc52279957c8dd18f05fb0c06 ;; \
      arm64) hurl_arch=aarch64; hurl_sha256=bc4732df4754748e9bf296aa3832ec019f798afb399f1279b72ed37b6e04525c ;; \
      *) echo >&2 "unsupported TARGETARCH: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/hurl.tar.gz \
      "https://github.com/Orange-OpenSource/hurl/releases/download/${HURL_VERSION}/hurl-${HURL_VERSION}-${hurl_arch}-unknown-linux-gnu.tar.gz"; \
    echo "${hurl_sha256}  /tmp/hurl.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/hurl.tar.gz -C /tmp; \
    install -m 0755 "/tmp/hurl-${HURL_VERSION}-${hurl_arch}-unknown-linux-gnu/bin/hurl" /usr/local/bin/hurl; \
    install -m 0755 "/tmp/hurl-${HURL_VERSION}-${hurl_arch}-unknown-linux-gnu/bin/hurlfmt" /usr/local/bin/hurlfmt; \
    rm -rf /tmp/hurl.tar.gz "/tmp/hurl-${HURL_VERSION}-${hurl_arch}-unknown-linux-gnu"

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
