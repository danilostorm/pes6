FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git cmake ninja-build make clang g++ \
    python3 python3-venv xz-utils zip unzip gzip pigz \
    libssl-dev zlib1g-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /project
