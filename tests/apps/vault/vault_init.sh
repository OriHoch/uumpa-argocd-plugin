#!/usr/bin/env bash

kubectl -n vault rollout restart deploy/vault &&\
kubectl -n vault wait --for=condition=available --timeout=60s deploy/vault &&\
kubectl -n vault exec deploy/vault -- sh -c '
  apk update && apk add jq &&\
  export VAULT_ADDR=http://127.0.0.1:8200 &&\
  export VAULT_FORMAT=json &&\
  INIT_JSON="$(vault operator init -key-shares=1 -key-threshold=1)" &&\
  UNSEAL_KEY="$(echo $INIT_JSON | jq -r '.unseal_keys_hex[0]')" &&\
  ROOT_TOKEN="$(echo $INIT_JSON | jq -r '.root_token')" &&\
  echo $ROOT_TOKEN > /tmp/root_token &&\
  echo $UNSEAL_KEY > /tmp/unseal_key &&\
  vault operator unseal $UNSEAL_KEY &&\
  vault login $ROOT_TOKEN &&\
  vault secrets enable -version=2 kv &&\
  vault auth enable approle &&\
  echo "path \"kv/data/*\" {" > /tmp/policy.hcl &&\
  echo "  capabilities = [\"create\", \"list\", \"read\", \"update\"]" >> /tmp/policy.hcl &&\
  echo "}" >> /tmp/policy.hcl &&\
  vault policy write approle /tmp/policy.hcl &&\
  vault write auth/approle/role/approle token_ttl=1h token_max_ttl=4h policies=approle &&\
  vault read auth/approle/role/approle/role-id | jq -r .data.role_id > /tmp/role_id &&\
  vault write -force auth/approle/role/approle/secret-id | jq -r .data.secret_id > /tmp/secret_id &&\
  vault kv put -mount=kv test value=1234 hello=world
' &&\
kubectl -n vault apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: vault-approle
stringData:
  role_id: $(kubectl -n vault exec deploy/vault -- cat /tmp/role_id)
  secret_id: $(kubectl -n vault exec deploy/vault -- cat /tmp/secret_id)
EOF
