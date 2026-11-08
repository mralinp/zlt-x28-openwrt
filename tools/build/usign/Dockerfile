# usign (OpenWrt's package signer) for the machine that signs the X28 feed. The sources are the exact commits that
# OpenWrt 23.05 builds (package/system/usign and package/libs/libubox), so signatures match the router's opkg.
#   docker build -t x28-usign:1 tools/build/usign
FROM debian:bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake git ca-certificates libjson-c-dev \
	&& rm -rf /var/lib/apt/lists/*
ARG LIBUBOX=75a3b870cace1171faf57bd55e5a9a2f1564f757
ARG USIGN=f1f65026a94137c91b5466b149ef3ea3f20091e9
RUN set -eu; \
	fetch() { mkdir -p "$1" && cd "$1" && git init -q && git fetch -q --depth 1 "$2" "$3" && git checkout -q FETCH_HEAD && test "$(git rev-parse HEAD)" = "$3"; }; \
	fetch /src/libubox https://git.openwrt.org/project/libubox.git "$LIBUBOX"; \
	cd /src/libubox && cmake -DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF -DBUILD_STATIC=OFF . && make -j"$(nproc)" ubox && install -D libubox.so /usr/local/lib/libubox.so \
	&& install -d /usr/local/include/libubox && cp *.h /usr/local/include/libubox/; \
	fetch /src/usign https://git.openwrt.org/project/usign.git "$USIGN"; \
	cd /src/usign && cmake -DCMAKE_PREFIX_PATH=/usr/local . && make -j"$(nproc)" && install -D usign /usr/local/bin/usign

FROM debian:bookworm-slim
COPY --from=build /usr/local/bin/usign /usr/local/bin/usign
COPY --from=build /usr/local/lib/libubox.so /usr/local/lib/libubox.so
RUN ldconfig /usr/local/lib && usign 2>&1 | head -1 || true
ENTRYPOINT ["/usr/local/bin/usign"]
