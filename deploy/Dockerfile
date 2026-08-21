# SandScope agent runtime — Northflank (ADR-0012).
#
# Originally written for Hugging Face Docker Spaces; those moved behind a PRO
# subscription, so the runtime moved here. Nothing in this file was
# Spaces-specific, which is why the migration cost a path change and a set of
# stale comments rather than a rewrite.
#
# Installs the runtime closure ONLY. `pip install .` resolves the 10 runtime
# dependencies and deliberately not the `ml` extra, which is where torch,
# transformers and scikit-learn live. That split is ADR-0009 (train offline,
# serve light) and it is also a security boundary: the training extra carries 4
# known RCE advisories in transformers, and the runtime closure audits clean at
# 0 known vulnerabilities. Adding `[ml]` here would import all four into a
# public, internet-facing container.
#
# Models are consumed as ONNX + a Rust tokenizer. Measured: onnxruntime 83MB
# plus tokenizers 9MB, against torch 522MB + transformers 111MB + scipy 99MB +
# sklearn 47MB for the same inference. The whole runtime closure is ~237MB on
# disk and the process peaks at 108MB RSS during a run with re-ranking.

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

# Run as a non-root uid the image creates itself, so the filesystem is owned by
# the account that actually runs the process rather than depending on whatever
# the host happens to do with a root-owned image.
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

# Single worker on purpose, for a reason that outlives the host: the router
# holds per-provider disable state in process, so a second worker would give
# each copy a private view of which providers are currently cooling off after a
# rate limit. The plan here is 0.2 shared vCPU / 512MB, against a measured peak
# of 108MB, so one worker is also all the CPU there is to give.
CMD ["sh", "-c", "uvicorn sandscope_agent.api.app:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
