# Serveur Pub/Sub WebSocket en Python

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Un serveur Pub/Sub WebSocket simple, robuste et prêt pour la production, construit avec Flask, Socket.IO et utilisant SQLite pour la persistance des données.

## ✨ Fonctionnalités

- 📢 **Diffusion par Sujets (Topics)** : Publiez des messages dans des canaux spécifiques.
- 📡 **Abonnement en Temps Réel** : Les clients s'abonnent via WebSocket pour recevoir les messages instantanément.
- 💾 **Persistance des Données** : Utilise SQLite pour sauvegarder les messages, les abonnements des clients et les confirmations de consommation.
- 🔌 **Double Interface** : Une API HTTP RESTful pour publier des messages et des points d'accès pour le monitoring, et des événements Socket.IO pour la communication
  temps réel.
- 📊 **Monitoring Intégré** : Points d'accès API pour lister les clients connectés, l'historique des messages et les événements de consommation.
- 📝 **Journalisation Complète** : Logging détaillé pour le débogage et le suivi de l'activité du serveur.
- 🧪 **Suite de Tests Complète** : Tests unitaires et d'intégration utilisant `pytest` pour assurer la fiabilité.

## 📦 Installation

### Depuis les sources

```bash
git clone https://github.com/votre-repo/Python.PubSub.Server.git
cd Python.PubSub.Server

# Il est recommandé d'utiliser un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Sur Windows: .venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

## 🚀 Lancement Rapide

Une fois les dépendances installées, vous pouvez démarrer le serveur :

```bash
python -m python_pubsub_server.pubsub_ws
```

Le serveur démarrera et écoutera sur `http://0.0.0.0:5000`. La première fois, il créera et initialisera une base de données SQLite nommée `pubsub.db`.

Vous pouvez accéder au panneau de contrôle en ouvrant `http://localhost:5000/` dans votre navigateur.

## 📝 Référence de l'API

Le serveur expose à la fois des points d'accès HTTP et des événements WebSocket.

### Points d'accès HTTP

#### `POST /publish`

Publie un message sur un sujet spécifique. Le corps de la requête doit être un JSON.

**Corps JSON :**

```json
{
  "topic": "notifications",
  "message_id": "msg-unique-001",
  "message": {
    "type": "alert",
    "content": "Maintenance système à 22h."
  },
  "producer": "admin-script"
}
```

- **Succès (200)** : `{"status": "ok"}`
- **Erreur (400)** : `{"status": "error", "message": "Missing required field"}`

#### `GET /clients`

Retourne la liste de tous les abonnements de clients actuellement actifs.

**Réponse :**

```json
[
  {
    "consumer": "dashboard-ui",
    "topic": "metrics",
    "connected_at": 1678886400.123
  }
]
```

#### `GET /messages`

Retourne la liste de tous les messages qui ont été publiés, triés par ordre antéchronologique.

**Réponse :**

```json
[
  {
    "topic": "notifications",
    "message_id": "msg-unique-001",
    "message": {
      "type": "alert",
      "content": "Maintenance système à 22h."
    },
    "producer": "admin-script",
    "timestamp": 1678886500.456
  }
]
```

#### `GET /consumptions`

Retourne la liste de tous les événements de consommation enregistrés.

**Réponse :**

```json
[
  {
    "consumer": "mobile-app-user-123",
    "topic": "notifications",
    "message_id": "msg-unique-001",
    "message": "{'type': 'alert', 'content': 'Maintenance système à 22h.'}",
    "timestamp": 1678886505.789
  }
]
```

### Événements WebSocket

Les clients communiquent avec le serveur via un client Socket.IO.

#### Émettre `subscribe`

Un client s'abonne à un ou plusieurs sujets.

```javascript
// Exemple côté client
socket.emit('subscribe', {
  consumer: 'mobile-app-user-123',
  topics: ['notifications', 'private-messages']
});
```

#### Recevoir `message`

Le serveur envoie cet événement aux clients abonnés lorsqu'un nouveau message est publié sur un sujet correspondant.

```javascript
// Exemple côté client
socket.on('message', (data) => {
  console.log(`Nouveau message sur le sujet ${data.topic}:`, data.message);

  // Le client peut ensuite notifier le serveur de la consommation
  socket.emit('consumed', {
    consumer: 'mobile-app-user-123',
    topic: data.topic,
    message_id: data.message_id,
    message: data.message
  });
});
```

#### Émettre `consumed`

Un client notifie le serveur qu'il a bien reçu et traité un message.

#### Événement `disconnect`

Géré automatiquement lorsque le client se déconnecte. Le serveur supprime l'abonnement du client de la base de données.

## 🛠️ Développement

### Prérequis

- Python 3.9 ou supérieur
- pip et virtualenv

### Environnement de développement

Suivez les mêmes étapes que pour l'installation, mais installez les dépendances de développement si un fichier `requirements-dev.txt` est disponible.

```bash
# Cloner le dépôt
git clone https://github.com/votre-repo/Python.PubSub.Server.git
cd Python.PubSub.Server

# Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
# pip install -r requirements-dev.txt # Si applicable
```

### Lancer les tests

Le projet utilise `pytest` pour les tests. Assurez-vous d'installer `pytest` et les autres dépendances de test.

```bash
# Lancer tous les tests
pytest -v
```

## 📁 Structure du Projet

```
Python.PubSub.Server/
├── src/
│   └── python_pubsub_server/    # Package principal
│       ├── pubsub_ws.py         # Implémentation du serveur
│       ├── *.html               # Interfaces web (control-panel, network-graph, etc.)
│       └── static/              # Fichiers statiques (CSS, JS)
├── migrations/
│   └── 001_...sql               # Scripts de migration de la base de données
├── tests/                       # Suite de tests
│   ├── test_pubsub_ws.py
│   └── ...
├── requirements.txt             # Dépendances du projet
└── README.md                    # Ce fichier
```

## 🤝 Contribution

Les contributions sont les bienvenues \! Veuillez suivre ces étapes :

1. Forkez le dépôt
2. Créez une branche pour votre fonctionnalité (`git checkout -b feature/nouvelle-feature`)
3. Commitez vos changements (`git commit -m 'Ajout de ma nouvelle feature'`)
4. Poussez vers la branche (`git push origin feature/nouvelle-feature`)
5. Ouvrez une Pull Request

Veuillez vous assurer que tous les tests passent et que la documentation est mise à jour si nécessaire.

## 📄 Licence

Ce projet est sous licence MIT - voir le fichier `LICENSE` pour plus de détails.

## 📧 Contact

- Auteur : venantvr
- Email : venantvr@gmail.com
- GitHub : [@venantvr](https://github.com/venantvr)