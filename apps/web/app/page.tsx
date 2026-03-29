"use client";

import { useEffect, useState } from "react";

type ConnectionStatus = "online" | "offline" | "simulated";

type RabbitSummary = {
  id: string;
  slug: string;
  name: string;
  connection_status: ConnectionStatus;
  updated_at: string;
};

type RabbitState = {
  left_ear: number;
  right_ear: number;
  led_nose: string;
  led_left: string;
  led_center: string;
  led_right: string;
  led_bottom: string;
  audio_playing: boolean;
  recording: boolean;
  last_audio_url: string | null;
  last_recording_id: string | null;
};

type Rabbit = RabbitSummary & {
  created_at: string;
  state: RabbitState;
  target: {
    host: string;
    port: number;
  } | null;
};

type EventItem = {
  id: string;
  type: string;
  message: string;
  created_at: string;
  payload: Record<string, unknown>;
};

type DiscoveryProbeResult = {
  reachable: boolean;
  host: string;
  port: number;
  state: string | null;
  connection_status: ConnectionStatus | null;
  packet: Record<string, unknown>;
  message: string;
};

type BootstrapConfigResult = {
  submitted: boolean;
  bootstrap_url: string;
  violet_platform: string;
  message: string;
  next_steps: string[];
};

type PairingStep = {
  key: string;
  title: string;
  done: boolean;
  active: boolean;
};

type WizardMode = "bootstrap" | "configured";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const connectionSteps = [
  {
    title: "Préparer le lapin ou le serveur Pynab",
    description:
      "Le daemon `nabd` doit être actif sur le lapin ou sur la machine qui l'héberge, avec le port TCP 10543 accessible depuis cette application.",
    checks: [
      "Repérer l'IP ou le nom DNS de la machine qui exécute `nabd`.",
      "Vérifier que `nabd` écoute bien sur le port `10543`.",
      "S'assurer que le firewall autorise la connexion depuis la machine qui lance l'API.",
    ],
  },
  {
    title: "Configurer l'API en mode protocole",
    description:
      "L'API doit être démarrée avec le driver `protocol`, sinon l'interface restera sur le simulateur et ne parlera pas au vrai lapin.",
    checks: [
      "Copier `apps/api/.env.example` vers `apps/api/.env`.",
      "Définir `NABAZTAG_GATEWAY_DRIVER=protocol`.",
      "Le host et le port globaux servent de cible par défaut et de base pour certains tests.",
      "La cible réseau réelle peut ensuite être enregistrée lapin par lapin depuis l'assistant.",
    ],
    code: `NABAZTAG_GATEWAY_DRIVER=protocol
NABAZTAG_GATEWAY_HOST=192.168.1.25
NABAZTAG_GATEWAY_PORT=10543`,
  },
  {
    title: "Démarrer les services",
    description:
      "Le frontend parle à l'API FastAPI. Le backend ouvre ensuite une socket TCP courte vers `nabd` pour chaque action.",
    checks: [
      "Créer l'environnement Python si nécessaire.",
      "Installer les dépendances backend.",
      "Lancer FastAPI sur `http://localhost:8000`.",
      "Installer puis lancer le frontend Next.js sur `http://localhost:3000`.",
    ],
    code: `python3 -m venv .venv
source .venv/bin/activate
pip install -e ./apps/api
uvicorn app.main:app --reload --app-dir apps/api

npm install
npm run dev:web`,
  },
  {
    title: "Valider la connexion dans l'interface",
    description:
      "Commencer par une séquence courte : connexion, synchronisation, oreilles, audio, puis LED sur une zone supportée.",
    checks: [
      "Créer un lapin dans la colonne de gauche.",
      "Choisir `Device` dans la carte Gateway puis cliquer sur `Connecter`.",
      "Cliquer sur `Sync` pour relire l'état initial envoyé par `nabd`.",
      "Tester d'abord `Oreilles`, puis `Audio`, puis LED `left`, `center` ou `right`.",
    ],
  },
  {
    title: "Lire les erreurs utiles",
    description:
      "Certaines primitives du MVP ne sont pas entièrement couvertes par la doc `nabd`. L'assistant les signale pour éviter les faux diagnostics.",
    checks: [
      "`nose` et `bottom` ne sont pas encore supportés en mode protocole.",
      "L'enregistrement micro brut n'est pas documenté comme primitive `start/stop recording` dans `nabd`.",
      "Une erreur `501` indique en général une capacité non encore implémentée, pas forcément un problème réseau.",
    ],
  },
] as const;

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "API error");
  }

  return response.json() as Promise<T>;
}

export default function HomePage() {
  const [rabbits, setRabbits] = useState<RabbitSummary[]>([]);
  const [selectedRabbitId, setSelectedRabbitId] = useState<string | null>(null);
  const [rabbit, setRabbit] = useState<Rabbit | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [ledTarget, setLedTarget] = useState("all");
  const [ledColor, setLedColor] = useState("#ff6a3d");
  const [leftEar, setLeftEar] = useState(8);
  const [rightEar, setRightEar] = useState(8);
  const [audioUrl, setAudioUrl] = useState("https://example.com/demo.mp3");
  const [recordDuration, setRecordDuration] = useState(10);
  const [connectMode, setConnectMode] = useState<"simulated" | "device">("simulated");
  const [wizardOpen, setWizardOpen] = useState(true);
  const [wizardMode, setWizardMode] = useState<WizardMode>("bootstrap");
  const [discoveryHost, setDiscoveryHost] = useState("192.168.1.25");
  const [discoveryPort, setDiscoveryPort] = useState(10543);
  const [discoveryStatus, setDiscoveryStatus] = useState<"idle" | "probing" | "success" | "error">("idle");
  const [discoveryResult, setDiscoveryResult] = useState<DiscoveryProbeResult | null>(null);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<{ host: string; port: number } | null>(null);

  const [newRabbitName, setNewRabbitName] = useState("");
  const [newRabbitSlug, setNewRabbitSlug] = useState("");
  const [bootstrapHomeSsid, setBootstrapHomeSsid] = useState("");
  const [bootstrapHomePassword, setBootstrapHomePassword] = useState("");
  const [bootstrapServerUrl, setBootstrapServerUrl] = useState("https://rabbit-api.example.com");
  const [bootstrapStatus, setBootstrapStatus] = useState<"idle" | "submitting" | "ready" | "error">("idle");
  const [bootstrapResult, setBootstrapResult] = useState<BootstrapConfigResult | null>(null);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  async function refreshRabbits() {
    const list = await api<RabbitSummary[]>("/api/rabbits");
    setRabbits(list);
    if (!selectedRabbitId && list[0]) {
      setSelectedRabbitId(list[0].id);
    }
  }

  async function refreshRabbit(rabbitId: string) {
    const [rabbitData, eventData] = await Promise.all([
      api<Rabbit>(`/api/rabbits/${rabbitId}`),
      api<EventItem[]>(`/api/rabbits/${rabbitId}/events`),
    ]);
    setRabbit(rabbitData);
    setEvents(eventData);
    setLeftEar(rabbitData.state.left_ear);
    setRightEar(rabbitData.state.right_ear);
  }

  useEffect(() => {
    void refreshRabbits().catch((cause: Error) => setError(cause.message));
  }, []);

  useEffect(() => {
    if (!selectedRabbitId) {
      return;
    }
    void refreshRabbit(selectedRabbitId).catch((cause: Error) => setError(cause.message));
  }, [selectedRabbitId]);

  useEffect(() => {
    if (rabbit?.target) {
      setSelectedTarget(rabbit.target);
    }
  }, [rabbit]);

  async function runCommand(path: string, payload: Record<string, unknown>) {
    if (!selectedRabbitId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api(`/api/rabbits/${selectedRabbitId}${path}`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await refreshRabbit(selectedRabbitId);
      await refreshRabbits();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function createRabbit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api<Rabbit>("/api/rabbits", {
        method: "POST",
        body: JSON.stringify({
          name: newRabbitName,
          slug: newRabbitSlug,
        }),
      });
      setNewRabbitName("");
      setNewRabbitSlug("");
      await refreshRabbits();
      setSelectedRabbitId(created.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function assignTargetToRabbit(target: { host: string; port: number }) {
    if (!selectedRabbitId) {
      setDiscoveryError("Crée ou sélectionne d'abord un lapin avant d'enregistrer une cible.");
      return;
    }
    setBusy(true);
    setDiscoveryError(null);
    try {
      const updated = await api<Rabbit>(`/api/rabbits/${selectedRabbitId}/target`, {
        method: "PUT",
        body: JSON.stringify(target),
      });
      setSelectedTarget(target);
      setRabbit(updated);
      await refreshRabbits();
    } catch (cause) {
      setDiscoveryError(cause instanceof Error ? cause.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function prepareBootstrapConfig() {
    setBootstrapStatus("submitting");
    setBootstrapResult(null);
    setBootstrapError(null);
    try {
      const result = await api<BootstrapConfigResult>("/api/bootstrap/submit", {
        method: "POST",
        body: JSON.stringify({
          rabbit_id: selectedRabbitId,
          bootstrap_host: "192.168.0.1",
          bootstrap_port: 80,
          rabbit_setup_ssid: "NabaztagXX",
          home_wifi_ssid: bootstrapHomeSsid,
          home_wifi_password: bootstrapHomePassword,
          server_base_url: bootstrapServerUrl,
        }),
      });
      setBootstrapResult(result);
      setBootstrapStatus("ready");
    } catch (cause) {
      setBootstrapStatus("error");
      setBootstrapError(cause instanceof Error ? cause.message : "Unknown error");
    }
  }

  async function probeRabbit() {
    setDiscoveryStatus("probing");
    setDiscoveryError(null);
    setDiscoveryResult(null);
    try {
      const result = await api<DiscoveryProbeResult>("/api/discovery/probe", {
        method: "POST",
        body: JSON.stringify({
          host: discoveryHost,
          port: discoveryPort,
          timeout_seconds: 3,
        }),
      });
      setDiscoveryResult(result);
      setDiscoveryStatus(result.reachable ? "success" : "error");
      if (!result.reachable) {
        setDiscoveryError(result.message);
      }
    } catch (cause) {
      setDiscoveryStatus("error");
      setDiscoveryError(cause instanceof Error ? cause.message : "Unknown error");
    }
  }

  const pairingSteps: PairingStep[] = [
    {
      key: "power",
      title: "Lapin sous tension et démarré",
      done: discoveryStatus !== "idle",
      active: discoveryStatus === "idle",
    },
    {
      key: "probe",
      title: "Détection réseau réussie",
      done: discoveryStatus === "success",
      active: discoveryStatus === "probing" || discoveryStatus === "error",
    },
    {
      key: "target",
      title: "Cible retenue pour l'appairage",
      done: (rabbit?.target ?? selectedTarget) !== null,
      active: discoveryStatus === "success" && (rabbit?.target ?? selectedTarget) === null,
    },
    {
      key: "connect",
      title: "Connexion device depuis la carte Gateway",
      done: rabbit?.connection_status === "online",
      active: selectedTarget !== null && rabbit?.connection_status !== "online",
    },
  ];

  const bootstrapSteps = [
    {
      title: "Passer le lapin en mode configuration",
      body: "Débranche le lapin, puis rebranche-le en gardant le bouton appuyé. Attends qu'il s'allume en bleu et qu'il émette son propre Wi-Fi, par exemple `Nabaztag8E`.",
    },
    {
      title: "Rejoindre le Wi-Fi du lapin",
      body: "Depuis ton ordinateur ou ton téléphone, quitte ton Wi-Fi habituel et connecte-toi au réseau émis par le lapin. Reviens ensuite sur cette page.",
    },
    {
      title: "Préparer les paramètres à injecter",
      body: "Saisis le nom du Wi-Fi maison, son mot de passe et l'adresse de notre serveur. Ces paramètres seront ensuite envoyés au lapin quand on aura retrouvé le protocole exact du mode provisioning.",
    },
    {
      title: "Attendre la première connexion serveur",
      body: "Une fois la configuration appliquée, le lapin redémarrera sur le Wi-Fi local puis contactera ton backend. C'est à ce moment-là qu'on pourra finaliser son enrôlement applicatif.",
    },
  ] as const;

  return (
    <main className="page">
      <section className="hero">
        <h1>Primitive-First Nabaztag Control</h1>
        <p>
          Cette première interface valide le pilotage du lapin avant toute couche
          conversationnelle. On contrôle LEDs, oreilles, audio et enregistrement depuis une UI
          unique.
        </p>
      </section>

      <section className="panel wizard-panel">
        <div className="panel-inner">
          <div className="wizard-header">
            <div>
              <h2 className="section-title">Assistant de connexion Nabaztag</h2>
              <p className="wizard-intro">
                Deux parcours sont maintenant distingués: premier paramétrage via le Wi-Fi du
                lapin, ou connexion d'un lapin déjà configuré et joignable sur le réseau.
              </p>
            </div>
            <button
              type="button"
              className="button secondary"
              onClick={() => setWizardOpen((open) => !open)}
            >
              {wizardOpen ? "Masquer" : "Afficher"}
            </button>
          </div>

          {wizardOpen ? (
            <>
              <div className="wizard-mode-switch">
                <button
                  type="button"
                  className="mode-pill"
                  data-selected={wizardMode === "bootstrap"}
                  onClick={() => setWizardMode("bootstrap")}
                >
                  Premier paramétrage
                </button>
                <button
                  type="button"
                  className="mode-pill"
                  data-selected={wizardMode === "configured"}
                  onClick={() => setWizardMode("configured")}
                >
                  Lapin déjà configuré
                </button>
              </div>

              {wizardMode === "bootstrap" ? (
                <div className="wizard-detect">
                  <div className="wizard-detect-copy">
                    <h3 className="section-title">Premier paramétrage</h3>
                    <p className="wizard-copy">
                      Ce parcours correspond au mode historique de configuration: le lapin émet
                      son propre Wi-Fi, l'utilisateur s'y connecte, puis on lui injecte le Wi-Fi
                      maison et l'adresse de notre serveur.
                    </p>
                    <div className="wizard-progress">
                      {bootstrapSteps.map((step, index) => (
                        <div
                          className="wizard-progress-item"
                          key={step.title}
                          data-done="false"
                          data-active={index === 0}
                        >
                          <span className="wizard-progress-bullet" />
                          <span>{step.title}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="wizard-detect-form">
                    <div className="field">
                      <label htmlFor="bootstrap-ssid">Wi-Fi maison</label>
                      <input
                        id="bootstrap-ssid"
                        value={bootstrapHomeSsid}
                        onChange={(event) => setBootstrapHomeSsid(event.target.value)}
                        placeholder="Maison-5G"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="bootstrap-password">Mot de passe Wi-Fi</label>
                      <input
                        id="bootstrap-password"
                        type="password"
                        value={bootstrapHomePassword}
                        onChange={(event) => setBootstrapHomePassword(event.target.value)}
                        placeholder="••••••••"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="bootstrap-server-url">Adresse du serveur Nabaztag</label>
                      <input
                        id="bootstrap-server-url"
                        value={bootstrapServerUrl}
                        onChange={(event) => setBootstrapServerUrl(event.target.value)}
                        placeholder="https://rabbit-api.example.com"
                      />
                    </div>
                    <div className="actions">
                      <button
                        type="button"
                        className="button"
                        disabled={
                          bootstrapStatus === "submitting" ||
                          !bootstrapHomeSsid ||
                          !bootstrapHomePassword ||
                          !bootstrapServerUrl
                        }
                        onClick={() => void prepareBootstrapConfig()}
                      >
                        {bootstrapStatus === "submitting"
                          ? "Préparation en cours..."
                          : "Préparer le paramétrage"}
                      </button>
                    </div>
                    <div className="wizard-status" data-status={bootstrapStatus === "error" ? "error" : bootstrapStatus === "ready" ? "success" : "idle"}>
                      {bootstrapStatus === "idle"
                        ? "Prépare les valeurs qui devront être injectées dans le lapin via son interface locale `http://192.168.0.1/`."
                        : null}
                      {bootstrapStatus === "submitting"
                        ? "Construction du plan de paramétrage en cours..."
                        : null}
                      {bootstrapStatus === "ready" && bootstrapResult ? bootstrapResult.message : null}
                      {bootstrapStatus === "error" ? bootstrapError ?? "Préparation impossible." : null}
                    </div>
                    {bootstrapResult ? (
                      <div className="wizard-probe-result">
                        <strong>Valeurs à injecter</strong>
                        <div className="wizard-stack">
                          <div>
                            <div className="event-meta">Interface locale du lapin</div>
                            <div className="mono">{bootstrapResult.bootstrap_url}</div>
                          </div>
                          <div>
                            <div className="event-meta">Champ Violet Platform</div>
                            <div className="mono">{bootstrapResult.violet_platform}</div>
                          </div>
                          <div>
                            <div className="event-meta">Étapes suivantes</div>
                            <ul className="wizard-list">
                              {bootstrapResult.next_steps.map((step) => (
                                <li key={step}>{step}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </div>
                    ) : null}
                    <div className="wizard-probe-result">
                      <strong>Étapes prévues</strong>
                      <div className="wizard-stack">
                        {bootstrapSteps.map((step, index) => (
                          <div key={step.title}>
                            <strong>0{index + 1}. {step.title}</strong>
                            <div className="wizard-copy" style={{ marginTop: 6 }}>
                              {step.body}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="wizard-detect">
                  <div className="wizard-detect-copy">
                    <h3 className="section-title">Lapin déjà configuré</h3>
                    <p className="wizard-copy">
                      Ce parcours suppose que le lapin ou le serveur `pynab` est déjà joignable
                      sur le réseau local. On détecte `nabd`, on enregistre la cible, puis on lance
                      la connexion depuis l'interface.
                    </p>
                    <ul className="wizard-list">
                      <li>Manipulation à faire: brancher le lapin et attendre qu’il soit totalement démarré.</li>
                      <li>Recherche en cours: l’API tente une connexion TCP puis lit le paquet `state` initial.</li>
                      <li>Détection réussie: on récupère l’état courant du daemon et on peut ensuite lancer `Connecter`.</li>
                    </ul>
                    <div className="wizard-progress">
                      {pairingSteps.map((step) => (
                        <div
                          className="wizard-progress-item"
                          key={step.key}
                          data-done={step.done}
                          data-active={step.active}
                        >
                          <span className="wizard-progress-bullet" />
                          <span>{step.title}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="wizard-detect-form">
                    <div className="field">
                      <label htmlFor="discovery-host">Hôte du Nabaztag ou du serveur Pynab</label>
                      <input
                        id="discovery-host"
                        value={discoveryHost}
                        onChange={(event) => setDiscoveryHost(event.target.value)}
                        placeholder="192.168.1.25"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="discovery-port">Port</label>
                      <input
                        id="discovery-port"
                        type="number"
                        value={discoveryPort}
                        onChange={(event) => setDiscoveryPort(Number(event.target.value))}
                      />
                    </div>
                    <div className="actions">
                      <button
                        type="button"
                        className="button"
                        disabled={discoveryStatus === "probing"}
                        onClick={() => void probeRabbit()}
                      >
                        {discoveryStatus === "probing" ? "Recherche en cours..." : "Détecter"}
                      </button>
                    </div>

                    <div className="wizard-status" data-status={discoveryStatus}>
                      {discoveryStatus === "idle" ? "En attente d’une détection." : null}
                      {discoveryStatus === "probing" ? "Recherche en cours vers le daemon nabd..." : null}
                      {discoveryStatus === "success" && discoveryResult
                        ? `Nabaztag détecté sur ${discoveryResult.host}:${discoveryResult.port} avec état initial ${discoveryResult.state ?? "unknown"}.`
                        : null}
                      {discoveryStatus === "error"
                        ? discoveryError ?? "Détection échouée."
                        : null}
                    </div>

                    {discoveryResult?.reachable ? (
                      <div className="wizard-probe-result">
                        <strong>Paquet initial reçu</strong>
                        <div className="mono">
                          {JSON.stringify(discoveryResult.packet)}
                        </div>
                        <div className="actions" style={{ marginTop: 12 }}>
                          <button
                            type="button"
                            className="button"
                            disabled={busy}
                            onClick={() =>
                              void assignTargetToRabbit({
                                host: discoveryResult.host,
                                port: discoveryResult.port,
                              })
                            }
                          >
                            Utiliser cette cible pour le lapin sélectionné
                          </button>
                        </div>
                      </div>
                    ) : null}

                    {rabbit?.target ?? selectedTarget ? (
                      <div className="wizard-probe-result">
                        <strong>Cible retenue</strong>
                        <div className="mono">
                          {(rabbit?.target ?? selectedTarget)?.host}:{(rabbit?.target ?? selectedTarget)?.port}
                        </div>
                        <p className="wizard-copy" style={{ marginTop: 10 }}>
                          Étape suivante: choisir `Device` dans la carte Gateway, puis cliquer sur
                          `Connecter`. Les appels protocole utiliseront directement cette cible.
                        </p>
                      </div>
                    ) : null}
                  </div>
                </div>
              )}

              <div className="wizard-grid">
                {connectionSteps.map((step, index) => (
                  <article className="wizard-step" key={step.title}>
                    <div className="wizard-step-index">0{index + 1}</div>
                    <div>
                      <h3 className="section-title">{step.title}</h3>
                      <p className="wizard-copy">{step.description}</p>
                      <ul className="wizard-list">
                        {step.checks.map((check) => (
                          <li key={check}>{check}</li>
                        ))}
                      </ul>
                      {step.code ? <pre className="code-block">{step.code}</pre> : null}
                    </div>
                  </article>
                ))}
              </div>
            </>
          ) : null}
        </div>
      </section>

      <section className="shell">
        <aside className="panel">
          <div className="panel-inner">
            <h2 className="section-title">Lapins</h2>
            <div className="rabbit-list">
              {rabbits.map((item) => (
                <button
                  type="button"
                  className="rabbit-item"
                  key={item.id}
                  data-selected={item.id === selectedRabbitId}
                  onClick={() => setSelectedRabbitId(item.id)}
                >
                  <strong>{item.name}</strong>
                  <div className="event-meta">{item.slug}</div>
                  <div className="status-pill" style={{ marginTop: 10 }}>
                    <span className="status-dot" data-status={item.connection_status} />
                    {item.connection_status}
                  </div>
                </button>
              ))}
            </div>

            <form className="create-form" onSubmit={createRabbit}>
              <h3 className="section-title">Enregistrer un lapin</h3>
              <div className="field">
                <label htmlFor="rabbit-name">Nom</label>
                <input
                  id="rabbit-name"
                  value={newRabbitName}
                  onChange={(event) => setNewRabbitName(event.target.value)}
                  placeholder="Lapin salon"
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="rabbit-slug">Slug</label>
                <input
                  id="rabbit-slug"
                  value={newRabbitSlug}
                  onChange={(event) => setNewRabbitSlug(event.target.value)}
                  placeholder="lapin-salon"
                  required
                />
              </div>
              <button className="button" type="submit" disabled={busy}>
                Ajouter
              </button>
            </form>
          </div>
        </aside>

        <div className="grid">
          <section className="panel">
            <div className="panel-inner">
              <h2 className="section-title">Pilotage</h2>
              {rabbit ? (
                <>
                  <div className="status-pill">
                    <span className="status-dot" data-status={rabbit.connection_status} />
                    {rabbit.name}
                  </div>
                  {rabbit.target ? (
                    <div className="event-meta" style={{ marginTop: 10 }}>
                      Cible active: <span className="mono">{rabbit.target.host}:{rabbit.target.port}</span>
                    </div>
                  ) : null}

                  <div className="grid" style={{ marginTop: 18 }}>
                    <div className="card">
                      <h3 className="section-title">Gateway</h3>
                      <div className="field">
                        <label htmlFor="connect-mode">Mode de connexion</label>
                        <select
                          id="connect-mode"
                          value={connectMode}
                          onChange={(event) =>
                            setConnectMode(event.target.value as "simulated" | "device")
                          }
                        >
                          <option value="simulated">Simulated</option>
                          <option value="device">Device</option>
                        </select>
                      </div>
                      <div className="actions">
                        <button
                          className="button"
                          type="button"
                          disabled={busy}
                          onClick={() => runCommand("/connect", { mode: connectMode })}
                        >
                          Connecter
                        </button>
                        <button
                          className="button secondary"
                          type="button"
                          disabled={busy}
                          onClick={() => runCommand("/sync", {})}
                        >
                          Sync
                        </button>
                        <button
                          className="button secondary"
                          type="button"
                          disabled={busy}
                          onClick={() => runCommand("/disconnect", {})}
                        >
                          Déconnecter
                        </button>
                      </div>
                    </div>

                    <div className="card">
                      <h3 className="section-title">LEDs</h3>
                      <div className="field">
                        <label htmlFor="led-target">Zone</label>
                        <select
                          id="led-target"
                          value={ledTarget}
                          onChange={(event) => setLedTarget(event.target.value)}
                        >
                          <option value="all">Toutes</option>
                          <option value="nose">Nez</option>
                          <option value="left">Gauche</option>
                          <option value="center">Centre</option>
                          <option value="right">Droite</option>
                          <option value="bottom">Bas</option>
                        </select>
                      </div>
                      <div className="field">
                        <label htmlFor="led-color">Couleur</label>
                        <input
                          id="led-color"
                          type="color"
                          value={ledColor}
                          onChange={(event) => setLedColor(event.target.value)}
                        />
                      </div>
                      <button
                        className="button"
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          runCommand("/commands/led", {
                            target: ledTarget,
                            color: ledColor,
                          })
                        }
                      >
                        Appliquer
                      </button>
                    </div>

                    <div className="card">
                      <h3 className="section-title">Oreilles</h3>
                      <div className="field">
                        <label htmlFor="left-ear">Oreille gauche: {leftEar}</label>
                        <input
                          id="left-ear"
                          type="range"
                          min={0}
                          max={16}
                          value={leftEar}
                          onChange={(event) => setLeftEar(Number(event.target.value))}
                        />
                      </div>
                      <div className="field">
                        <label htmlFor="right-ear">Oreille droite: {rightEar}</label>
                        <input
                          id="right-ear"
                          type="range"
                          min={0}
                          max={16}
                          value={rightEar}
                          onChange={(event) => setRightEar(Number(event.target.value))}
                        />
                      </div>
                      <button
                        className="button"
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          runCommand("/commands/ears", {
                            left: leftEar,
                            right: rightEar,
                          })
                        }
                      >
                        Déplacer
                      </button>
                    </div>

                    <div className="card">
                      <h3 className="section-title">Audio sortant</h3>
                      <div className="field">
                        <label htmlFor="audio-url">URL du son</label>
                        <input
                          id="audio-url"
                          value={audioUrl}
                          onChange={(event) => setAudioUrl(event.target.value)}
                        />
                      </div>
                      <button
                        className="button"
                        type="button"
                        disabled={busy}
                        onClick={() => runCommand("/commands/audio", { url: audioUrl })}
                      >
                        Jouer
                      </button>
                    </div>

                    <div className="card">
                      <h3 className="section-title">Enregistrement</h3>
                      <div className="field">
                        <label htmlFor="record-duration">
                          Durée max: {recordDuration} sec
                        </label>
                        <input
                          id="record-duration"
                          type="range"
                          min={1}
                          max={30}
                          value={recordDuration}
                          onChange={(event) => setRecordDuration(Number(event.target.value))}
                        />
                      </div>
                      <div className="actions">
                        <button
                          className="button"
                          type="button"
                          disabled={busy}
                          onClick={() =>
                            runCommand("/commands/recording/start", {
                              max_duration_seconds: recordDuration,
                            })
                          }
                        >
                          Démarrer
                        </button>
                        <button
                          className="button secondary"
                          type="button"
                          disabled={busy}
                          onClick={() =>
                            runCommand("/commands/recording/stop", {
                              reason: "user",
                            })
                          }
                        >
                          Arrêter
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="card" style={{ marginTop: 20 }}>
                    <h3 className="section-title">État courant</h3>
                    <div className="state-grid">
                      <div className="state-tile">
                        <strong>LEDs</strong>
                        <div className="mono">{rabbit.state.led_nose} nose</div>
                        <div className="mono">{rabbit.state.led_left} left</div>
                        <div className="mono">{rabbit.state.led_center} center</div>
                        <div className="mono">{rabbit.state.led_right} right</div>
                        <div className="mono">{rabbit.state.led_bottom} bottom</div>
                      </div>
                      <div className="state-tile">
                        <strong>Position</strong>
                        <div>Oreille gauche: {rabbit.state.left_ear}</div>
                        <div>Oreille droite: {rabbit.state.right_ear}</div>
                        <div>Audio: {rabbit.state.audio_playing ? "playing" : "idle"}</div>
                        <div>Recording: {rabbit.state.recording ? "on" : "off"}</div>
                      </div>
                      <div className="state-tile">
                        <strong>Dernier audio</strong>
                        <div className="mono">{rabbit.state.last_audio_url ?? "none"}</div>
                      </div>
                      <div className="state-tile">
                        <strong>Dernier enregistrement</strong>
                        <div className="mono">{rabbit.state.last_recording_id ?? "none"}</div>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <p>Sélectionne un lapin pour commencer.</p>
              )}

              {error ? (
                <div className="card" style={{ marginTop: 20, borderColor: "#bf6d3a" }}>
                  <strong>Erreur API</strong>
                  <div className="mono" style={{ marginTop: 8 }}>
                    {error}
                  </div>
                </div>
              ) : null}
            </div>
          </section>

          <section className="panel">
            <div className="panel-inner">
              <h2 className="section-title">Journal d’événements</h2>
              <div className="event-log">
                {events.map((event) => (
                  <article className="event-item" key={event.id}>
                    <strong>{event.type}</strong>
                    <div>{event.message}</div>
                    <div className="event-meta">
                      {new Date(event.created_at).toLocaleString("fr-FR")}
                    </div>
                    <div className="mono">{JSON.stringify(event.payload)}</div>
                  </article>
                ))}
                {events.length === 0 ? <p>Aucun événement.</p> : null}
              </div>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
