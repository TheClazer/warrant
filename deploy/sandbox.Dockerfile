# Sandbox image for Warrant missions: NVIDIA's OpenShell base image plus the tools an agent needs.
FROM nvcr.io/nvidia/base/ubuntu:24.04
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*
