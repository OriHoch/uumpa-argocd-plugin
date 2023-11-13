#!/usr/bin/env bash

VERSION="v1.13.2"
URL="https://github.com/cert-manager/cert-manager/releases/download/${VERSION}/cert-manager.yaml"
echo "# Downloaded from ${URL} on $(date) using tests/apps/cert-manager/download.sh" > tests/apps/cert-manager/install.yaml
curl -L "${URL}" >> tests/apps/cert-manager/install.yaml
echo OK
