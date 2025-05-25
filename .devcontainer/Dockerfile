# Credit:
# https://endjin.com/blog/2025/01/spark-devcontainers-local-spark

FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    openjdk-17-jre \
    && apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# RUN python3 -m venv .sparkvenv \
#     && source .sparkvenv/bin/activate \
#     && pip install pyspark==3.5.5 delta-spark==3.3.1