# Infrastructure boundary

This directory marks the home for future deployment files. It intentionally contains no Terraform, Kubernetes, Helm, or CI configuration because the current platform does not use those technologies.

Add infrastructure only when a real deployment target exists:

- `terraform/` for reviewed cloud resources and state configuration.
- `k8s/` for Kubernetes or Helm resources after a cluster is selected.
- `github/` for repository CI workflows and evaluation gates.

The current deployment artifacts are the three application Dockerfiles and the root `docker-compose.yml`.
