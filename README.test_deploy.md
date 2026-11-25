# Déployer TaskFlow sur Kubernetes avec Istio et Kiali

Ce guide déploie TaskFlow sur un cluster **Minikube**, avec le service mesh **Istio**
et ses outils d'observation : **Kiali**, **Prometheus**, **Grafana** et **Jaeger**.
Il suit la démarche du TP [charroux/servicemesh](https://github.com/charroux/servicemesh).

Toutes les commandes s'exécutent dans **Git Bash**, depuis la racine du dépôt `taskFlow`.

## Sommaire

1. [Prérequis](#1-prérequis)
2. [Déploiement en une commande](#2-déploiement-en-une-commande)
3. [Déploiement pas à pas](#3-déploiement-pas-à-pas)
4. [Ouvrir l'application et les outils](#4-ouvrir-lapplication-et-les-outils)
5. [Générer du trafic](#5-générer-du-trafic)
6. [Démonstrations Kubernetes et Istio](#6-démonstrations-kubernetes-et-istio)
7. [Arrêter, redémarrer, supprimer](#7-arrêter-redémarrer-supprimer)
8. [Dépannage](#8-dépannage)

---

## 1. Prérequis

| Outil | Vérification |
|---|---|
| Docker Desktop, **démarré**, conteneurs Linux | `docker info` |
| Minikube | `minikube version` |
| kubectl | `kubectl version --client` |
| Python 3.12 | `python --version` |
| Istio 1.32 (archive décompressée) | `istioctl version --remote=false` |

### Ressources

Istio (profil `demo`), les quatre addons et les huit pods de TaskFlow demandent
**4 CPU et 7 Gio** pour Minikube. Docker Desktop doit disposer d'au moins 7,5 Gio
(*Settings > Resources*, ou fichier `%UserProfile%\.wslconfig` avec WSL 2).

### Rendre `istioctl` disponible

Télécharger Istio depuis <https://github.com/istio/istio/releases> et le décompresser
dans `~/tools/istio`, puis, dans chaque nouvelle fenêtre Git Bash :

```bash
export ISTIO_HOME="$HOME/tools/istio/istio-1.32.0"
export PATH="$ISTIO_HOME/bin:$PATH"
istioctl version --remote=false
```

Pour ne plus avoir à le refaire, ajouter ces deux `export` à la fin de `~/.bashrc`.
Le script `scripts/k8s.sh` utilise ce chemin par défaut. Pour un autre dossier,
définir `ISTIO_HOME` avant de le lancer.

### Antivirus avec analyse HTTPS (Avast, AVG, Kaspersky…)

> [!WARNING]
> Ces antivirus interceptent le HTTPS, y compris vers `127.0.0.1`, et remplacent le
> certificat de l'API Kubernetes par le leur. `kubectl`, `istioctl` et `minikube`
> échouent alors avec `x509: certificate signed by unknown authority`, et
> `minikube start` finit par `apiserver healthz never reported healthy`.
> Désactiver l'analyse HTTPS du bouclier Web, ou exclure `minikube.exe`, `kubectl.exe`
> et `istioctl.exe`.

Vérifier que le certificat présenté est bien celui de Minikube (cluster démarré) :

```bash
PORT=$(docker port minikube 8443 | head -1 | cut -d: -f2)
echo | openssl s_client -connect "127.0.0.1:$PORT" 2>/dev/null | openssl x509 -noout -issuer
# attendu : issuer=CN=minikubeCA
```

### Libérer le port 8080

La stack Docker Compose utilise aussi le port 8080, et la mémoire de Docker.
L'arrêter avant de déployer sur Kubernetes (les données sont conservées) :

```bash
docker compose stop
```

---

## 2. Déploiement en une commande

```bash
bash scripts/k8s.sh up
```

Le script enchaîne toutes les étapes de la [section 3](#3-déploiement-pas-à-pas) et
ignore celles qui sont déjà faites. Compter 10 à 15 minutes au premier lancement, à
cause des téléchargements. Il se termine par l'état des pods : les six applications
doivent afficher `2/2` (le conteneur applicatif et le proxy Envoy d'Istio).
PostgreSQL et RabbitMQ affichent `1/1`, car ils n'ont pas de sidecar.

Autres commandes du script :

| Commande | Rôle |
|---|---|
| `bash scripts/k8s.sh status` | Pods, services, volumes et objets Istio |
| `bash scripts/k8s.sh forward` | Application sur <http://localhost:8080> |
| `bash scripts/k8s.sh kiali` | Kiali sur <http://localhost:20001> |
| `bash scripts/k8s.sh grafana` | Grafana sur <http://localhost:3000> |
| `bash scripts/k8s.sh jaeger` | Jaeger sur <http://localhost:16686> |
| `bash scripts/k8s.sh prometheus` | Prometheus sur <http://localhost:9090> |
| `bash scripts/k8s.sh images` | Reconstruit les six images et redémarre les pods |
| `bash scripts/k8s.sh down` | Supprime TaskFlow (volumes compris) et arrête Minikube |

---

## 3. Déploiement pas à pas

Ce sont les commandes exécutées par `scripts/k8s.sh up`, à lancer à la main pour
comprendre ou déboguer chaque étape.

### 3.1 Cluster Minikube

```bash
minikube start --driver=docker --cpus=4 --memory=7168
kubectl get nodes          # STATUS Ready
```

Un cluster existant garde ses ressources d'origine : `--cpus` et `--memory` ne
s'appliquent qu'à sa création. Pour agrandir un cluster déjà créé, il faut le
supprimer avec `minikube delete`, ce qui efface tout son contenu.

### 3.2 Istio

```bash
istioctl install --set profile=demo -y
kubectl -n istio-system rollout status deployment/istiod --timeout=300s
kubectl -n istio-system get pods     # istiod, istio-ingressgateway, istio-egressgateway
```

L'injection automatique des sidecars est activée par le label du namespace, dans
[k8s/namespace.yaml](k8s/namespace.yaml) (`istio-injection: enabled`).

### 3.3 Images

Les images sont construites par Docker Desktop, puis copiées dans Minikube. Elles ne
sont publiées sur aucun registre (`imagePullPolicy: Never`).

```bash
docker compose build
for app in user-service workspace-service task-service analytics-service frontend gateway; do
  minikube image load --overwrite=true "taskflow/$app:latest"
done
minikube image ls | grep taskflow
```

### 3.4 TaskFlow

```bash
kubectl apply -f k8s/namespace.yaml
python scripts/k8s_secrets.py          # Secret Kubernetes, identifiants dans .k8s.env
kubectl apply -k k8s/base              # ConfigMap, PostgreSQL, RabbitMQ, services, front, gateway
kubectl apply -f k8s/istio/gateway.yaml      # entrée Istio -> gateway Nginx
kubectl apply -f k8s/istio/resilience.yaml   # timeout et retries vers WorkspaceService

kubectl -n taskflow rollout status statefulset/postgres --timeout=300s
kubectl -n taskflow rollout status statefulset/rabbitmq --timeout=300s
for app in user-service workspace-service task-service analytics-service frontend gateway; do
  kubectl -n taskflow rollout status "deployment/$app" --timeout=300s
done
kubectl -n taskflow get pods,svc,pvc
```

Pendant la première minute, WorkspaceService, TaskService et AnalyticsService
peuvent redémarrer une ou deux fois en attendant RabbitMQ. C'est normal.

`scripts/k8s_secrets.py` crée `.k8s.env` au premier lancement (ignoré par Git) et le
réutilise ensuite. Le conserver tant que les volumes PostgreSQL et RabbitMQ existent :
leurs identifiants ont été initialisés avec ces valeurs.

### 3.5 Kiali, Prometheus, Grafana, Jaeger

Les manifestes sont fournis dans l'archive Istio. Prometheus est indispensable à Kiali.

```bash
for addon in prometheus kiali grafana jaeger; do
  kubectl apply -f "$ISTIO_HOME/samples/addons/$addon.yaml"
done
for addon in prometheus kiali grafana jaeger; do
  kubectl -n istio-system rollout status "deployment/$addon" --timeout=300s
done
kubectl apply -f k8s/istio/tracing.yaml     # active l'envoi des traces vers Jaeger
```

Sans [k8s/istio/tracing.yaml](k8s/istio/tracing.yaml), Jaeger reste vide : le profil
`demo` déclare le fournisseur `jaeger`, mais une ressource `Telemetry` doit l'activer.
Elle échantillonne ici 100 % des requêtes, ce qui convient à une démonstration.

---

## 4. Ouvrir l'application et les outils

Chaque `port-forward` occupe sa fenêtre Git Bash tant qu'il tourne (Ctrl+C pour
l'arrêter). Ouvrir une fenêtre par outil.

| Fenêtre | Commande | Adresse |
|---|---|---|
| 1 | `kubectl -n istio-system port-forward service/istio-ingressgateway 8080:80` | <http://localhost:8080> : TaskFlow |
| 2 | `kubectl -n istio-system port-forward service/kiali 20001:20001` | <http://localhost:20001> : Kiali |
| 3 | `kubectl -n istio-system port-forward service/grafana 3000:3000` | <http://localhost:3000> : Grafana |
| 4 | `kubectl -n istio-system port-forward service/tracing 16686:80` | <http://localhost:16686> : Jaeger |
| 5 | `kubectl -n istio-system port-forward service/prometheus 9090:9090` | <http://localhost:9090> : Prometheus |

Avec `istioctl`, on peut aussi ouvrir directement le navigateur :
`istioctl dashboard kiali` (ou `grafana`, `jaeger`, `prometheus`).

### Lire Kiali

1. Menu **Traffic Graph**, namespace **taskflow**.
2. En haut à droite, choisir **Last 15m** et un rafraîchissement automatique.
3. Menu **Display** : cocher **Traffic Animation**, **Security** (cadenas mTLS) et
   **Response Time**.

Le graphe montre :

- `istio-ingressgateway` → `gateway` (point d'entrée) ;
- `gateway` → les quatre services et le `frontend` ;
- les appels REST internes : `workspace-service` → `user-service`, et
  `task-service` / `analytics-service` → `workspace-service` ;
- les connexions TCP vers `postgres` et `rabbitmq`.

Le graphe est vide tant qu'aucune requête n'a été faite : voir la
[section 5](#5-générer-du-trafic).

### Lire Grafana et Jaeger

- **Grafana** : dossier **Istio**, tableaux *Istio Service Dashboard* (débit, erreurs,
  latences par service) et *Istio Mesh Dashboard* (vue globale).
- **Jaeger** : choisir le service `istio-ingressgateway.istio-system` (ou
  `gateway.taskflow`), puis **Find Traces**. Une trace montre le trajet d'une requête :
  ingress Istio, gateway Nginx, puis le microservice. Les appels REST qu'un service fait
  ensuite apparaissent dans des traces séparées, car les services Python ne
  transmettent pas les en-têtes de traçage (`traceparent`).

---

## 5. Générer du trafic

Avec le port-forward de l'application actif (fenêtre 1) :

```bash
python scripts/taskflow.py smoke          # scénario complet : REST et événements RabbitMQ
python scripts/taskflow.py load 300 20    # 300 requêtes, 20 en parallèle
```

`load` affiche le nombre de réponses par code HTTP. Sans règle de démonstration
active, toutes les réponses sont des `200`. On peut aussi simplement utiliser
l'application sur <http://localhost:8080>.

---

## 6. Démonstrations Kubernetes et Istio

Les règles Istio de démonstration sont dans [k8s/istio/](k8s/istio/) :

| Fichier | Rôle |
|---|---|
| `gateway.yaml` | Point d'entrée Istio, toujours appliqué |
| `resilience.yaml` | Timeout de 5 s et retries vers WorkspaceService, appliqué par défaut |
| `tracing.yaml` | Envoi des traces vers Jaeger, appliqué avec les addons |
| `mtls.yaml` | mTLS obligatoire entre les sidecars du namespace |
| `fault-injection.yaml` | Erreurs 503 et délais injectés sur AnalyticsService |
| `circuit-breaker.yaml` | Limite de connexions et éjection des instances défaillantes de WorkspaceService |

### 6.1 Mise à l'échelle

```bash
kubectl -n taskflow scale deployment/task-service --replicas=2
kubectl -n taskflow get pods -l app=task-service
python scripts/taskflow.py load 200 10    # Kiali répartit le trafic sur les deux pods
kubectl -n taskflow scale deployment/task-service --replicas=1
```

Garder une seule réplique en temps normal : les services créent leurs tables au
démarrage (`generate_schemas`).

### 6.2 Auto-réparation

```bash
kubectl -n taskflow delete pod -l app=user-service
kubectl -n taskflow get pods -w           # un nouveau pod remplace l'ancien (Ctrl+C)
```

### 6.3 mTLS strict

```bash
kubectl apply -f k8s/istio/mtls.yaml
python scripts/taskflow.py smoke          # tout fonctionne toujours
```

Dans Kiali, avec **Display > Security**, un cadenas apparaît sur chaque arc entre
sidecars. PostgreSQL et RabbitMQ n'ont pas de sidecar : Istio leur parle en clair,
automatiquement. Pour revenir au mode permissif :
`kubectl delete -f k8s/istio/mtls.yaml`.

### 6.4 Injection de fautes

```bash
kubectl apply -f k8s/istio/fault-injection.yaml
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "%{http_code} " http://localhost:8080/api/analytics/me
done; echo
```

Sur 20 appels, environ la moitié renvoie `503` : c'est Envoy qui répond, sans
jamais contacter AnalyticsService. Les autres renvoient `401`, la réponse normale du
service à une requête sans jeton. Un quart des appels subit aussi un délai de 2 s.
Dans l'application, l'onglet **Statistiques** d'un espace échoue une fois sur deux.
Kiali colore en rouge l'arc `gateway` → `analytics-service`.

Le smoke test, lui, passe malgré tout : il réinterroge AnalyticsService jusqu'à
obtenir une réponse. Pour retirer la règle :

```bash
kubectl delete -f k8s/istio/fault-injection.yaml
```

### 6.5 Circuit breaker

```bash
kubectl apply -f k8s/istio/circuit-breaker.yaml
python scripts/taskflow.py load 200 20
kubectl delete -f k8s/istio/circuit-breaker.yaml
```

Résultat observé, par exemple :

```
200 requests in 6.5s
          200: 52
          502: 94
          503: 54
```

- **503** : Envoy refuse la requête, car la limite d'une connexion vers
  WorkspaceService est atteinte. Le circuit est ouvert.
- **502** : TaskService n'a pas pu joindre WorkspaceService et le signale au client.

Le graphe Kiali montre ces erreurs. Une icône d'éclair signale le circuit breaker sur
`workspace-service`. Relancer `load` après le `delete` : toutes les réponses
redeviennent `200`.

---

## 7. Arrêter, redémarrer, supprimer

**Arrêter sans rien perdre** (déploiement, images, données) :

```bash
minikube stop
```

**Redémarrer** plus tard, sans reconstruire :

```bash
minikube start
kubectl -n taskflow get pods              # attendre que tout soit Running
bash scripts/k8s.sh forward               # puis kiali, grafana, etc. dans d'autres fenêtres
```

**Mettre à jour le code** déployé :

```bash
bash scripts/k8s.sh images
```

**Supprimer TaskFlow**, données comprises, puis arrêter Minikube :

```bash
bash scripts/k8s.sh down
```

**Repartir de zéro** (efface le cluster entier, Istio compris) :

```bash
minikube delete
bash scripts/k8s.sh up
```

Après un `minikube delete`, supprimer aussi `.k8s.env` pour générer de nouveaux
identifiants, ou le garder : les volumes ayant disparu, les deux fonctionnent.

---

## 8. Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| `x509: certificate signed by unknown authority` | Antivirus avec analyse HTTPS | [Voir les prérequis](#antivirus-avec-analyse-https-avast-avg-kaspersky) |
| `minikube start` : `apiserver healthz never reported healthy` | Même cause, ou cluster corrompu | Corriger l'antivirus, puis `minikube delete` et `minikube start` |
| `error during connect … dockerDesktopLinuxEngine` | Docker Desktop arrêté | Lancer Docker Desktop, attendre que `docker info` réponde |
| `istioctl: command not found` | Istio absent du `PATH` | `export PATH="$ISTIO_HOME/bin:$PATH"` |
| Pods `Pending`, `Insufficient memory` ou `cpu` | Cluster trop petit | `minikube delete`, puis `minikube start --cpus=4 --memory=7168` |
| Pod `ErrImageNeverPull` | Image absente de Minikube | `bash scripts/k8s.sh images` |
| Services en `CrashLoopBackOff` | RabbitMQ ou PostgreSQL pas encore prêt | Attendre. Sinon : `kubectl -n taskflow logs deploy/task-service -c task-service` |
| `rabbitmq-0` reste à `0/1` après la modification d'une sonde | Un StatefulSet ne remplace pas un pod qui n'a jamais été prêt | `kubectl -n taskflow delete pod rabbitmq-0` |
| `port-forward` : `address already in use` | Port 8080 pris (stack Compose) | `docker compose stop` |
| Jaeger ne liste que le service `jaeger` | Traçage non activé | `kubectl apply -f k8s/istio/tracing.yaml`, puis générer du trafic |
| Graphe Kiali vide | Pas de trafic récent | `python scripts/taskflow.py smoke`, puis élargir la période à **Last 15m** |
| Kiali n'affiche que `PassthroughCluster` | Ancienne image du gateway (en-tête `Host` incorrect) | `bash scripts/k8s.sh images` |
| Avertissement de version de `kubectl` | Client fourni par Docker Desktop plus ancien que le cluster | Sans incidence ici, ou `minikube kubectl -- <commande>` |

Commandes utiles pour diagnostiquer :

```bash
kubectl -n taskflow get pods
kubectl -n taskflow describe pod <nom-du-pod>          # section Events en bas
kubectl -n taskflow logs <nom-du-pod> -c <conteneur>   # -c istio-proxy pour Envoy
istioctl analyze -n taskflow                           # vérifie la configuration Istio
istioctl proxy-status                                  # synchronisation des sidecars
```

Références : [TP servicemesh](https://github.com/charroux/servicemesh),
[Istio, démarrage](https://istio.io/latest/docs/setup/getting-started/),
[addons Istio](https://istio.io/latest/docs/ops/integrations/),
[chargement d'images dans Minikube](https://minikube.sigs.k8s.io/docs/handbook/pushing/).
