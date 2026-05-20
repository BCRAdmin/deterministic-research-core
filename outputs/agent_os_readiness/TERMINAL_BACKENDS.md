# Terminal Backend Contracts

These are execution contracts only. No backend is started by the readiness runner.

| Backend | Status | Isolation | Network | Secrets | Gate | Valid |
| --- | --- | --- | --- | --- | ---: | ---: |
| `local_read_only` | `implemented_contract_only` | `host_user_no_extra_isolation` | `disabled_by_policy_for_readiness_pack` | `not_read_not_printed` | false | true |
| `docker_project_sandbox` | `planned_contract_ready_not_started` | `container_namespace_with_project_mount` | `off_by_default` | `empty_env_except_explicit_allowlist` | true | true |

## Verification

### local_read_only
- `commands_must_be_non_destructive`
- `dangerous_command_scan_before_execution`
- `workdir_must_equal:/Users/BjornRosinger/Documents/New project 2`
- validation_errors: `none`
- validation_warnings: `none`

### docker_project_sandbox
- `image_digest_pinned_before_use`
- `workspace_mount_read_write_scope_confirmed`
- `no_home_or_secret_mounts`
- `post_run_artifact_diff_review`
- validation_errors: `none`
- validation_warnings: `none`
