#!/usr/bin/env bash
# TaskFlow on Minikube + Istio, in the spirit of https://github.com/charroux/servicemesh
# Run from Git Bash (Windows), Linux or macOS, from anywhere in the repository.
#
#   scripts/k8s.sh up          cluster, Istio, images, TaskFlow, observability addons
#   scripts/k8s.sh status      pods (2/2 = app + Envoy sidecar), services, Istio objects
#   scripts/k8s.sh forward     app on http://localhost:8080 through the Istio ingress
#   scripts/k8s.sh kiali       Kiali on http://localhost:20001 (service graph)
#   scripts/k8s.sh grafana     Grafana on http://localhost:3000
#   scripts/k8s.sh jaeger      Jaeger on http://localhost:16686 (traces)
#   scripts/k8s.sh prometheus  Prometheus on http://localhost:9090
#   scripts/k8s.sh images      rebuild the six images and roll the deployments
#   scripts/k8s.sh down        delete TaskFlow (volumes included) and stop Minikube
#
# Variables: ISTIO_HOME (default ~/tools/istio/istio-1.32.0), MINIKUBE_CPUS (4),
# MINIKUBE_MEMORY (7168, in MiB; must fit in the memory given to Docker Desktop).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ISTIO_HOME="${ISTIO_HOME:-$HOME/tools/istio/istio-1.32.0}"
export PATH="$ISTIO_HOME/bin:$PATH"
NS=taskflow
APPS=(user-service workspace-service task-service analytics-service frontend gateway)
ADDONS=(prometheus kiali grafana jaeger)

step() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require() {
  for tool in docker minikube kubectl python istioctl; do
    command -v "$tool" >/dev/null || die "$tool not found${tool/istioctl/ (set ISTIO_HOME, now $ISTIO_HOME)}"
  done
  docker info >/dev/null 2>&1 || die "Docker is not running: start Docker Desktop first"
}

cluster() {
  step "Minikube"
  if minikube status >/dev/null 2>&1; then
    echo "already running"
  else
    minikube start --driver=docker --cpus="${MINIKUBE_CPUS:-4}" --memory="${MINIKUBE_MEMORY:-7168}"
  fi
  kubectl get nodes >/dev/null || die "Kubernetes API not reachable. If the cluster is broken (x509 errors), run: minikube delete, then this script again"
  local mem
  mem="$(kubectl get node minikube -o jsonpath='{.status.capacity.memory}')"
  echo "node memory: $mem (Istio demo + addons need about 6 GiB; recreate the cluster if it is smaller)"
}

istio() {
  step "Istio (demo profile)"
  if kubectl -n istio-system get deployment istiod >/dev/null 2>&1; then
    echo "already installed"
  else
    istioctl install --set profile=demo -y
  fi
  kubectl -n istio-system rollout status deployment/istiod --timeout=300s
  kubectl -n istio-system rollout status deployment/istio-ingressgateway --timeout=300s
}

build_images() {
  step "Build the six images and load them into Minikube"
  docker compose build
  for app in "${APPS[@]}"; do
    echo "load taskflow/$app:latest"
    minikube image load --overwrite=true "taskflow/$app:latest"
  done
}

deploy() {
  step "TaskFlow manifests"
  kubectl apply -f k8s/namespace.yaml
  python scripts/k8s_secrets.py
  kubectl apply -k k8s/base
  kubectl apply -f k8s/istio/gateway.yaml
  kubectl apply -f k8s/istio/resilience.yaml
  kubectl -n "$NS" rollout status statefulset/postgres --timeout=300s
  kubectl -n "$NS" rollout status statefulset/rabbitmq --timeout=300s
  for app in "${APPS[@]}"; do
    kubectl -n "$NS" rollout status "deployment/$app" --timeout=300s
  done
}

addons() {
  step "Observability addons: ${ADDONS[*]}"
  [ -d "$ISTIO_HOME/samples/addons" ] || die "missing $ISTIO_HOME/samples/addons"
  for addon in "${ADDONS[@]}"; do
    kubectl apply -f "$ISTIO_HOME/samples/addons/$addon.yaml"
  done
  for addon in "${ADDONS[@]}"; do
    kubectl -n istio-system rollout status "deployment/$addon" --timeout=300s
  done
}

status() {
  kubectl -n "$NS" get pods,svc,pvc
  echo
  kubectl -n "$NS" get gateways.networking.istio.io,virtualservices,destinationrules,peerauthentications 2>/dev/null
  echo
  kubectl -n istio-system get pods
}

forward() {
  # Same role as ingress-forward.sh in the reference lab.
  echo "TaskFlow: http://localhost:${1:-8080}  (Ctrl+C to stop)"
  kubectl -n istio-system port-forward service/istio-ingressgateway "${1:-8080}:80"
}

dashboard() { # name service local-port remote-port
  echo "$1: http://localhost:$3  (Ctrl+C to stop)"
  kubectl -n istio-system port-forward "service/$2" "$3:$4"
}

case "${1:-}" in
  up) require; cluster; istio; build_images; deploy; addons; status
      printf '\nNext: "scripts/k8s.sh forward" in one terminal, "scripts/k8s.sh kiali" in another,\nthen "python scripts/taskflow.py smoke" to generate traffic.\n' ;;
  status) status ;;
  forward) forward "${2:-8080}" ;;
  kiali) dashboard Kiali kiali 20001 20001 ;;
  grafana) dashboard Grafana grafana 3000 3000 ;;
  jaeger) dashboard Jaeger tracing 16686 80 ;;
  prometheus) dashboard Prometheus prometheus 9090 9090 ;;
  images) require; build_images
          for app in "${APPS[@]}"; do kubectl -n "$NS" rollout restart "deployment/$app"; done
          for app in "${APPS[@]}"; do kubectl -n "$NS" rollout status "deployment/$app" --timeout=300s; done ;;
  down) for f in fault-injection circuit-breaker mtls resilience gateway; do
          kubectl delete -f "k8s/istio/$f.yaml" --ignore-not-found
        done
        kubectl delete -f k8s/namespace.yaml --ignore-not-found
        minikube stop ;;
  *) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
