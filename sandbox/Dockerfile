FROM python:3.12-slim

# Scientific libraries an engineering calculation would plausibly need.
RUN pip install --no-cache-dir \
        numpy==2.2.1 \
        pandas==2.2.3 \
        scipy==1.15.0 \
        sympy==1.13.3 \
        openpyxl==3.1.5 \
    && rm -rf /root/.cache

# Non-root user. Code runs with no privileges and no home directory writes.
RUN useradd --create-home --shell /usr/sbin/nologin --uid 10001 sandboxuser

WORKDIR /workspace
USER sandboxuser

# Overridden at run time. Never starts on its own.
CMD ["python", "-c", "print('sandbox ready')"]
