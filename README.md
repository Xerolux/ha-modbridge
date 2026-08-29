# ModBridge für Home Assistant

![Version](https://img.shields.io/badge/version-v2.0.10.18-blue) ![License](https://img.shields.io/github/license/Xerolux/ha-modbridge.svg?style=flat-square)

**[English version below](#english)**

Home-Assistant-Integration für [ModBridge](https://github.com/Xerolux/modbridge) — den Modbus-TCP-Proxy-Manager. Die Integration verbindet sich mit einem laufenden ModBridge-Server (Docker, systemd, beliebig im Netzwerk) und bringt alle Proxys, Statistiken und Steuerungsfunktionen direkt nach Home Assistant.

> **Version:** v2.0.10.18 — diese Integration wird automatisch mit der Version des Original-ModBridge synchronisiert ([Sync-Workflow](.github/workflows/sync-version.yml)).

---

## ✨ Funktionen

- **Geräte & Entitäten pro Proxy:** Jeder ModBridge-Proxy erscheint als eigenes Gerät mit:
  - **Switch** — Proxy starten/stoppen (erkennt automatisch pausierte Proxys und setzt sie korrekt fort)
  - **Status-Sensor** — `Running` / `Stopped` / `Error`
  - **Sensoren** — Anfragen, Fehler, aktive Verbindungen, Latenz (inkl. P50/P95/P99), Laufzeit
- **Server-Gerät:** Konnektivität, laufende/gesamte Proxys, aktive Verbindungen, Anfragen, Fehler, Laufzeit, Speichernutzung
- **Buttons:** ModBridge-Server neu starten, alle Proxys neu starten
- **Dienste:** `start_proxy`, `stop_proxy`, `restart_proxy`, `pause_proxy`, `resume_proxy`, `start_all`, `stop_all`, `restart_all`, `restart_system`
- **Automatischer Re-Login** bei abgelaufener Session, Re-Auth-Flow bei ungültigen Zugangsdaten
- **Mehrsprachig:** Deutsch & Englisch

## 📋 Voraussetzungen

- Home Assistant ≥ 2024.4
- Ein erreichbarer ModBridge-Server (ab v2.0.x) mit aktivierter WebUI/API (Standard-Port `8080`)
- ModBridge-Benutzerkonto (Standard: `admin` — das Initial-Passwort steht beim ersten ModBridge-Start in dessen Logs)

## 🚀 Installation (HACS)

1. HACS öffnen → **⋯** → **Benutzerdefinierte Repositories**
2. Repository hinzufügen: `https://github.com/Xerolux/ha-modbridge`, Kategorie **Integration**
3. **ModBridge** suchen und herunterladen
4. Home Assistant neu starten

Alternativ manuell: `custom_components/modbridge/` aus diesem Repo nach `<config>/custom_components/modbridge/` kopieren und neu starten.

## ⚙️ Einrichtung

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen → ModBridge**
2. Host, Port, Benutzername und Passwort des ModBridge-Servers eingeben
3. Bei aktiviertem TLS in ModBridge: **HTTPS verwenden** ankreuzen (selbstsignierte Zertifikate: *SSL-Zertifikat überprüfen* abschalten)

Optionen (über *Konfigurieren*): Aktualisierungsintervall (10–3600 s, Standard 30 s).

## 🛠️ Dienste

| Dienst | Beschreibung |
|--------|--------------|
| `modbridge.start_proxy` | Proxy per `proxy_id` oder `proxy_name` starten |
| `modbridge.stop_proxy` | Proxy stoppen |
| `modbridge.restart_proxy` | Proxy neu starten |
| `modbridge.pause_proxy` | Proxy pausieren |
| `modbridge.resume_proxy` | Pausierten Proxy fortsetzen |
| `modbridge.start_all` | Alle Proxys starten |
| `modbridge.stop_all` | Alle Proxys stoppen |
| `modbridge.restart_all` | Alle Proxys neu starten |
| `modbridge.restart_system` | ModBridge-Server-Prozess neu starten |

Beispiel-Automatisierung (Proxy per Name stoppen):

```yaml
action:
  - service: modbridge.stop_proxy
    data:
      proxy_name: "Waermepumpe"
```

## 🔄 Versionssync mit ModBridge

Die Integration trägt **immer die Version des Original-ModBridge**. Ein GitHub-Workflow prüft täglich `version.txt` im Upstream-Repo und erzeugt bei Abweichung automatisch Commit, Tag und Release. Lokal beim Entwickeln:

```bash
python scripts/sync_version.py            # erwartet ../modbridge/version.txt
python scripts/sync_version.py C:/pfad/zum/modbridge
```

## 🐛 Troubleshooting

- **`cannot_connect`**: Host/Port prüfen; TLS-Option muss zur ModBridge-Konfiguration passen.
- **`invalid_auth`**: Zugangsdaten prüfen (Multi-User-Modus: Benutzername + Passwort; Legacy-Modus: nur Passwort, Benutzername wird ignoriert).
- **Entitäten fehlen**: Proxys werden beim ersten Poll angelegt — kurze Zeit warten oder die Integration über *Konfigurieren* neu laden.

## 📄 Lizenz

MIT — siehe [LICENSE](LICENSE).

## ✍️ Autor

- **Xerolux** — [GitHub](https://github.com/Xerolux)

---

# English

Home Assistant integration for [ModBridge](https://github.com/Xerolux/modbridge) — the Modbus TCP proxy manager. Connects to any running ModBridge server and exposes every proxy as a device with a start/stop switch plus status, request, error, connection, latency and uptime sensors. Server-level diagnostics, restart buttons and full service coverage (`start/stop/restart/pause/resume` per proxy, bulk actions, system restart) are included. Sessions are kept alive automatically with re-login and re-auth flows.

**Version:** v2.0.10.18 — kept in lockstep with upstream ModBridge via a daily sync workflow.
