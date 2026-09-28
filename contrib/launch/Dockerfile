# Build and run a Tacita node in a container.
#   docker build -t tacita -f contrib/launch/Dockerfile .
#   docker run -d --name tacitad -p 29960:29960 -v tacita-data:/data tacita
FROM ubuntu:24.04 AS build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake pkg-config git ca-certificates \
    libssl-dev libzmq3-dev libunbound-dev libsodium-dev libunwind8-dev liblzma-dev libreadline-dev libexpat1-dev \
    libpgm-dev libhidapi-dev libusb-1.0-0-dev libprotobuf-dev protobuf-compiler libudev-dev libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY . .
RUN git submodule update --init --recursive || true
RUN mkdir -p build/release && cd build/release && \
    cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=OFF -DUSE_DEVICE_TREZOR=OFF ../.. && \
    make -j"$(nproc)" daemon simplewallet wallet_rpc_server

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libboost-chrono1.83.0t64 libboost-filesystem1.83.0 libboost-program-options1.83.0 libboost-serialization1.83.0 libboost-thread1.83.0 libhidapi-libusb0 libreadline8t64 libsodium23 libssl3t64 libunbound8 libusb-1.0-0 libzmq5 \
    && rm -rf /var/lib/apt/lists/* && useradd --system --home /data tacita && mkdir -p /data && chown tacita /data
COPY --from=build /src/build/release/bin/ /usr/local/bin/
USER tacita
VOLUME /data
EXPOSE 29960 29961
ENTRYPOINT ["tacitad", "--data-dir=/data", "--non-interactive", "--p2p-bind-ip=0.0.0.0", "--rpc-bind-ip=127.0.0.1"]
