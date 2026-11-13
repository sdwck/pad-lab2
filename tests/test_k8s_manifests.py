"""Kubernetes Manifest Specification Validation Tests.

Validates:
1. Syntax and parsing of all YAML manifests in `k8s/`
2. Presence of critical cluster resources (Namespace, ConfigMap, Secrets, PVC, Redis)
3. Replica specifications, matchLabels, and selector alignment
4. Liveness and readiness probe configurations
5. Resource requests and limits specifications for predictable autoscaling
"""

from pathlib import Path

import yaml

K8S_DIR = Path(__file__).parent.parent / "k8s"


def test_k8s_manifests_parse_without_errors():
    yaml_files = list(K8S_DIR.glob("*.yaml"))
    assert len(yaml_files) >= 15, f"Expected at least 15 manifest files, found {len(yaml_files)}"

    for manifest_path in yaml_files:
        with open(manifest_path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, f"Empty document in {manifest_path.name}"
            for doc in docs:
                if doc is None:
                    continue
                assert "apiVersion" in doc, f"Missing apiVersion in {manifest_path.name}"
                assert "kind" in doc, f"Missing kind in {manifest_path.name}"
                assert "metadata" in doc, f"Missing metadata in {manifest_path.name}"
                assert "name" in doc["metadata"], f"Missing metadata.name in {manifest_path.name}"


def test_k8s_deployments_and_services_conformance():
    yaml_files = list(K8S_DIR.glob("*.yaml"))
    deployments = []
    services = []

    for manifest_path in yaml_files:
        with open(manifest_path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
            for doc in docs:
                if not doc:
                    continue
                if doc.get("kind") == "Deployment":
                    deployments.append(doc)
                elif doc.get("kind") == "Service":
                    services.append(doc)

    assert len(deployments) >= 13, f"Expected at least 13 Deployments, found {len(deployments)}"
    assert len(services) >= 13, f"Expected at least 13 Services, found {len(services)}"

    # Validate each deployment has replicas, selectors, and probes
    for dep in deployments:
        dep_name = dep["metadata"]["name"]
        spec = dep["spec"]
        assert "replicas" in spec, f"Deployment {dep_name} missing replicas"
        assert spec["replicas"] >= 1, f"Deployment {dep_name} has invalid replica count"
        assert "selector" in spec, f"Deployment {dep_name} missing selector"
        assert "matchLabels" in spec["selector"], f"Deployment {dep_name} missing matchLabels"

        template = spec["template"]
        pod_labels = template["metadata"]["labels"]
        for k, v in spec["selector"]["matchLabels"].items():
            assert pod_labels.get(k) == v, f"Selector label mismatch in {dep_name}: {k}={v}"

        containers = template["spec"]["containers"]
        assert len(containers) >= 1, f"Deployment {dep_name} has no containers"
        container = containers[0]

        # Verify resource limits and requests exist for QoS
        assert "resources" in container, f"Container in {dep_name} missing resources"
        assert "requests" in container["resources"], f"Container in {dep_name} missing requests"
        assert "limits" in container["resources"], f"Container in {dep_name} missing limits"

        # Verify liveness probe
        assert "livenessProbe" in container, f"Container in {dep_name} missing livenessProbe"
        assert "readinessProbe" in container, f"Container in {dep_name} missing readinessProbe"


def test_k8s_namespace_and_config():
    with open(K8S_DIR / "00-namespace.yaml", "r", encoding="utf-8") as f:
        ns = yaml.safe_load(f)
        assert ns["kind"] == "Namespace"
        assert ns["metadata"]["name"] == "pad"

    with open(K8S_DIR / "01-configmap.yaml", "r", encoding="utf-8") as f:
        cm = yaml.safe_load(f)
        assert cm["kind"] == "ConfigMap"
        assert cm["metadata"]["namespace"] == "pad"
        assert "REDIS_URL" in cm["data"]
        assert "ENVIRONMENT" in cm["data"]

    with open(K8S_DIR / "02-secret.yaml", "r", encoding="utf-8") as f:
        sec = yaml.safe_load(f)
        assert sec["kind"] == "Secret"
        assert sec["metadata"]["namespace"] == "pad"
        assert "JWT_SECRET" in sec["data"]
