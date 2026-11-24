FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY bram ./bram
RUN pip install --no-cache-dir . \
    && useradd --uid 10001 --no-create-home bram \
    && mkdir /data && chown bram /data && chmod 700 /data
USER bram
VOLUME /data
EXPOSE 8765
ENTRYPOINT ["bram-server", "--data", "/data"]
CMD ["run"]
