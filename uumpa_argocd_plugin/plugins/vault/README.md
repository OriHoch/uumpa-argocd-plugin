# Uumpa ArgoCD Plugin - Vault

## Install

The Vault plugin depends on AppRole auth method, the values need to be set in env vars in the plugin sidecar container.

Following is an example of steps to install, but you might need to adjust it to your needs:

* Enable approle auth method with `approle/` path
* Enable kv v2 secrets engine with `kv/` path
* Create a policy named `approle`:
```
path "kv/data/*" {
  capabilities = ["create", "list", "read", "update"]
}
```
* Click on the CLI icon on the top right and run the following commands:
  * `write auth/approle/role/approle token_ttl=1h token_max_ttl=4h policies=approle`
  * `read auth/approle/role/approle/role-id`
  * `write -force auth/approle/role/approle/secret-id`

Create a Secret with the vault approle details:

```
kubectl -n argocd create secret generic vault-approle \
  --from-literal=ARGOCD_ENV_VAULT_ROLE_ID=ROLE_ID \
  --from-literal=ARGOCD_ENV_VAULT_SECRET_ID=SECRET_ID \
  --from-literal=ARGOCD_ENV_VAULT_ADDR=VAULT_ADDR
  --from-literal=ARGOCD_ENV_VAULT_PATH=kv/data
```

Set the env vars in the plugin sidecar container:

```
envFrom:
  - secretRef:
      name: vault-approle
```

## Usage

Get values from Vault, example `uumpa_data.yaml`:

```yaml
- password:
    plugin: uumpa_argocd_plugin.plugins.vault
    path: my/secret
    key: password
```

Set values in Vault, example `uumpa_generators.yaml`:

```yaml
- plugin: uumpa_argocd_plugin.plugins.vault
  path: my/secret
  data:
    password: ~password~
```

## Reference

### Environment variables

| Name                       | Description                                  | Default |
|----------------------------|----------------------------------------------|---------|
| ARGOCD_ENV_VAULT_ROLE_ID   | AppRole role_id to authenticate with Vault   | -       |
| ARGOCD_ENV_VAULT_SECRET_ID | AppRole secret_id to authenticate with Vault | -       |
| ARGOCD_ENV_VAULT_ADDR      | Vault URL                                    | -       |
| ARGOCD_ENV_VAULT_PATH      | Path in Vault to get/set secrets in          | -       |

### Common attributes

| Name   | Description                         | Default |
|--------|-------------------------------------|---------|
| plugin | `uumpa_argocd_plugin.plugins.vault` | -       |

### Data

Get values from Vault path:

* if `key` is set - get the value of the key
* if `keys` is set - get the values of the keys as a map of key: value
* if neither are set - get the whole vault secret as a map of key: value

| Name | Description                         | Default               |
|------|-------------------------------------|-----------------------|
| path | Path to the Vault secret            | -                     |
| key  | Key to get from the secret          | -                     |
| keys | List of keys to get from the secret | -                     |

### Generator

Update values in given Vault path using an ArgoCD Hook

Creates the Vault path if doen'st exist, updates only the specified keys, does not delete keys

| Name  | Description                                                                                                                                          | Default |
|-------|------------------------------------------------------------------------------------------------------------------------------------------------------|---------|
| name  | Name of the job to create, should be unique in case multiple vault generators are used in the same app                                               | -       |
| vault | Key-Value data, key is vault path, value is a map of key: value to set in that path                                                                  | -       |
| *     | Any other attribute will be added to the created job, see [/README.md#jobs](https://github.com/OriHoch/uumpa-argocd-plugin/blob/main/README.md#jobs) | -       |
