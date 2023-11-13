#!/usr/bin/env bash

VERSION="v1.49.0"
URL="https://github.com/jaegertracing/jaeger-operator/releases/download/${VERSION}/jaeger-operator.yaml"
echo "# Downloaded from ${URL} on $(date) using tests/apps/cert-manager/download.sh" > tests/apps/jaeger-operator/install.yaml
curl -L "${URL}" >> tests/apps/jaeger-operator/install.yaml
echo OK
