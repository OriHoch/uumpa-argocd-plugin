# Uumpa ArgoCD Plugin - Vault

## Install

The Vault plugin depends on AppRole auth method, the values need to be set in env vars in the plugin sidecar container.

Following is an example of steps to install, but you might need to adjust it to your needs:

* Enable approle auth method with `approle/` path
* Enable kv v2 secrets engine with `kv/` path
* Create a policy named `read-only`:
```
path "kv/data/*" {
  capabilities = ["create", "list", "read", "update"]
}
```
* Click on the CLI icon on the top right and run the following commands:
  * `write auth/approle/role/read-only token_ttl=1h token_max_ttl=4h policies=read-only`
  * `read auth/approle/role/read-only/role-id`
  * `write auth/approle/role/read-only/secret-id -force`

Create a Secret with the vault approle details:

```
kubectl -n argocd create secret generic vault-approle \
  --from-literal=VAULT_ROLE_ID=ROLE_ID \
  --from-literal=VAULT_SECRET_ID=SECRET_ID \
  --from-literal=VAULT_ADDR=VAULT_ADDR
  --from-literal=VAULT_PATH=kv/data
```

Set the env vars in the plugin sidecar container:

```
envFrom:
  - secretRef:
      name: vault-approle
```

## Usage

Get values from Vault:

```yaml
- password:
    plugin: uumpa_argocd_plugin.plugins.vault
    path: my/secret
    key: password
```

Set values in Vault:

```yaml
update_vault:
  plugin: uumpa_argocd_plugin.plugins.vault
  hook: PreSync
  vault:
    my/secret:
      password: ~password~
```

## Reference

### Environment variables

| Name            | Description                                  | Default |
|-----------------|----------------------------------------------|---------|
| VAULT_ROLE_ID   | AppRole role_id to authenticate with VAult   | -       |
| VAULT_SECRET_ID | AppRole secret_id to authenticate with VAult | -       |
| VAULT_ADDR      | Vault URL                                    | -       |
| VAULT_PATH      | Path in Vault to get/set secrets in          | -       |

### Common attributes

| Name   | Description                         | Default |
|--------|-------------------------------------|---------|
| plugin | `uumpa_argocd_plugin.plugins.vault` | -       |

### Default data type

Get values from Vault path:

* if `key` is set - get the value of the key
* if `keys` is set - get the values of the keys as a map of key: value
* if neither are set - get the whole vault secret as a map of key: value

| Name | Description                         | Default               |
|------|-------------------------------------|-----------------------|
| path | Path to the Vault secret            | -                     |
| key  | Key to get from the secret          | -                     |
| keys | List of keys to get from the secret | -                     |

### Default hook

Update values in given Vault path, creates the Vault path if doen'st exist, updates only the specified keys, does not delete keys

| Name  | Description                                                              | Default |
|-------|--------------------------------------------------------------------------|---------|
| vault | map where key is a path and value is map of the key/values to set for it | -       |
