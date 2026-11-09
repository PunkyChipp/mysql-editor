# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm
ARG TARGETARCH
ENV PATH="/opt/python/bin:/opt/code-server/bin:${PATH}" \
    PIP_NO_INDEX=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/coder
WORKDIR /home/coder/coursework
# One installation layer also keeps builds practical with Docker's vfs driver.
RUN --mount=type=secret,id=build_ca,required=true \
    --mount=type=bind,source=editor,target=/mnt/editor \
    --mount=type=bind,source=starter,target=/mnt/starter \
    apt-get -o Acquire::https::CaInfo=/run/secrets/build_ca update && \
    apt-get -o Acquire::https::CaInfo=/run/secrets/build_ca install -y --no-install-recommends \
      curl ca-certificates git default-mysql-client libatomic1 procps && \
    rm -rf /var/lib/apt/lists/* && \
    case "$TARGETARCH" in \
      amd64) archive_arch=amd64; archive_sha=771bf6038658034d7caf509fcc44af50f0b8bdac5e738177b6cf9c4181dd3382 ;; \
      arm64) archive_arch=arm64; archive_sha=425d3bc5167c85dc070427d2aa93760083b02aec852ea9ce75c2906c99138f45 ;; \
      *) echo 'Unsupported architecture' >&2; exit 1 ;; \
    esac && \
    curl --fail --location --cacert /run/secrets/build_ca \
      "https://github.com/coder/code-server/releases/download/v4.145.0/code-server-4.145.0-linux-${archive_arch}.tar.gz" \
      -o /tmp/code-server.tar.gz && \
    echo "${archive_sha}  /tmp/code-server.tar.gz" | sha256sum -c - && \
    mkdir -p /opt/code-server /opt/study-extensions /opt/study /run/editor && \
    tar -xzf /tmp/code-server.tar.gz --strip-components=1 -C /opt/code-server && \
    rm /tmp/code-server.tar.gz && \
    python -m venv /opt/python && \
    PIP_NO_INDEX=0 /opt/python/bin/pip --cert /run/secrets/build_ca install --no-cache-dir \
      mysql-connector-python==9.5.0 debugpy==1.8.17 jedi==0.19.2 && \
    NODE_EXTRA_CA_CERTS=/run/secrets/build_ca code-server --user-data-dir /tmp/install-profile \
      --extensions-dir /opt/study-extensions \
      --install-extension ms-python.python@2026.4.0 \
      --install-extension ms-python.debugpy@2026.6.0 \
      --install-extension detachhead.basedpyright@1.40.2 \
      --install-extension mtxr.sqltools@0.28.6 \
      --install-extension mtxr.sqltools-driver-mysql@0.6.7 && \
    rm -rf /opt/study-extensions/ms-python.vscode-python-envs-* && \
    python -c "import json,pathlib; p=pathlib.Path('/opt/study-extensions/extensions.json'); p.write_text(json.dumps([x for x in json.loads(p.read_text()) if x.get('identifier',{}).get('id','').lower() != 'ms-python.vscode-python-envs']))" && \
    rm -rf /tmp/install-profile /root/.cache && \
    useradd --create-home --uid 1000 --shell /bin/bash coder && \
    mkdir -p /home/coder/coursework /home/coder/.local/share/code-server && \
    cp /mnt/editor/settings.json /opt/study/settings.json && \
    cp /mnt/editor/entrypoint.sh /opt/study/entrypoint.sh && \
    cp -a /mnt/starter/. /home/coder/coursework/ && \
    chmod 0555 /opt/study/entrypoint.sh && \
    chmod 0444 /opt/study/settings.json && \
    chown -R coder:coder /home/coder /run/editor && \
    chown -R root:root /opt/study-extensions /opt/study && \
    chmod -R go-w /opt/study-extensions /opt/study
USER 1000:1000
ENTRYPOINT ["/opt/study/entrypoint.sh"]
