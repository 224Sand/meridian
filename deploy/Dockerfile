# SandScope agent runtime — Hugging Face Spaces (Docker SDK).
#
# Installs the runtime closure ONLY. `pip install .` resolves the 10 runtime
# dependencies and deliberately not the `ml` extra, which is where torch,
# transformers and scikit-learn live. That split is ADR-0009 (train offline,
# serve light) and it is also a security boundary: the training extra carries 4
# known RCE advisories in transformers, and the runtime closure audits clean at
# 0 known vulnerabilities. Adding `[ml]` here would import all four into a
# public, internet-facing container.
#
# Models are consumed as ONNX + a Rust tokenizer: ~50MB of runtime instead of
# the ~2-3GB the training frameworks would cost to do the same inference.

FROM python:3.11-slim AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Dependency layer first: pyproject alone changes far less often than source,
# so edits to the agent do not re-resolve the whole tree on every push.
COPY apps/agent/pyproject.toml ./pyproject.toml
COPY apps/agent/sandscope_agent/__init__.py ./sandscope_agent/__init__.py
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install .

COPY apps/agent/ ./
RUN /opt/venv/bin/pip install --no-deps .


FROM python:3.11-slim AS runtime

# Spaces runs the container as uid 1000. Creating the user explicitly means the
# filesystem is owned by the account that will actually run the process, rather
# than relying on the platform to paper over root-owned files.
RUN useradd --create-home --uid 1000 sandscope

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=7860

COPY --from=build /opt/venv /opt/venv
COPY --chown=sandscope:sandscope apps/agent/ /app/

WORKDIR /app
USER sandscope

EXPOSE 7860

# /healthz is unauthenticated by design so an orchestrator can probe liveness
# without holding a service token.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/healthz', timeout=4).status==200 else 1)"

# Single worker on purpose. The free Space is 2 vCPU, the router holds
# per-provider disable state in process, and a second worker would give each
# copy a private view of which providers are cooling off.
CMD ["sh", "-c", "uvicorn sandscope_agent.api.app:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
