# Tester le déploiement TaskFlow et Kiali (Git Bash sur Windows)

Exécuter les commandes depuis la racine du dépôt `taskFlow`. Docker Desktop doit être
démarré en mode conteneurs Linux. Les outils `minikube`, `kubectl`, `docker`, `python`
et `istioctl` doivent être installés. Le chemin ci-dessous correspond à l'installation
d'Istio 1.32.0 proposée pour Windows ; l'adapter si la version ou le dossier diffère.

```bash
export ISTIO_HOME="$HOME/tools/istio/istio-1.32.0"
export PATH="$ISTIO_HOME/bin:$PATH"
istioctl version --remote=false
```

### Si Docker Desktop fournit un `kubectl` trop ancien

Un client `kubectl` 1.34 est hors de la plage prise en charge pour Kubernetes 1.37.
Dans Git Bash, installer localement le client 1.37 correspondant au cluster :

```bash
mkdir -p "$HOME/tools/kubectl"
curl -fL "https://dl.k8s.io/release/v1.37.0/bin/windows/amd64/kubectl.exe" \
  -o "$HOME/tools/kubectl/kubectl.exe"
export PATH="$HOME/tools/kubectl:$PATH"
kubectl version --client
```

Le changement de `PATH` vaut pour cette fenêtre Git Bash. Le refaire dans les autres
fenêtres si besoin. La commande `minikube kubectl -- get pods -A` permet aussi
d'utiliser directement le client fourni par Minikube.

## Redémarrer un déploiement qui a déjà passé le smoke test

Un simple `minikube stop` conserve les ressources Kubernetes et les images du
cluster. Il n'est donc pas nécessaire de reconstruire les images ou de recréer les
secrets à chaque démarrage.

```bash
minikube start
minikube status
kubectl get namespace istio-system taskflow
kubectl -n istio-system get deployment istiod
kubectl -n taskflow get deployment gateway
```

Attendre `APIServer: Running` avant toute commande `kubectl`. Si l'API reste
arrêtée, relancer `minikube start` et consulter `minikube logs` en cas d'échec.
Si une des ressources ci-dessus est introuvable, passer à la section
**Déployer depuis un cluster neuf** avant d'installer les addons. Si tout existe,
continuer :

```bash
kubectl -n istio-system rollout status deployment/istiod --timeout=300s
kubectl -n taskflow rollout status deployment/gateway --timeout=300s
kubectl -n taskflow get pods
kubectl apply -f "$ISTIO_HOME/samples/addons"
kubectl -n istio-system rollout status deployment/kiali --timeout=300s
```

L'avertissement de version de `kubectl` est distinct de l'absence des namespaces.
Le corriger avec les commandes de la section précédente avant de poursuivre.

## Déployer depuis un cluster neuf

Prévoir au moins 4 CPU et 7 Gio de mémoire pour Minikube et Istio. Les six images
TaskFlow sont d'abord construites par Docker Desktop, puis chargées dans Minikube.
Cette méthode fonctionne avec les runtimes `containerd` et Docker de Minikube.

```bash
minikube start --driver=docker --cpus=4 --memory=7168
minikube status
istioctl install --set profile=demo -y
kubectl -n istio-system rollout status deployment/istiod --timeout=300s

docker compose build
for image in \
  taskflow/user-service:latest \
  taskflow/workspace-service:latest \
  taskflow/task-service:latest \
  taskflow/analytics-service:latest \
  taskflow/frontend:latest \
  taskflow/gateway:latest; do
  minikube image load --daemon "$image"
done

kubectl apply -f k8s/namespace.yaml
python scripts/k8s_secrets.py
kubectl apply -k k8s/base
kubectl apply -f k8s/istio/gateway.yaml

kubectl -n taskflow rollout status statefulset/postgres --timeout=300s
kubectl -n taskflow rollout status statefulset/rabbitmq --timeout=300s
for service in user-service workspace-service task-service analytics-service frontend gateway; do
  kubectl -n taskflow rollout status "deployment/$service" --timeout=300s
done
kubectl -n taskflow get pods,svc,pvc

kubectl apply -f "$ISTIO_HOME/samples/addons"
kubectl -n istio-system rollout status deployment/kiali --timeout=300s
```

Le script `scripts/k8s_secrets.py` crée `.k8s.env` une seule fois et le réutilise.
Ce fichier est ignoré par Git. Le conserver tant que les volumes PostgreSQL et
RabbitMQ existent : leurs identifiants ont été initialisés avec ses valeurs.

## Ouvrir TaskFlow et Kiali

Utiliser trois fenêtres Git Bash. Le port 8080 doit être libre : arrêter la stack
Docker Compose si elle l'utilise.

**Fenêtre 1**, depuis la racine du projet :

```bash
kubectl -n istio-system port-forward svc/istio-ingressgateway 8080:80
```

**Fenêtre 2**, pour ouvrir Kiali dans le navigateur :

```bash
export ISTIO_HOME="$HOME/tools/istio/istio-1.32.0"
export PATH="$ISTIO_HOME/bin:$PATH"
istioctl dashboard kiali
```

**Fenêtre 3**, depuis la racine du projet, pour produire du trafic :

```bash
python scripts/taskflow.py smoke
```

Ouvrir aussi <http://localhost:8080> pour utiliser l'application. Dans Kiali,
choisir **Graph**, puis le namespace **taskflow**. Actualiser le graphe après le
smoke test. Les pods applicatifs doivent afficher `2/2` dans la sortie de
`kubectl -n taskflow get pods` : un conteneur applicatif et un proxy Istio. PostgreSQL et RabbitMQ,
sans sidecar, affichent `1/1`.

## Démontrer Kubernetes et le circuit breaker

Afficher les ressources, puis augmenter temporairement TaskService à deux répliques :

```bash
kubectl -n taskflow get deployments,pods,services
kubectl -n taskflow scale deployment/task-service --replicas=2
kubectl -n taskflow rollout status deployment/task-service --timeout=300s
kubectl -n taskflow get pods -l app=task-service
kubectl -n taskflow scale deployment/task-service --replicas=1
```

Le circuit breaker est une règle Istio optionnelle. L'appliquer pour une
démonstration de charge vers WorkspaceService, puis la retirer. Le smoke test seul
ne suffit pas à montrer son déclenchement : il faut envoyer plusieurs requêtes
concurrentes vers ce service et observer les réponses et métriques dans Kiali.

```bash
kubectl apply -f k8s/istio/circuit-breaker.yaml
kubectl -n taskflow get destinationrule workspace-circuit-breaker
kubectl delete -f k8s/istio/circuit-breaker.yaml
```

## Arrêter ou supprimer

Pour arrêter le cluster **sans perdre le déploiement ni les données** :

```bash
minikube stop
```

Pour supprimer tout le déploiement TaskFlow, y compris ses volumes et leurs données :

```bash
kubectl delete -f k8s/istio/circuit-breaker.yaml --ignore-not-found
kubectl delete -f k8s/istio/gateway.yaml --ignore-not-found
kubectl delete -f k8s/namespace.yaml
minikube stop
```

Références : [chargement des images dans Minikube](https://minikube.sigs.k8s.io/docs/handbook/pushing/),
[démarrage d'Istio avec Kiali](https://istio.io/latest/docs/setup/additional-setup/getting-started-istio-apis/)
et [compatibilité de `kubectl`](https://kubernetes.io/releases/version-skew-policy/).
