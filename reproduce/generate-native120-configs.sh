#!/usr/bin/env bash
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
config_root="$(cd -- "${script_dir}/../configs" && pwd -P)"
generated_dir="${config_root}/generated"
openssl_bin="${OPENSSL:-openssl}"

if [[ -e "${generated_dir}" || -L "${generated_dir}" ]]; then
    printf 'Refusing to overwrite existing generated config: %s\n' "${generated_dir}" >&2
    exit 1
fi

temporary_dir="$(mktemp -d "${config_root}/.native120-tmp.XXXXXX")"
cleanup_temporary() {
    local status=$?
    trap - EXIT
    if [[ -n "${temporary_dir:-}" && -d "${temporary_dir}" ]]; then
        rm -rf -- "${temporary_dir}"
    fi
    exit "${status}"
}
trap cleanup_temporary EXIT

mkdir -m 0700 "${temporary_dir}/certs" \
              "${temporary_dir}/node0" \
              "${temporary_dir}/node1" \
              "${temporary_dir}/node2"

"${openssl_bin}" ecparam -name prime256v1 -genkey -noout \
    -out "${temporary_dir}/certs/ca.key"
"${openssl_bin}" req -x509 -new -sha256 -days 90 \
    -key "${temporary_dir}/certs/ca.key" \
    -subj "/CN=qdrant-native120-local-benchmark-ca" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -out "${temporary_dir}/certs/ca.crt"

api_key="$("${openssl_bin}" rand -hex 32)"
printf '%s\n' "${api_key}" >"${temporary_dir}/api-key.txt"
chmod 0600 "${temporary_dir}/api-key.txt"

for node in node0 node1 node2; do
    "${openssl_bin}" ecparam -name prime256v1 -genkey -noout \
        -out "${temporary_dir}/certs/${node}.key"
    "${openssl_bin}" req -new -sha256 \
        -key "${temporary_dir}/certs/${node}.key" \
        -subj "/CN=${node}" \
        -out "${temporary_dir}/certs/${node}.csr"

    cat >"${temporary_dir}/certs/${node}.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=serverAuth,clientAuth
subjectAltName=DNS:${node},DNS:localhost,IP:127.0.0.1
EOF

    "${openssl_bin}" x509 -req -sha256 -days 30 \
        -in "${temporary_dir}/certs/${node}.csr" \
        -CA "${temporary_dir}/certs/ca.crt" \
        -CAkey "${temporary_dir}/certs/ca.key" \
        -CAcreateserial \
        -extfile "${temporary_dir}/certs/${node}.ext" \
        -out "${temporary_dir}/certs/${node}.crt" >/dev/null

    chmod 0600 "${temporary_dir}/certs/${node}.key"
    rm -f -- "${temporary_dir}/certs/${node}.csr" \
              "${temporary_dir}/certs/${node}.ext"
done

rm -f -- "${temporary_dir}/certs/ca.key" \
          "${temporary_dir}/certs/ca.srl"
chmod 0644 "${temporary_dir}/certs/ca.crt" \
           "${temporary_dir}/certs/node0.crt" \
           "${temporary_dir}/certs/node1.crt" \
           "${temporary_dir}/certs/node2.crt"

for node in node0 node1 node2; do
    cat >"${temporary_dir}/${node}/config.yaml" <<EOF
log_level: INFO
storage:
  storage_path: /qdrant/storage
  snapshots_path: /qdrant/snapshots
  performance:
    max_search_threads: 1
    max_optimization_runtime_threads: 1
    optimizer_cpu_budget: 1
  wal:
    wal_capacity_mb: 32
  optimizers:
    default_segment_number: 1
    indexing_threshold_kb: 10000000
    flush_interval_sec: 1
service:
  host: 0.0.0.0
  http_port: 6333
  grpc_port: 6334
  max_workers: 1
  api_key: "${api_key}"
  enforce_internal_auth: true
  enable_tls: false
  verify_https_client_certificate: false
cluster:
  enabled: true
  p2p:
    host: 0.0.0.0
    port: 6335
    enable_tls: true
  consensus:
    bootstrap_timeout_sec: 600
tls:
  cert: /etc/qdrant/certs/node.crt
  key: /etc/qdrant/certs/node.key
  ca_cert: /etc/qdrant/certs/ca.crt
telemetry_disabled: true
EOF
    chmod 0600 "${temporary_dir}/${node}/config.yaml"
done

mv -- "${temporary_dir}" "${generated_dir}"
temporary_dir=""
trap - EXIT
printf 'Generated private node configs and cluster certificates under %s\n' "${generated_dir}"
