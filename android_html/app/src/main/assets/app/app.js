const I18N = {
de:{
 "nav.devices":"Geräte","nav.manage":"Verwalten","nav.schedule":"Zeitplan","nav.logs":"Protokolle","nav.settings":"Einstellungen",
 /* Geräte */
 "devices.summary":"{total} Geräte · {online} online",
 "devices.empty":"Noch keine Geräte vorhanden. Fügen Sie Geräte im Bereich Verwalten hinzu.",
 "devices.wake":"Aufwecken","devices.shutdown":"Herunterfahren","devices.wake_all":"Alle starten",
 "devices.refresh":"Aktualisieren","devices.viewList":"Zur Listenansicht wechseln","devices.viewGrid":"Zur Kachelansicht wechseln",
 "devices.search":"Suche nach Name, MAC, IP oder Benutzer…",
 "sort.name":"Name","sort.ip":"IP-Adresse","sort.mac":"MAC-Adresse","sort.status":"Status",
 "status.online":"Online","status.offline":"Offline","status.unknown":"Unbekannt",
 "device.me":"(ich)","device.disabled":"Deaktiviert",
 "button.remote_fullscreen":"Remote Vollbild","button.remote_window":"Remote Fenster","button.dashboard":"Dashboard","button.ping":"Ping",
 "shutdown.title":"Herunterfahren bestätigen","shutdown.message":"Wollen Sie das Gerät wirklich herunterfahren?",
 "wakeall.title":"Alle Geräte aktivieren","wakeall.message":"Möchten Sie wirklich alle {count} Geräte aktivieren?",
 "wakeall.done":"Magic Packets erfolgreich an {count} Gerät(e) gesendet.",
 "wol.sent":"Magic Packet an {name} gesendet.","wol.online":"{name} ist online.","wol.fail":"{count} Gerät(e) haben das Paket nicht erhalten.",
 "wol.failone":"Wake-Vorgang für {name} fehlgeschlagen.",
 "ping.ok":"Ping an {ip}: Antwort in {ms} ms","ping.fail":"Ping an {ip}: Ziel nicht erreichbar","ping.diag.none":"{ip}: kein IPv4-DNS-Eintrag – Smartphone-DNS prüfen (Privates DNS aus?)","ping.diag.fail":"{ip}: Port nicht erreichbar –",
 "remote.demo":"{mode}: verbindungsaufbau zu {name} (Demo)",
 "remote.soon":"Remote-Desktop folgt – bitte die Windows App / Microsoft Remote Desktop verwenden.",
 "remote.notinstalled":"Keine Remote-Desktop-App gefunden – bitte die App „Windows App“ (Microsoft Remote Desktop) installieren.",
 "remote.nohost":"Für dieses Gerät ist keine IP-Adresse/Hostname hinterlegt.",
 "remote.pwcopied":"RDP-Passwort in die Zwischenablage kopiert – im Verbindungsfenster einfügen.",
 /* Verwalten */
 "manage.subtitle":"Geräte-Verwaltung & Netzwerk-Scan",
 "manage.sec.devices":"Geräte-Verwaltung","manage.sec.scan":"Netzwerk-Scan",
 "manage.add":"+ Gerät hinzufügen","manage.import":"Importieren","manage.export":"Exportieren",
 "manage.scan.start":"Scan starten","manage.add.btn":"Hinzufügen",
 "manage.scan.initial":'Bitte wählen Sie ein Netzwerk aus und klicken Sie auf "Scannen".',
 "manage.scan.running":"Scanne ausgewählte Netzwerke nach aktiven Geräten",
 "manage.scan.done":"{count} Gerät(e) gefunden",
 "manage.scan.none":"Kein Netzwerk ausgewählt","manage.scan.none.msg":"Bitte wählen Sie mindestens ein Netzwerk zum Scannen aus.",
 "manage.dns":"  |  DNS: {dns}",
 "edit.title":"Bearbeiten","edit.delete":"Löschen",
 "del.title":"Löschung bestätigen","del.message":'Möchten Sie das Gerät "{name}" wirklich löschen?',
 "imp.done":"{count} Gerät(e) importiert.","exp.done":"Export nach {name} ({count} Einträge).",
 "imp.summary":"Import: {added} neu, {updated} aktualisiert, {skipped} übersprungen.","imp.err":"Import fehlgeschlagen: Format nicht lesbar.",
 "scan.known":"bekannt","scan.new":"neu",
 /* Geräte-Dialog */
 "dev.add":"Gerät hinzufügen","dev.edit":"Gerät bearbeiten",
 "dev.name":"Gerätename:","dev.mac":"MAC-Adresse:","dev.ip":"IP-Adresse / Hostname:",
 "dev.user":"Benutzer:","dev.pass":"Passwort:","dev.method":"Herunterfahr-Methode:",
 "dev.watch":"Überwachte Prozesse (Dashboard):",
 "ph.name":"Gerätenamen eingeben","ph.mac":"z.B., AA:BB:CC:DD:EE:FF","ph.ip":"z.B., 192.168.1.100 oder ubuntu-mercury",
 "ph.user":"Benutzername (optional)","ph.pass":"Passwort (optional)","ph.watch":"z.B., llama-server.exe:8080",
 "ph.pass.keep":"Leer lassen = gespeichertes Passwort behalten",
 "dev.added":"Gerät hinzugefügt.",
 "dev.method.host":"Host-Service (empfohlen)","dev.method.smb":"SMB (Windows-Freigabe)",
 "dev.enabled":"Gerät ist aktiviert","dev.save":"Speichern","dev.update":"Aktualisieren","dev.cancel":"Abbrechen",
 "err.name":"Bitte einen Namen eingeben.","err.mac":"Ungültige MAC-Adresse (z. B. AA:BB:CC:DD:EE:FF).",
 "err.ip":"Ungültige IP oder Hostname.",
 "dev.saved":"Gerät gespeichert.","dev.deleted":"Gerät gelöscht.",
 "mac.unknown.title":"Unbekannte MAC-Adresse","mac.unknown.msg":"Gerät {host} ({ip}) hat eine unbekannte MAC-Adresse. Mit Platzhalter fortfahren?",
 "mac.dup.title":"Gerät existiert bereits","mac.dup.msg":"Ein Gerät mit der MAC-Adresse {mac} existiert bereits.",
 /* Zeitplan */
 "sched.subtitle":"Geräte zeitgesteuert ein- oder ausschalten",
 "sched.add":"+ Zeitplan erstellen","sched.search":"Zeitpläne suchen…",
 "sched.empty":"Noch keine Zeitpläne vorhanden. Erstellen Sie Ihren ersten Zeitplan.",
 "sched.wake":"Aufwecken","sched.shutdown":"Herunterfahren",
 "sched.days.every":"Täglich","sched.days.weekdays":"Wochentags",
 "sched.del.title":"Zeitplan löschen","sched.del.message":'Möchten Sie den Zeitplan für "{name}" wirklich löschen?',
 "sched.no_dev.title":"Keine Geräte","sched.no_dev.msg":"Bitte fügen Sie zuerst ein Gerät hinzu, bevor Sie einen Zeitplan erstellen.",
 "sc.add":"Neuer Zeitplan","sc.edit":"Zeitplan bearbeiten",
 "sc.device":"Gerät:","sc.action":"Aktion:","sc.act.wake":"Einschalten","sc.act.shutdown":"Herunterfahren",
 "sc.time":"Zeit:","sc.days":"Wochentage","sc.enabled":"Zeitplan ist aktiviert",
 "sc.no_days.title":"Keine Tage","sc.no_days.msg":"Bitte wählen Sie mindestens einen Wochentag.",
 "sc.unknown":"Unbekanntes Gerät","sc.saved":"Zeitplan gespeichert.",
 "day.Mon":"Mo","day.Tue":"Di","day.Wed":"Mi","day.Thu":"Do","day.Fri":"Fr","day.Sat":"Sa","day.Sun":"So",
 /* Protokolle */
 "logs.subtitle":"Alle Ereignisse der Applikation",
 "logs.search":"Nachricht oder Gerät suchen…","logs.level.all":"Alle Level",
 "logs.export":"CSV exportieren","logs.empty":"Keine Protokolleinträge vorhanden.",
 "logs.exported":"Protokoll exportiert nach {path}","logs.unknown":"Unbekannt",
 /* Einstellungen */
 "set.subtitle":"Applikation & Netzwerk konfigurieren",
 "set.broadcast_ip":"Broadcast-IP","set.broadcast_port":"Broadcast-Port","set.language":"Sprache",
 "set.display":"Anzeigemodus","set.design":"App-Design","set.design.hint":"Eine Änderung des Designs erfordert einen Neustart der App.",
 "set.auto_update":"Automatisch nach Updates suchen","set.interval":"Prüfintervall",
 "set.max_logs":"Maximale Protokolleinträge","set.resolution":"Auflösung","set.method":"Standard-Methode für neue Geräte",
 "disp.auto":"Auto","disp.light":"Hell","disp.dark":"Dunkel",
 "design.classic":"Klassische App","design.modern":"Moderne App",
 "int.day":"Jeden Tag","int.week":"Jede Woche","int.month":"Jeden Monat",
 "res.opt":"Optimiert 16:9",
 "set.info":"Wake-on-LAN funktioniert durch das Senden eines speziellen 'Magic Packet' an die MAC-Adresse des Zielgeräts im lokalen Netzwerk. Dazu muss das Gerät Wake-on-LAN unterstützen und es im BIOS/UEFI und in den Systemeinstellungen aktivieren.",
 "set.reset":"Zurücksetzen","set.save":"Speichern",
 "set.saved.title":"Einstellungen gespeichert","set.saved.msg":"Einstellungen erfolgreich gespeichert.",
 "set.reset.title":"Werkseinstellungen wiederherstellen",
 "set.reset.msg":"Möchten Sie alle Einstellungen auf die Werkseinstellungen zurücksetzen?\n\nGeräte, Zeitpläne und Protokolle bleiben erhalten.",
 "err.ip_missing":"IP-Adresse fehlt","err.ip_title":"Ungültige IP-Adresse",
 "err.ip_msg":"Das IP-Adressformat ist ungültig. Verwenden Sie x.x.x.x (z. B. 192.168).",
 "err.port_title":"Ungültiger Port","err.port_msg":"Die Portnummer muss zwischen 1 und 65535 liegen.",
 /* Info (unten in Einstellungen) */
 "about.name":"Wake-on-LAN Manager","about.version":"Version: {v}",
 "about.desc":"Ein leistungsstärkes Tool zur Verwaltung von Geräten in Ihrem Netzwerk via Wake-on-LAN-Technologie.",
 "upd.check":"🔄 Nach Updates suchen","upd.changelog":"Changelog",
 "upd.checking":"Es wird nach Updates gesucht…","upd.ok":"✅ Sie verwenden die aktuellste Version.",
 "upd.err":"⚠️ {msg}","upd.err.msg":"Die Aktualitätsprüfung konnte nicht durchgeführt werden.",
 "upd.new":"🆕 Neue Version {v} verfügbar!",
 /* Dashboard */
 "dash.back":"← Geräte","dash.interval":"Intervall",
 "dash.swipe":"Wischen nach links/rechts wechselt zum nächsten Gerät.",
 "dash.svc":"Dienste","dash.svc.sub":"Überwachte Prozesse","dash.svc.none":"Keine überwachten Prozesse konfiguriert.",
 "svc.running":"läuft · PID {pid}","svc.ready":"läuft · PID {pid} · API bereit :{port}","svc.unreach":"läuft (PID {pid}), aber Port {port} nicht erreichbar","svc.gone":"Prozess nicht gefunden",
 "svc.probing":"wird geprüft…",
 "dash.inferenz":"⚡ Inferenz aktiv","dash.model":"🧠 {m}",
 "m.cpu":"CPU-AUSLASTUNG","m.ram":"RAM-NUTZUNG","m.gpu":"GPU-AUSLASTUNG","m.vram":"VRAM-NUTZUNG",
 "d.cores":"{n} Kerne","d.gb":"{used} / {total} GB","d.uptime":"Uptime {v}","d.na":"k/A",
 "hostv":"Host Service v{v}",
 "batch.title":"Batches","batch.new":"Neu","batch.dup":"Duplizieren","batch.del":"Löschen",
 "batch.run":"Ausführen","batch.save":"Speichern","batch.clear":"Leeren","batch.out":"Ausgabe",
 "batch.timeout":"Timeout (s)","batch.allow":"Batches auf diesem Gerät erlauben",
 "batch.newname":"Neuer Batch","batch.running":"Batch läuft…","batch.exit":"Exit-Code: {c}","batch.dur":"Dauer: {s} s",
 "batch.empty":"Noch keine Batches. „Neu\" erstellt einen neuen Batch.",
 "batch.disabled":"Ausführung deaktiviert: „Batches erlauben\" aktivieren und den Host freigeben (WOL Host Service.exe --enable-batch).",
 "dash.creds":"Für dieses Gerät sind keine Benutzerdaten hinterlegt. Dashboard-Metriken benötigen die Host-Service-Anmeldung.",
 "dash.unreach":"Host Service nicht erreichbar ({ip}:8765). Läuft der Dienst?",
 "dash.err":"Host-Service-Fehler: {msg}",
 "batch.exit.short":"Exit-Code {c}","batch.save.first":"Bitte zuerst den Batch speichern.",
 "yes":"Ja","no":"Nein","ok":"OK"
},
en:{
 "nav.devices":"Devices","nav.manage":"Manage","nav.schedule":"Schedule","nav.logs":"Logs","nav.settings":"Settings",
 "devices.summary":"{total} devices · {online} online",
 "devices.empty":"No devices yet. Add devices in the Manage area.",
 "devices.wake":"Wake","devices.shutdown":"Shut down","devices.wake_all":"Start all",
 "devices.refresh":"Refresh","devices.viewList":"Switch to list view","devices.viewGrid":"Switch to grid view",
 "devices.search":"Search by name, MAC, IP or user…",
 "sort.name":"Name","sort.ip":"IP address","sort.mac":"MAC address","sort.status":"Status",
 "status.online":"Online","status.offline":"Offline","status.unknown":"Unknown",
 "device.me":"(me)","device.disabled":"Disabled",
 "button.remote_fullscreen":"Remote fullscreen","button.remote_window":"Remote window","button.dashboard":"Dashboard","button.ping":"Ping",
 "shutdown.title":"Confirm shutdown","shutdown.message":"Do you really want to shut down the device?",
 "wakeall.title":"Wake all devices","wakeall.message":"Do you really want to wake all {count} devices?",
 "wakeall.done":"Magic packets successfully sent to {count} device(s).",
 "wol.sent":"Magic packet sent to {name}.","wol.online":"{name} is online.","wol.fail":"{count} device(s) did not receive the packet.",
 "wol.failone":"Wake failed for {name}.",
 "ping.ok":"Ping to {ip}: reply in {ms} ms","ping.fail":"Ping to {ip}: destination unreachable","ping.diag.none":"{ip}: no IPv4 DNS entry – check the phone's DNS (Private DNS off?)","ping.diag.fail":"{ip}: port unreachable –",
 "remote.demo":"{mode}: connecting to {name} (demo)",
 "remote.soon":"Remote desktop coming soon – please use the Windows App / Microsoft Remote Desktop.",
 "remote.notinstalled":"No remote desktop app found – please install the “Windows App” (Microsoft Remote Desktop).",
 "remote.nohost":"This device has no IP address/hostname configured.",
 "remote.pwcopied":"RDP password copied to the clipboard – paste it in the connect window.",
 "manage.subtitle":"Device management & network scan",
 "manage.sec.devices":"Device management","manage.sec.scan":"Network scan",
 "manage.add":"+ Add device","manage.import":"Import","manage.export":"Export",
 "manage.scan.start":"Start scan","manage.add.btn":"Add",
 "manage.scan.initial":'Please select a network and click "Scan".',
 "manage.scan.running":"Scanning selected networks for active devices",
 "manage.scan.done":"{count} device(s) found",
 "manage.scan.none":"No network selected","manage.scan.none.msg":"Please select at least one network to scan.",
 "manage.dns":"  |  DNS: {dns}",
 "edit.title":"Edit","edit.delete":"Delete",
 "del.title":"Confirm deletion","del.message":'Do you really want to delete the device "{name}"?',
 "scan.known":"known","scan.new":"new",
 "imp.done":"{count} device(s) imported.","exp.done":"Exported to {name} ({count} entries).",
 "imp.summary":"Import: {added} new, {updated} updated, {skipped} skipped.","imp.err":"Import failed: format not readable.",
 "dev.add":"Add device","dev.edit":"Edit device",
 "dev.name":"Device name:","dev.mac":"MAC address:","dev.ip":"IP address / hostname:",
 "dev.user":"Username:","dev.pass":"Password:","dev.method":"Shutdown method:",
 "dev.watch":"Watched processes (Dashboard):",
 "ph.name":"Enter device name","ph.mac":"e.g., AA:BB:CC:DD:EE:FF","ph.ip":"e.g., 192.168.1.100 or ubuntu-mercury",
 "ph.user":"Username (optional)","ph.pass":"Password (optional)","ph.watch":"e.g., llama-server.exe:8080",
 "ph.pass.keep":"Leave empty = keep stored password",
 "dev.added":"Device added.",
 "dev.method.host":"Host service (recommended)","dev.method.smb":"SMB (Windows share)",
 "dev.enabled":"Device is enabled","dev.save":"Save","dev.update":"Update","dev.cancel":"Cancel",
 "err.name":"Please enter a name.","err.mac":"Invalid MAC address (e.g. AA:BB:CC:DD:EE:FF).",
 "err.ip":"Invalid IP or hostname.",
 "dev.saved":"Device saved.","dev.deleted":"Device deleted.",
 "mac.unknown.title":"Unknown MAC address","mac.unknown.msg":"Device {host} ({ip}) has an unknown MAC address. Continue with placeholder?",
 "mac.dup.title":"Device already exists","mac.dup.msg":"A device with MAC address {mac} already exists.",
 "sched.subtitle":"Switch devices on or off on a schedule",
 "sched.add":"+ Create schedule","sched.search":"Search schedules…",
 "sched.empty":"No schedules yet. Create your first schedule.",
 "sched.wake":"Wake","sched.shutdown":"Shut down",
 "sched.days.every":"Daily","sched.days.weekdays":"Weekdays",
 "sched.del.title":"Delete schedule","sched.del.message":'Do you really want to delete the schedule for "{name}"?',
 "sched.no_dev.title":"No devices","sched.no_dev.msg":"Please add a device first before creating a schedule.",
 "sc.add":"New schedule","sc.edit":"Edit schedule",
 "sc.device":"Device:","sc.action":"Action:","sc.act.wake":"Power on","sc.act.shutdown":"Shut down",
 "sc.time":"Time:","sc.days":"Days of week","sc.enabled":"Schedule is enabled",
 "sc.no_days.title":"No days","sc.no_days.msg":"Please select at least one day of the week.",
 "sc.unknown":"Unknown device","sc.saved":"Schedule saved.",
 "day.Mon":"Mon","day.Tue":"Tue","day.Wed":"Wed","day.Thu":"Thu","day.Fri":"Fri","day.Sat":"Sat","day.Sun":"Sun",
 "logs.subtitle":"All application events",
 "logs.search":"Search message or device…","logs.level.all":"All levels",
 "logs.export":"Export CSV","logs.empty":"No log entries.",
 "logs.exported":"Log exported to {path}","logs.unknown":"Unknown",
 "set.subtitle":"Configure application & network",
 "set.broadcast_ip":"Broadcast IP","set.broadcast_port":"Broadcast port","set.language":"Language",
 "set.display":"Display mode","set.design":"App design","set.design.hint":"Changing the design requires an app restart.",
 "set.auto_update":"Automatically check for updates","set.interval":"Check interval",
 "set.max_logs":"Maximum log entries","set.resolution":"Resolution","set.method":"Default method for new devices",
 "disp.auto":"Auto","disp.light":"Light","disp.dark":"Dark",
 "design.classic":"Classic app","design.modern":"Modern app",
 "int.day":"Every day","int.week":"Every week","int.month":"Every month",
 "res.opt":"Optimized 16:9",
 "set.info":"Wake-on-LAN works by sending a special 'Magic Packet' to the MAC address of the target device on the local network. The device must support Wake-on-LAN and have it enabled in BIOS/UEFI and system settings.",
 "set.reset":"Reset","set.save":"Save",
 "set.saved.title":"Settings saved","set.saved.msg":"Settings saved successfully.",
 "set.reset.title":"Restore factory settings",
 "set.reset.msg":"Do you want to reset all settings to factory defaults?\n\nDevices, schedules and logs are kept.",
 "err.ip_missing":"IP address missing","err.ip_title":"Invalid IP address",
 "err.ip_msg":"The IP address format is invalid. Use x.x.x.x (e.g. 192.168).",
 "err.port_title":"Invalid port","err.port_msg":"The port number must be between 1 and 65535.",
 "about.name":"Wake-on-LAN Manager","about.version":"Version: {v}",
 "about.desc":"A powerful tool for managing devices on your network via Wake-on-LAN technology.",
 "upd.check":"🔄 Check for updates","upd.changelog":"Changelog",
 "upd.checking":"Checking for updates…","upd.ok":"✅ You are using the latest version.",
 "upd.err":"⚠️ {msg}","upd.err.msg":"The update check could not be performed.",
 "upd.new":"🆕 New version {v} available!",
 "dash.back":"← Devices","dash.interval":"Interval",
 "dash.swipe":"Swipe left/right to switch to the next device.",
 "dash.svc":"Services","dash.svc.sub":"Watched processes","dash.svc.none":"No watched processes configured.",
 "svc.running":"running · PID {pid}","svc.ready":"running · PID {pid} · API ready :{port}","svc.unreach":"running (PID {pid}), but port {port} unreachable","svc.gone":"Process not found",
 "svc.probing":"checking…",
 "dash.inferenz":"⚡ Inference active","dash.model":"🧠 {m}",
 "m.cpu":"CPU LOAD","m.ram":"RAM USAGE","m.gpu":"GPU LOAD","m.vram":"VRAM USAGE",
 "d.cores":"{n} cores","d.gb":"{used} / {total} GB","d.uptime":"Uptime {v}","d.na":"n/a",
 "hostv":"Host Service v{v}",
 "batch.title":"Batches","batch.new":"New","batch.dup":"Duplicate","batch.del":"Delete",
 "batch.run":"Run","batch.save":"Save","batch.clear":"Clear","batch.out":"Output",
 "batch.timeout":"Timeout (s)","batch.allow":"Allow batches on this device",
 "batch.newname":"New batch","batch.running":"Batch running…","batch.exit":"Exit code: {c}","batch.dur":"Duration: {s} s",
 "batch.empty":"No batches yet. \"New\" creates a new batch.",
 "batch.disabled":"Execution disabled: enable \"Allow batches\" and release the host (WOL Host Service.exe --enable-batch).",
 "dash.creds":"No credentials stored for this device. Dashboard metrics require host service sign-in.",
 "dash.unreach":"Host Service unreachable ({ip}:8765). Is the service running?",
 "dash.err":"Host service error: {msg}",
 "batch.exit.short":"exit code {c}","batch.save.first":"Please save the batch first.",
 "yes":"Yes","no":"No","ok":"OK"
},
fr:{
 "nav.devices":"Appareils","nav.manage":"Gérer","nav.schedule":"Planification","nav.logs":"Journaux","nav.settings":"Paramètres",
 "devices.summary":"{total} appareils · {online} en ligne",
 "devices.empty":"Aucun appareil. Ajoutez des appareils dans Gérer.",
 "devices.wake":"Réveiller","devices.shutdown":"Éteindre","devices.wake_all":"Tout démarrer",
 "devices.refresh":"Actualiser","devices.viewList":"Passer à la liste","devices.viewGrid":"Passer aux vignettes",
 "devices.search":"Rechercher nom, MAC, IP ou utilisateur…",
 "sort.name":"Nom","sort.ip":"Adresse IP","sort.mac":"Adresse MAC","sort.status":"Statut",
 "status.online":"En ligne","status.offline":"Hors ligne","status.unknown":"Inconnu",
 "device.me":"(moi)","device.disabled":"Désactivé",
 "button.remote_fullscreen":"Plein écran","button.remote_window":"Fenêtre","button.dashboard":"Tableau de bord","button.ping":"Ping",
 "shutdown.title":"Confirmer l'extinction","shutdown.message":"Voulez-vous vraiment éteindre l'appareil ?",
 "wakeall.title":"Réveiller tous les appareils","wakeall.message":"Voulez-vous vraiment réveiller les {count} appareils ?",
 "wakeall.done":"Magic packets envoyés avec succès à {count} appareil(s).",
 "wol.sent":"Magic packet envoyé à {name}.","wol.online":"{name} est en ligne.","wol.fail":"{count} appareil(s) n'ont pas reçu le paquet.",
 "wol.failone":"Échec du réveil de {name}.",
 "ping.ok":"Ping vers {ip} : réponse en {ms} ms","ping.fail":"Ping vers {ip} : destination injoignable","ping.diag.none":"{ip} : aucune entrée DNS IPv4 – vérifier le DNS du smartphone (DNS privé désactivé ?)","ping.diag.fail":"{ip} : port inaccessible –",
 "remote.demo":"{mode} : connexion à {name} (démo)",
 "remote.soon":"Bureau à distance bientôt disponible – veuillez utiliser Windows App / Microsoft Remote Desktop.",
 "remote.notinstalled":"Aucune application de bureau à distance trouvée – veuillez installer « Windows App » (Microsoft Remote Desktop).",
 "remote.nohost":"Aucune adresse IP/nom d'hôte configuré pour cet appareil.",
 "remote.pwcopied":"Mot de passe RDP copié dans le presse-papiers – collez-le dans la fenêtre de connexion.",
 "manage.subtitle":"Gestion des appareils & analyse réseau",
 "manage.sec.devices":"Gestion des appareils","manage.sec.scan":"Analyse réseau",
 "manage.add":"+ Ajouter un appareil","manage.import":"Importer","manage.export":"Exporter",
 "manage.scan.start":"Démarrer l'analyse","manage.add.btn":"Ajouter",
 "manage.scan.initial":'Veuillez sélectionner un réseau et cliquer sur "Analyser".',
 "manage.scan.running":"Analyse des réseaux sélectionnés",
 "manage.scan.done":"{count} appareil(s) trouvé(s)",
 "manage.scan.none":"Aucun réseau sélectionné","manage.scan.none.msg":"Veuillez sélectionner au moins un réseau à analyser.",
 "manage.dns":"  |  DNS : {dns}",
 "edit.title":"Modifier","edit.delete":"Supprimer",
 "del.title":"Confirmer la suppression","del.message":'Voulez-vous vraiment supprimer l\'appareil "{name}" ?',
 "scan.known":"connu","scan.new":"nouveau",
 "imp.done":"{count} appareil(s) importé(s).","exp.done":"Export vers {name} ({count} entrées).",
 "imp.summary":"Import : {added} nouveau(x), {updated} mis à jour, {skipped} ignoré(s).","imp.err":"Échec de l'import : format illisible.",
 "dev.add":"Ajouter un appareil","dev.edit":"Modifier l'appareil",
 "dev.name":"Nom de l'appareil :","dev.mac":"Adresse MAC :","dev.ip":"Adresse IP / nom d'hôte :",
 "dev.user":"Utilisateur :","dev.pass":"Mot de passe :","dev.method":"Méthode d'extinction :",
 "dev.watch":"Processus surveillés (Tableau de bord) :",
 "ph.name":"Saisir le nom","ph.mac":"ex., AA:BB:CC:DD:EE:FF","ph.ip":"ex., 192.168.1.100 ou ubuntu-mercury",
 "ph.user":"Utilisateur (facultatif)","ph.pass":"Mot de passe (facultatif)","ph.watch":"ex., llama-server.exe:8080",
 "ph.pass.keep":"Vide = conserver le mot de passe enregistré",
 "dev.added":"Appareil ajouté.",
 "dev.method.host":"Service hôte (recommandé)","dev.method.smb":"SMB (partage Windows)",
 "dev.enabled":"L'appareil est activé","dev.save":"Enregistrer","dev.update":"Actualiser","dev.cancel":"Annuler",
 "err.name":"Veuillez saisir un nom.","err.mac":"Adresse MAC invalide (ex. AA:BB:CC:DD:EE:FF).",
 "err.ip":"IP ou nom d'hôte invalide.",
 "dev.saved":"Appareil enregistré.","dev.deleted":"Appareil supprimé.",
 "mac.unknown.title":"Adresse MAC inconnue","mac.unknown.msg":"L'appareil {host} ({ip}) a une adresse MAC inconnue. Continuer avec un espace réservé ?",
 "mac.dup.title":"L'appareil existe déjà","mac.dup.msg":"Un appareil avec la MAC {mac} existe déjà.",
 "sched.subtitle":"Allumer ou éteindre les appareils à heure fixe",
 "sched.add":"+ Créer une planification","sched.search":"Rechercher…",
 "sched.empty":"Aucune planification. Créez votre première planification.",
 "sched.wake":"Réveiller","sched.shutdown":"Éteindre",
 "sched.days.every":"Quotidien","sched.days.weekdays":"Jours ouvrés",
 "sched.del.title":"Supprimer la planification","sched.del.message":'Voulez-vous vraiment supprimer la planification de "{name}" ?',
 "sched.no_dev.title":"Aucun appareil","sched.no_dev.msg":"Ajoutez d'abord un appareil avant de créer une planification.",
 "sc.add":"Nouvelle planification","sc.edit":"Modifier la planification",
 "sc.device":"Appareil :","sc.action":"Action :","sc.act.wake":"Allumer","sc.act.shutdown":"Éteindre",
 "sc.time":"Heure :","sc.days":"Jours de la semaine","sc.enabled":"La planification est activée",
 "sc.no_days.title":"Aucun jour","sc.no_days.msg":"Veuillez sélectionner au moins un jour.",
 "sc.unknown":"Appareil inconnu","sc.saved":"Planification enregistrée.",
 "day.Mon":"Lu","day.Tue":"Ma","day.Wed":"Me","day.Thu":"Je","day.Fri":"Ve","day.Sat":"Sa","day.Sun":"Di",
 "logs.subtitle":"Tous les événements de l'application",
 "logs.search":"Rechercher message ou appareil…","logs.level.all":"Tous les niveaux",
 "logs.export":"Exporter CSV","logs.empty":"Aucune entrée de journal.",
 "logs.exported":"Journal exporté vers {path}","logs.unknown":"Inconnu",
 "set.subtitle":"Configurer l'application et le réseau",
 "set.broadcast_ip":"IP de diffusion","set.broadcast_port":"Port de diffusion","set.language":"Langue",
 "set.display":"Mode d'affichage","set.design":"Design de l'app","set.design.hint":"Un changement de design exige un redémarrage.",
 "set.auto_update":"Rechercher les mises à jour","set.interval":"Intervalle",
 "set.max_logs":"Entrées de journal max.","set.resolution":"Résolution","set.method":"Méthode par défaut",
 "disp.auto":"Auto","disp.light":"Clair","disp.dark":"Sombre",
 "design.classic":"App classique","design.modern":"App moderne",
 "int.day":"Chaque jour","int.week":"Chaque semaine","int.month":"Chaque mois",
 "res.opt":"Optimisé 16:9",
 "set.info":"Le Wake-on-LAN envoie un 'Magic Packet' à l'adresse MAC de l'appareil cible sur le réseau local. L'appareil doit prendre en charge le WOL et l'avoir activé dans le BIOS/UEFI et les paramètres système.",
 "set.reset":"Réinitialiser","set.save":"Enregistrer",
 "set.saved.title":"Paramètres enregistrés","set.saved.msg":"Paramètres enregistrés avec succès.",
 "set.reset.title":"Rétablir les paramètres d'usine",
 "set.reset.msg":"Voulez-vous réinitialiser tous les paramètres ?\n\nAppareils, planifications et journaux sont conservés.",
 "err.ip_missing":"Adresse IP manquante","err.ip_title":"Adresse IP invalide",
 "err.ip_msg":"Le format est invalide. Utilisez x.x.x.x (ex. 192.168).",
 "err.port_title":"Port invalide","err.port_msg":"Le port doit être compris entre 1 et 65535.",
 "about.name":"Wake-on-LAN Manager","about.version":"Version : {v}",
 "about.desc":"Un outil puissant pour gérer les appareils du réseau via la technologie Wake-on-LAN.",
 "upd.check":"🔄 Rechercher les mises à jour","upd.changelog":"Changelog",
 "upd.checking":"Recherche de mises à jour…","upd.ok":"✅ Vous utilisez la dernière version.",
 "upd.err":"⚠️ {msg}","upd.err.msg":"La vérification a échoué.",
 "upd.new":"🆕 Nouvelle version {v} disponible !",
 "dash.back":"← Appareils","dash.interval":"Intervalle",
 "dash.swipe":"Faites glisser à gauche/droite pour changer d'appareil.",
 "dash.svc":"Services","dash.svc.sub":"Processus surveillés","dash.svc.none":"Aucun processus surveillé.",
 "svc.running":"actif · PID {pid}","svc.ready":"actif · PID {pid} · API prête :{port}","svc.unreach":"actif (PID {pid}), port {port} injoignable","svc.gone":"Processus introuvable",
 "svc.probing":"vérification…",
 "dash.inferenz":"⚡ Inférence active","dash.model":"🧠 {m}",
 "m.cpu":"CHARGE CPU","m.ram":"UTILISATION RAM","m.gpu":"CHARGE GPU","m.vram":"UTILISATION VRAM",
 "d.cores":"{n} cœurs","d.gb":"{used} / {total} Go","d.uptime":"Uptime {v}","d.na":"n/d",
 "hostv":"Service hôte v{v}",
 "batch.title":"Lots","batch.new":"Nouveau","batch.dup":"Dupliquer","batch.del":"Supprimer",
 "batch.run":"Exécuter","batch.save":"Enregistrer","batch.clear":"Vider","batch.out":"Sortie",
 "batch.timeout":"Timeout (s)","batch.allow":"Autoriser les lots sur cet appareil",
 "batch.newname":"Nouveau lot","batch.running":"Lot en cours…","batch.exit":"Code retour : {c}","batch.dur":"Durée : {s} s",
 "batch.empty":"Aucun lot. « Nouveau » crée un lot.",
 "batch.disabled":"Exécution désactivée : activez « Autoriser les lots » et libérez l'hôte.",
 "dash.creds":"Aucun identifiant enregistré. Les métriques exigent la connexion au service hôte.",
 "dash.unreach":"Service hôte injoignable ({ip}:8765). Le service tourne-t-il ?",
 "dash.err":"Erreur du service hôte : {msg}",
 "batch.exit.short":"code retour {c}","batch.save.first":"Veuillez d'abord enregistrer le lot.",
 "yes":"Oui","no":"Non","ok":"OK"
},
es:{
 "nav.devices":"Dispositivos","nav.manage":"Administrar","nav.schedule":"Planificación","nav.logs":"Registros","nav.settings":"Ajustes",
 "devices.summary":"{total} dispositivos · {online} en línea",
 "devices.empty":"Aún no hay dispositivos. Añádalos en Administrar.",
 "devices.wake":"Encender","devices.shutdown":"Apagar","devices.wake_all":"Iniciar todos",
 "devices.refresh":"Actualizar","devices.viewList":"Cambiar a lista","devices.viewGrid":"Cambiar a mosaico",
 "devices.search":"Buscar por nombre, MAC, IP o usuario…",
 "sort.name":"Nombre","sort.ip":"Dirección IP","sort.mac":"Dirección MAC","sort.status":"Estado",
 "status.online":"En línea","status.offline":"Fuera de línea","status.unknown":"Desconocido",
 "device.me":"(yo)","device.disabled":"Deshabilitado",
 "button.remote_fullscreen":"Remoto completo","button.remote_window":"Remoto en ventana","button.dashboard":"Panel","button.ping":"Ping",
 "shutdown.title":"Confirmar apagado","shutdown.message":"¿Realmente quiere apagar el dispositivo?",
 "wakeall.title":"Activar todos los dispositivos","wakeall.message":"¿Realmente quiere activar los {count} dispositivos?",
 "wakeall.done":"Paquetes mágicos enviados con éxito a {count} dispositivo(s).",
 "wol.sent":"Paquete mágico enviado a {name}.","wol.online":"{name} está en línea.","wol.fail":"{count} dispositivo(s) no recibieron el paquete.",
 "wol.failone":"Fallo al encender {name}.",
 "ping.ok":"Ping a {ip}: respuesta en {ms} ms","ping.fail":"Ping a {ip}: destino inaccesible","ping.diag.none":"{ip}: sin entrada DNS IPv4 – compruebe el DNS del smartphone (¿DNS privado desactivado?)","ping.diag.fail":"{ip}: puerto inaccesible –",
 "remote.demo":"{mode}: conectando a {name} (demo)",
 "remote.soon":"Escritorio remoto próximamente – use Windows App / Microsoft Remote Desktop.",
 "remote.notinstalled":"No se encontró ninguna aplicación de escritorio remoto: instale « Windows App » (Microsoft Remote Desktop).",
 "remote.nohost":"Este dispositivo no tiene dirección IP/nombre de host configurado.",
 "remote.pwcopied":"Contraseña RDP copiada al portapapeles: péguela en la ventana de conexión.",
 "manage.subtitle":"Gestión de dispositivos y escaneo de red",
 "manage.sec.devices":"Gestión de dispositivos","manage.sec.scan":"Escaneo de red",
 "manage.add":"+ Añadir dispositivo","manage.import":"Importar","manage.export":"Exportar",
 "manage.scan.start":"Iniciar escaneo","manage.add.btn":"Añadir",
 "manage.scan.initial":'Seleccione una red y haga clic en "Escanear".',
 "manage.scan.running":"Escaneando las redes seleccionadas",
 "manage.scan.done":"{count} dispositivo(s) encontrados",
 "manage.scan.none":"Ninguna red seleccionada","manage.scan.none.msg":"Seleccione al menos una red para escanear.",
 "manage.dns":"  |  DNS: {dns}",
 "edit.title":"Editar","edit.delete":"Eliminar",
 "del.title":"Confirmar eliminación","del.message":'¿Realmente quiere eliminar el dispositivo "{name}"?',
 "scan.known":"conocido","scan.new":"nuevo",
 "imp.done":"{count} dispositivo(s) importados.","exp.done":"Exportado a {name} ({count} entradas).",
 "imp.summary":"Importación: {added} nuevos, {updated} actualizados, {skipped} omitidos.","imp.err":"Importación fallida: formato ilegible.",
 "dev.add":"Añadir dispositivo","dev.edit":"Editar dispositivo",
 "dev.name":"Nombre del dispositivo:","dev.mac":"Dirección MAC:","dev.ip":"Dirección IP / nombre de host:",
 "dev.user":"Usuario:","dev.pass":"Contraseña:","dev.method":"Método de apagado:",
 "dev.watch":"Procesos supervisados (Panel):",
 "ph.name":"Introduzca el nombre","ph.mac":"p. ej., AA:BB:CC:DD:EE:FF","ph.ip":"p. ej., 192.168.1.100 o ubuntu-mercury",
 "ph.user":"Usuario (opcional)","ph.pass":"Contraseña (opcional)","ph.watch":"p. ej., llama-server.exe:8080",
 "ph.pass.keep":"Vacío = mantener la contraseña guardada",
 "dev.added":"Dispositivo añadido.",
 "dev.method.host":"Servicio host (recomendado)","dev.method.smb":"SMB (recurso compartido Windows)",
 "dev.enabled":"El dispositivo está habilitado","dev.save":"Guardar","dev.update":"Actualizar","dev.cancel":"Cancelar",
 "err.name":"Introduzca un nombre.","err.mac":"MAC no válida (p. ej. AA:BB:CC:DD:EE:FF).",
 "err.ip":"IP o host no válido.",
 "dev.saved":"Dispositivo guardado.","dev.deleted":"Dispositivo eliminado.",
 "mac.unknown.title":"MAC desconocida","mac.unknown.msg":"El dispositivo {host} ({ip}) tiene una MAC desconocida. ¿Continuar con marcador?",
 "mac.dup.title":"El dispositivo ya existe","mac.dup.msg":"Ya existe un dispositivo con la MAC {mac}.",
 "sched.subtitle":"Encender o apagar dispositivos programados",
 "sched.add":"+ Crear planificación","sched.search":"Buscar planificaciones…",
 "sched.empty":"No hay planificaciones. Cree su primera planificación.",
 "sched.wake":"Encender","sched.shutdown":"Apagar",
 "sched.days.every":"Diario","sched.days.weekdays":"Lunes a viernes",
 "sched.del.title":"Eliminar planificación","sched.del.message":'¿Realmente quiere eliminar la planificación de "{name}"?',
 "sched.no_dev.title":"Sin dispositivos","sched.no_dev.msg":"Añada primero un dispositivo antes de crear una planificación.",
 "sc.add":"Nueva planificación","sc.edit":"Editar planificación",
 "sc.device":"Dispositivo:","sc.action":"Acción:","sc.act.wake":"Encender","sc.act.shutdown":"Apagar",
 "sc.time":"Hora:","sc.days":"Días de la semana","sc.enabled":"La planificación está activada",
 "sc.no_days.title":"Sin días","sc.no_days.msg":"Seleccione al menos un día.",
 "sc.unknown":"Dispositivo desconocido","sc.saved":"Planificación guardada.",
 "day.Mon":"Lu","day.Tue":"Ma","day.Wed":"Mi","day.Thu":"Ju","day.Fri":"Vi","day.Sat":"Sá","day.Sun":"Do",
 "logs.subtitle":"Todos los eventos de la aplicación",
 "logs.search":"Buscar mensaje o dispositivo…","logs.level.all":"Todos los niveles",
 "logs.export":"Exportar CSV","logs.empty":"No hay entradas de registro.",
 "logs.exported":"Registro exportado a {path}","logs.unknown":"Desconocido",
 "set.subtitle":"Configurar aplicación y red",
 "set.broadcast_ip":"IP de difusión","set.broadcast_port":"Puerto de difusión","set.language":"Idioma",
 "set.display":"Modo de visualización","set.design":"Diseño de la app","set.design.hint":"Cambiar el diseño requiere reiniciar la app.",
 "set.auto_update":"Buscar actualizaciones automáticamente","set.interval":"Intervalo",
 "set.max_logs":"Entradas máx. del registro","set.resolution":"Resolución","set.method":"Método predeterminado",
 "disp.auto":"Auto","disp.light":"Claro","disp.dark":"Oscuro",
 "design.classic":"App clásica","design.modern":"App moderna",
 "int.day":"Cada día","int.week":"Cada semana","int.month":"Cada mes",
 "res.opt":"Optimizado 16:9",
 "set.info":"Wake-on-LAN envía un 'Magic Packet' a la dirección MAC del dispositivo destino en la red local. El dispositivo debe admitir WOL y tenerlo activado en la BIOS/UEFI y la configuración del sistema.",
 "set.reset":"Restablecer","set.save":"Guardar",
 "set.saved.title":"Ajustes guardados","set.saved.msg":"Ajustes guardados correctamente.",
 "set.reset.title":"Restaurar valores de fábrica",
 "set.reset.msg":"¿Quiere restablecer todos los ajustes?\n\nLos dispositivos, planificaciones y registros se conservan.",
 "err.ip_missing":"Falta la dirección IP","err.ip_title":"IP no válida",
 "err.ip_msg":"El formato no es válido. Use x.x.x.x (p. ej. 192.168).",
 "err.port_title":"Puerto no válido","err.port_msg":"El puerto debe estar entre 1 y 65535.",
 "about.name":"Wake-on-LAN Manager","about.version":"Versión: {v}",
 "about.desc":"Una herramienta potente para gestionar dispositivos en su red mediante Wake-on-LAN.",
 "upd.check":"🔄 Buscar actualizaciones","upd.changelog":"Changelog",
 "upd.checking":"Buscando actualizaciones…","upd.ok":"✅ Ya usa la última versión.",
 "upd.err":"⚠️ {msg}","upd.err.msg":"No se pudo comprobar la actualización.",
 "upd.new":"🆕 ¡Nueva versión {v} disponible!",
 "dash.back":"← Dispositivos","dash.interval":"Intervalo",
 "dash.swipe":"Desliza a izquierda/derecha para cambiar de dispositivo.",
 "dash.svc":"Servicios","dash.svc.sub":"Procesos supervisados","dash.svc.none":"Sin procesos supervisados.",
 "svc.running":"activo · PID {pid}","svc.ready":"activo · PID {pid} · API lista :{port}","svc.unreach":"activo (PID {pid}), puerto {port} inaccesible","svc.gone":"Proceso no encontrado",
 "svc.probing":"comprobando…",
 "dash.inferenz":"⚡ Inferencia activa","dash.model":"🧠 {m}",
 "m.cpu":"CARGA DE CPU","m.ram":"USO DE RAM","m.gpu":"CARGA DE GPU","m.vram":"USO DE VRAM",
 "d.cores":"{n} núcleos","d.gb":"{used} / {total} GB","d.uptime":"Tiempo activo {v}","d.na":"n/d",
 "hostv":"Servicio host v{v}",
 "batch.title":"Lotes","batch.new":"Nuevo","batch.dup":"Duplicar","batch.del":"Eliminar",
 "batch.run":"Ejecutar","batch.save":"Guardar","batch.clear":"Vaciar","batch.out":"Salida",
 "batch.timeout":"Tiempo máx. (s)","batch.allow":"Permitir lotes en este dispositivo",
 "batch.newname":"Nuevo lote","batch.running":"Lote en ejecución…","batch.exit":"Código de salida: {c}","batch.dur":"Duración: {s} s",
 "batch.empty":"No hay lotes. „Nuevo\" crea un lote.",
 "batch.disabled":"Ejecución desactivada: active „Permitir lotes\" y libere el host.",
 "dash.creds":"No hay credenciales para este dispositivo. Las métricas requieren inicio de sesión del servicio host.",
 "dash.unreach":"Servicio host inaccesible ({ip}:8765). ¿Está en ejecución?",
 "dash.err":"Error del servicio host: {msg}",
 "batch.exit.short":"código de salida {c}","batch.save.first":"Guarde primero el lote.",
 "yes":"Sí","no":"No","ok":"OK"
}};

/* ══════════════════════════ State / Datenmodell ═══════════════════════════
   Native (Repo) ist Source-of-Truth für Geräte/Zeitpläne/Protokolle/Einstellungen.
   Beim Start wird via Native.snapshot() geladen. Pro Gerät kommen reine
   Laufzeit-Felder dazu (nicht persistiert):
   device = { id, name, mac, ip, username, enabled, watch[], allow_batch, batches[],
              + status: online|offline|unknown|waking, local, sim:{proto,reachable},
                upSeconds, metrics, spark:{cpu,ram,gpu}, gpuHigh, checking }       */
const state = {
  lang: "de", displayMode: "auto", theme: "dark",
  settings: {
    broadcastIp: "255.255.255.255", broadcastPort: 9, language: "",
    displayMode: "auto", autoUpdate: true, interval: "168", maxLogs: 100,
  },
  ui: { screen: "devices", deviceView: "grid", sort: "name", search: "",
        manageSearch: "", schedSearch: "", logSearch: "", logLevel: "all",
        dashDeviceId: null, dashInterval: 3000, editing: null, confirmFn: null,
        selBatch: null, pressTimer: null },
  devices: [],
  schedules: [],
  logs: [],
  scan: { running:false, results:[], shown:false, ifaces:[] },
  con: { lines:[], running:false, exit:null, dur:null, timer:null },
  upd: "",
};

/* Native-Fassade: in der App → echte Brücke, im Browser → Demo-Stub (bridge.js). */
const Native = (typeof window !== "undefined" && window.Native) ? window.Native : null;

/* Reine Laufzeit-Felder pro Gerät (nie persistiert). */
function rtDefaults() {
  return { status: "unknown", local: false, upSeconds: 0, metrics: null, dashError: null,
    spark: { cpu: [], ram: [], gpu: [] }, gpuHigh: 0, checking: false };
}
/* Geräte aus nativer Sicht übernehmen: Runtime-Felder existing Geräte bleiben erhalten. */
function applyDevices(list) {
  const prev = new Map(state.devices.map(d => [d.id, d]));
  state.devices = (list || []).map(d => {
    const base = prev.get(d.id) || Object.assign({ id: d.id }, rtDefaults());
    return Object.assign(base, {
      name: d.name, mac: d.mac, ip: d.ip, username: d.username, enabled: d.enabled,
      hasPassword: d.hasPassword, watch: d.watch || [], allow_batch: !!d.allow_batch,
      batches: d.batches || [],
    });
  });
}
function setRt(id, patch) { const d = byId(id); if (d) Object.assign(d, patch); }
/* Save ohne Passwortfeld: nativ bleibt das gespeicherte Passwort erhalten. */
function saveDeviceNative(d, extra) {
  return Native.call("saveDevice", Object.assign({
    id: d.id, name: d.name, mac: d.mac, ip: d.ip, username: d.username, password: "",
    enabled: d.enabled, watch: d.watch, allow_batch: d.allow_batch, batches: d.batches,
  }, extra || {}));
}

/* ══════════════════════════ Helpers ═══════════════════════════════════════ */
const $ = s => document.querySelector(s);
const t = (k, vars) => {
  let s = (I18N[state.lang] && I18N[state.lang][k]) ?? I18N.de[k] ?? k;
  for (const [v, r] of Object.entries(vars || {})) s = s.replaceAll("{"+v+"}", r);
  return s;
};
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const escA = s => esc(s).replaceAll("\n","<br>");
const rnd = (a, b) => a + Math.random() * (b - a);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const byId = id => state.devices.find(d => d.id === id);
const DAY_CODES = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
const RE_MAC = /^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$/;
const RE_HOST = /^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$/;
const RE_IP = /^(\d{1,3}\.){3}\d{1,3}$/;
const dotCls = d => d.status === "online" ? "dotOnline" : d.status === "offline" ? "dotOffline"
  : d.status === "waking" ? "dotWaking" : "dotUnknown";
const statusName = d => t("status." + (d.status === "waking" ? "unknown" : d.status));
function fmtUptime(s) {
  const d = Math.floor(s/86400), h = Math.floor(s%86400/3600), m = Math.floor(s%3600/60);
  return (d ? d+"d " : "") + String(h).padStart(2,"0") + ":" + String(m).padStart(2,"0");
}
function daysText(days) {
  if (!days.length || days.length === 7) return t("sched.days.every");
  if (days.length === 5 && DAY_CODES.slice(0,5).every(d => days.includes(d))) return t("sched.days.weekdays");
  return DAY_CODES.filter(d => days.includes(d)).map(d => t("day."+d)).join(" · ");
}
function logIt(device, level, msg) {
  state.logs.unshift({ ts: Date.now(), device, level, msg });
  if (state.logs.length > 300) state.logs.pop();
  Native.call("log", { device, level, msg });
  if (state.ui.screen === "logs") renderLogs();
}
function toast(msg, isErr) {
  const el = $("#toast"); el.textContent = msg;
  el.classList.toggle("err", !!isErr); el.classList.add("show");
  clearTimeout(el._tm); el._tm = setTimeout(() => el.classList.remove("show"), 2600);
}

/* ══════════════════════════ Sheet / Dialoge ═══════════════════════════════ */
function openSheet(html) { $("#sheet").innerHTML = html; $("#sheet").classList.add("open"); $("#overlay").classList.add("open"); Native.setSheetOpen(true); }
function closeSheet() { $("#sheet").classList.remove("open"); $("#overlay").classList.remove("open"); state.ui.editing = null; state.ui.confirmFn = null; Native.setSheetOpen(false); }
function openConfirm(title, msg, onYes, yesCls = "primary") {
  state.ui.confirmFn = onYes;
  openSheet(`<div class="grab"></div><h2>${esc(title)}</h2>
    <p style="font-size:13.5px;line-height:1.55">${escA(msg)}</p>
    <div class="sheetbtns"><button class="btn" data-act="sheet-close">${esc(t("no"))}</button>
    <button class="btn ${yesCls}" data-act="confirm-yes">${esc(t("yes"))}</button></div>`);
}
function openAlert(title, msg) {
  openSheet(`<div class="grab"></div><h2>${esc(title)}</h2>
    <p style="font-size:13.5px;line-height:1.55">${escA(msg)}</p>
    <div class="sheetbtns"><button class="btn primary" data-act="sheet-close">${esc(t("ok"))}</button></div>`);
}
/* Herunterfahren bestätigen – wie Windows ModernShutdownConfirmDialog (Power-Symbol) */
function openShutdownConfirm(d) {
  state.ui.confirmFn = () => shutdownDevice(d);
  openSheet(`<div class="grab"></div>
    <div style="text-align:center"><div class="powerIcon"></div>
    <h2 style="text-align:center;margin-bottom:0">${esc(t("shutdown.title"))}</h2>
    <p style="font-size:13.5px;color:var(--text-dim);margin-top:8px">${esc(t("shutdown.message"))}<br><b style="color:var(--text)">${esc(d.name)}</b></p></div>
    <div class="sheetbtns"><button class="btn" data-act="sheet-close">${esc(t("no"))}</button>
    <button class="btn danger" data-act="confirm-yes">${esc(t("yes"))}</button></div>`);
}

/* ══════════════════════════ Aktionen: Wake / Shutdown / Ping ══════════════ */
function wakeDevice(d) {
  if (!d || d.status === "online" || d.status === "waking" || !d.enabled) return;
  if (!RE_MAC.test(d.mac || "")) { openAlert(t("mac.unknown.title"), t("mac.unknown.msg", { host: d.name, ip: d.ip || "?" })); return; }
  setRt(d.id, { status: "waking" }); renderDevices();
  Native.call("wake", { id: d.id }).then(res => {
    if (!res.ok) { setRt(d.id, { status: "unknown" }); toast(t("wol.failone", { name: d.name }), true); }
    else toast(t("wol.sent", { name: d.name }));
    renderDevices(); if (state.ui.screen === "dash") renderDash();
  });
}
function shutdownDevice(d) {
  toast(t("devices.shutdown") + ": " + d.name + " …");
  Native.call("shutdown", { id: d.id }).then(res => {
    if (res.ok) { setRt(d.id, { status: "offline", metrics: null, upSeconds: 0 }); }
    else toast(String(res.error || "error"), true);
    renderDevices(); if (state.ui.screen === "dash") renderDash();
  });
}
function refreshStatus() {
  if (!state.devices.length) return;
  state.devices.forEach(d => { if (d.status === "unknown") setRt(d.id, { checking: true }); });
  Native.call("refreshStatus", {});
}
setInterval(() => { if (state.ui.screen === "devices") refreshStatus(); }, 30000);

function pingDevice(d) {
  Native.call("ping", { id: d.id }).then(res => {
    if (!res.ok) { toast(String(res.error || "error"), true); return; }
    const dg = res.data || {};
    const cands = dg.candidates || [];
    const first = cands.find(c => c.ok);
    if (first) { toast(t("ping.ok", { ip: dg.host || d.ip, ms: first.rttMs })); return; }
    if (!dg.resolved) { toast(t("ping.diag.none", { ip: dg.host || d.ip }), true); return; }
    const detail = cands.map(c => "✗ " + c.address + " – " + (c.error || "?")).join("  ");
    toast(t("ping.diag.fail", { ip: dg.host || d.ip }) + (detail ? " " + detail : ""), true);
  });
}

/* Remotedesktop: Windows App per rdp://-URI öffnen (Rechner + Benutzer vorbelegt).
   Das Passwort kann das Android-URI-Schema nicht übertragen → die Bridge legt es in
   die Zwischenablage, die UI weist darauf hin. Fehler → Toast. */
function doRemote(id, mode) {
  Native.call("remote", { id, mode: mode === "win" ? "win" : "full" }).then(res => {
    if (!res.ok) {
      const msg = String(res.error || "");
      const key = msg === "remote.notinstalled" ? "remote.notinstalled"
        : msg === "remote.nohost" ? "remote.nohost" : null;
      toast(key ? t(key) : msg, true);
      return;
    }
    const d = res.data || {};
    if (d.passwordCopied) toast(t("remote.pwcopied"));
  });
}

/* ══════════════════════════ Netzwerk-Scan (Verwalten) ═════════════════════ */
/* Interfaces + Scan laufen nativ (ConnectivityManager / TCP-Sweep). Ergebnisse
   kommen als Events: scan-progress / scan-found / scan-done. */
function loadIfaces() {
  Native.call("scanIfaces", {}).then(res => {
    if (!res.ok) return;
    const old = new Map(state.scan.ifaces.map(f => [f.ip + "/" + f.prefix, f.checked]));
    state.scan.ifaces = (res.data || []).map(f => ({
      name: f.name, ip: f.ip, prefix: f.prefix, dns: f.dns || "",
      checked: old.has(f.ip + "/" + f.prefix) ? old.get(f.ip + "/" + f.prefix) : !!f.checked,
    }));
    if (state.ui.screen === "manage") renderManage();
  });
}
function startScan() {
  if (!state.scan.ifaces.some(i => i.checked)) { openAlert(t("manage.scan.none"), t("manage.scan.none.msg")); return; }
  state.scan.running = true; state.scan.results = []; state.scan.shown = false;
  renderManage();
  Native.call("scanStart", {});
}
function scanAdd(host, ip, mac) {
  if (mac && state.devices.some(d => d.mac.toUpperCase() === mac.toUpperCase())) {
    openAlert(t("mac.dup.title"), t("mac.dup.msg", { mac })); return;
  }
  /* Android sieht kein MAC → mit Platzhalter vorbefüllen, Nutzer kann nachtragen. */
  openDeviceSheet(null, { name: (!host || host === "Unknown") ? "" : host, ip, mac: mac || "00:00:00:00:00:00" });
}

/* ══════════════════════════ Geräte-Dialog (Bottom-Sheet) ══════════════════ */
function openDeviceSheet(id, prefill) {
  const d = id ? byId(id) : null;
  state.ui.editing = d ? { ...d, watch: [...d.watch] } : {
    id: null, name: prefill?.name || "", mac: prefill?.mac || "", ip: prefill?.ip || "",
    username: "", password: "", enabled: true, watch: [] };
  const e = state.ui.editing;
  openSheet(`
    <div class="grab"></div><h2>${esc(t(d ? "dev.edit" : "dev.add"))}</h2>
    <div class="field"><label>${esc(t("dev.name"))}</label>
      <input class="inp" id="i-name" value="${esc(e.name)}" placeholder="${esc(t("ph.name"))}" maxlength="60">
      <div class="hint" id="e-name" style="color:var(--danger);display:none">${esc(t("err.name"))}</div></div>
    <div class="field"><label>${esc(t("dev.mac"))}</label>
      <input class="inp" id="i-mac" value="${esc(e.mac)}" placeholder="${esc(t("ph.mac"))}" maxlength="17">
      <div class="hint" id="e-mac" style="color:var(--danger);display:none">${esc(t("err.mac"))}</div></div>
    <div class="field"><label>${esc(t("dev.ip"))}</label>
      <input class="inp" id="i-ip" value="${esc(e.ip)}" placeholder="${esc(t("ph.ip"))}" maxlength="253">
      <div class="hint" id="e-ip" style="color:var(--danger);display:none">${esc(t("err.ip"))}</div></div>
    <div class="field"><label>${esc(t("dev.user"))}</label>
      <input class="inp" id="i-user" value="${esc(e.username)}" placeholder="${esc(t("ph.user"))}" autocomplete="off"></div>
    <div class="field"><label>${esc(t("dev.pass"))}</label>
      <input class="inp" id="i-pass" type="password" value=""
        placeholder="${esc(t(d && e.hasPassword ? "ph.pass.keep" : "ph.pass"))}" autocomplete="new-password"></div>
    <div class="field"><label>${esc(t("dev.watch"))}</label>
      <input class="inp" id="i-watch" value="${esc(e.watch.join(", "))}" placeholder="${esc(t("ph.watch"))}"></div>
    <div class="togRow" style="padding:6px 0 0"><div>${esc(t("dev.enabled"))}</div>
      <div class="toggle ${e.enabled ? "on" : ""}" data-act="edit-toggle" data-key="enabled"></div></div>
    <div class="sheetbtns">
      <button class="btn" data-act="sheet-close">${esc(t("dev.cancel"))}</button>
      <button class="btn primary" data-act="dev-save">${esc(t(d ? "dev.update" : "dev.save"))}</button>
    </div>`);
}
function saveDeviceFromSheet() {
  const e = state.ui.editing;
  const name = $("#i-name").value.trim(), mac = $("#i-mac").value.trim(), ip = $("#i-ip").value.trim();
  let bad = false;
  const mark = (id, ok) => { $("#" + id).style.display = ok ? "none" : "block"; if (!ok) bad = true; };
  mark("e-name", !!name);
  mark("e-mac", RE_MAC.test(mac));
  mark("e-ip", !ip || (RE_HOST.test(ip) && ip.length <= 253));
  if (bad) return;
  const payload = {
    id: e.id || "", name, mac: mac.toUpperCase(), ip,
    username: $("#i-user").value.trim(), password: $("#i-pass").value,
    enabled: e.enabled, watch: $("#i-watch").value.split(/[,;]/).map(s => s.trim()).filter(Boolean),
    allow_batch: e.allow_batch || false, batches: e.batches || [],
  };
  Native.call("saveDevice", payload).then(res => {
    if (!res.ok) { toast(String(res.error || "error"), true); return; }
    applyDevices(res.data);
    closeSheet(); renderDevices(); renderManage(); renderSched();
    toast(t("dev.saved"));
    logIt(name, e.id ? "info" : "info", t(e.id ? "dev.saved" : "dev.added"));
  });
}
function deleteDevice(id) {
  const d = byId(id);
  openConfirm(t("del.title"), t("del.message", { name: d.name }), () => {
    Native.call("deleteDevice", { id }).then(res => {
      if (!res.ok) { toast(String(res.error || "error"), true); return; }
      applyDevices(res.data);
      state.schedules = state.schedules.filter(s => s.deviceId !== id);
      closeSheet(); renderDevices(); renderManage(); renderSched();
      logIt(d.name, "warn", t("dev.deleted")); toast(t("dev.deleted"));
    });
  }, "danger");
}

/* ══════════════════════════ Zeitplan-Dialog (Bottom-Sheet) ════════════════ */
function openSchedSheet(id) {
  if (!state.devices.length) { openAlert(t("sched.no_dev.title"), t("sched.no_dev.msg")); return; }
  const sc = id ? state.schedules.find(s => s.id === id) : null;
  state.ui.editing = sc ? { ...sc, days: [...sc.days] } :
    { id: null, deviceId: state.devices[0].id, action: "wake", time: "07:30",
      days: [...DAY_CODES], enabled: true };
  const e = state.ui.editing;
  openSheet(`
    <div class="grab"></div><h2>${esc(t(sc ? "sc.edit" : "sc.add"))}</h2>
    <div class="field"><label>${esc(t("sc.device"))}</label>
      <select class="sel" id="sc-dev" style="width:100%">${state.devices.map(d =>
        `<option value="${d.id}" ${d.id === e.deviceId ? "selected" : ""}>${esc(d.name)}</option>`).join("")}</select></div>
    <div class="field"><label>${esc(t("sc.action"))}</label>
      <select class="sel" id="sc-act" style="width:100%">
        <option value="wake" ${e.action==="wake"?"selected":""}>${esc(t("sc.act.wake"))}</option>
        <option value="shutdown" ${e.action==="shutdown"?"selected":""}>${esc(t("sc.act.shutdown"))}</option></select></div>
    <div class="field"><label>${esc(t("sc.time"))}</label>
      <input class="inp" type="time" id="sc-time" value="${e.time}"></div>
    <div class="field"><label>${esc(t("sc.days"))}</label>
      <div style="display:flex;gap:5px;flex-wrap:wrap">${DAY_CODES.map(c =>
        `<span class="chip ${e.days.includes(c) ? "run" : "off"}" style="cursor:pointer;padding:6px 12px"
          data-act="sc-day" data-day="${c}">${esc(t("day."+c))}</span>`).join("")}</div></div>
    <div class="togRow" style="padding:2px 0"><div>${esc(t("sc.enabled"))}</div>
      <div class="toggle ${e.enabled ? "on" : ""}" data-act="edit-toggle" data-key="enabled"></div></div>
    <div class="sheetbtns">
      <button class="btn" data-act="sheet-close">${esc(t("dev.cancel"))}</button>
      <button class="btn primary" data-act="sc-save">${esc(t(sc ? "dev.update" : "dev.save"))}</button>
    </div>`);
}
function saveSchedFromSheet() {
  const e = state.ui.editing;
  e.deviceId = $("#sc-dev").value; e.action = $("#sc-act").value; e.time = $("#sc-time").value;
  if (!e.days.length) { openAlert(t("sc.no_days.title"), t("sc.no_days.msg")); return; }
  Native.call("saveSchedule", { id: e.id || "", deviceId: e.deviceId, action: e.action,
    time: e.time, days: e.days, enabled: e.enabled }).then(res => {
    if (!res.ok) { toast(String(res.error || "error"), true); return; }
    state.schedules = res.data || [];
    closeSheet(); renderSched(); toast(t("sc.saved"));
  });
}

/* ══════════════════════════ Long-Press-Kontextmenü (wie Rechtsklick) ══════ */
function openDeviceMenu(id) {
  const d = byId(id);
  const actRow = d.status === "online"
    ? `<div class="menuitem" data-act="m-shutdown" data-id="${id}">⏻ ${esc(t("devices.shutdown"))}</div>`
    : `<div class="menuitem ${d.status==="waking"||!d.enabled?"dis":""}" data-act="m-wake" data-id="${id}">⚡ ${esc(t("devices.wake"))}</div>`;
  openSheet(`<div class="grab"></div><h2>${esc(d.name)}</h2>
    <div class="menuitem ${d.status!=="online"?"dis":""}" data-act="m-rdp" data-id="${id}" data-mode="full">🖥️ ${esc(t("button.remote_fullscreen"))}</div>
    <div class="menuitem ${d.status!=="online"?"dis":""}" data-act="m-rdp" data-id="${id}" data-mode="win">🪟 ${esc(t("button.remote_window"))}</div>
    <div class="menuitem ${d.status!=="online"?"dis":""}" data-act="m-dash" data-id="${id}">📊 ${esc(t("button.dashboard"))}</div>
    <div class="sep"></div>${actRow}
    <div class="menuitem" data-act="m-ping" data-id="${id}">📡 ${esc(t("button.ping"))}</div>
    <div class="sep"></div>
    <div class="menuitem" data-act="m-edit" data-id="${id}">✏️ ${esc(t("edit.title"))}</div>
    <div class="menuitem" style="color:var(--danger)" data-act="m-del" data-id="${id}">🗑️ ${esc(t("edit.delete"))}</div>
    <div class="sheetbtns"><button class="btn" data-act="sheet-close">${esc(t("dev.cancel"))}</button></div>`);
}

/* ══════════════════════════ Dashboard-Metriken (echter Host Service) ══════ */
/* Metriken kommen nativ via metrics(id) → HostResult; kein Zufalls-Walk mehr. */
let dashTimer = null;
function dashTick() {
  const d = byId(state.ui.dashDeviceId);
  if (!d || d.status !== "online" || !d.username) return;
  Native.call("metrics", { id: d.id }).then(res => {
    if (state.ui.dashDeviceId !== d.id) return;
    if (!res.ok) { d.metrics = null; d.dashError = String(res.error || "error"); }
    else {
      const m = res.data;
      d.metrics = m; d.dashError = null;
      d.upSeconds = m.uptime || 0;
      for (const k of ["cpu", "ram", "gpu"]) {
        if (m[k] != null) { d.spark[k].push(m[k]); if (d.spark[k].length > 60) d.spark[k].shift(); }
      }
      if ((m.gpu || 0) >= 60) d.gpuHigh++; else d.gpuHigh = 0;
    }
    if (state.ui.screen === "dash") renderDash();
  });
}
function restartDashTimer() {
  clearInterval(dashTimer);
  dashTimer = setInterval(dashTick, state.ui.dashInterval);
}
restartDashTimer();

/* ── Wisch-Geste im Dashboard: wechselt zum nächsten/vorherigen Gerät in
   genau der Reihenfolge, die gerade im Gerätemanager sortiert ist. ──────── */
function dashDevicesOrdered() { return sortDevices([...state.devices]); }
function switchDashDevice(dir) {
  const list = dashDevicesOrdered();
  if (list.length < 2) return;
  let i = list.findIndex(x => x.id === state.ui.dashDeviceId);
  if (i < 0) i = 0;
  const nd = list[(i + dir + list.length) % list.length];
  state.ui.dashDeviceId = nd.id; state.ui.selBatch = null;
  state.con = { lines: [], running: false, exit: null, dur: null, timer: null };
  renderDash(dir > 0 ? "left" : "right");
  Native.call("vibrate", { ms: 10 });
}
(function initDashSwipe() {
  const el = document.getElementById("s-dash");
  if (!el) return;
  let s = null;
  el.addEventListener("touchstart", ev => {
    if (ev.touches.length !== 1) { s = null; return; }
    const p = ev.touches[0];
    s = { x: p.clientX, y: p.clientY, tm: Date.now() };
  }, { passive: true });
  el.addEventListener("touchend", ev => {
    if (!s) return;
    const st = s; s = null;
    const p = ev.changedTouches[0];
    const dx = p.clientX - st.x, dy = p.clientY - st.y;
    if (Date.now() - st.tm > 900) return;                    /* kein Drag/Scroll */
    if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 2) return; /* zu klein / vertikal */
    if (ev.target && ev.target.closest &&
        ev.target.closest("input,select,textarea,.console,#sheet,#overlay")) return;
    switchDashDevice(dx < 0 ? 1 : -1); /* links wischen → nächstes Gerät */
  }, { passive: true });
  el.addEventListener("touchcancel", () => { s = null; }, { passive: true });
})();

function updateDashLive(d) {
  const m = d.metrics; if (!m) return;
  for (const k of ["cpu", "ram", "gpu", "vram"]) {
    const g = document.querySelector(`[data-g="${k}"]`); if (!g) return;
    g.style.setProperty("--v", m[k] ?? 0);
    const b = document.querySelector(`[data-gv="${k}"]`); if (b) b.textContent = (m[k] ?? "–") + "%";
  }
  for (const k of ["cpu", "ram", "gpu"]) {
    const sp = document.querySelector(`[data-spark="${k}"]`);
    if (sp) sp.innerHTML = sparkSvg(d.spark[k], `var(--gauge-${k})`);
  }
  const up = $("#dashUptime"); if (up) up.textContent = t("d.uptime", { v: fmtUptime(m.uptime || 0) });
  const inf = $("#infBadge"); if (inf) inf.style.display = d.gpuHigh >= 2 ? "inline" : "none";
}
function sparkSvg(vals, color) {
  if (!vals || !vals.length) return `<svg width="100%" height="30" viewBox="0 0 140 30"></svg>`;
  const pts = vals.map((v, i) => `${((i / Math.max(1, vals.length - 1)) * 140).toFixed(1)},${(30 - (v / 100) * 28 - 1).toFixed(1)}`).join(" ");
  return `<svg width="100%" height="30" viewBox="0 0 140 30" preserveAspectRatio="none">
    <polyline fill="none" stroke="${color}" stroke-width="2" points="${pts}"/></svg>`;
}
/* Prozess-Info aus dem letzten Metrik-Snapshot (watch-Key → Eintrag). */
function procFor(d, key) { return (d.metrics && d.metrics.processes || []).find(p => p.key === key) || null; }
function svcLine(d, entry) {
  if (d.status !== "online") return t("svc.gone");
  const p = procFor(d, entry);
  if (!p) return t("svc.probing");
  if (!p.running) return t("svc.gone");
  const port = entry.split(":")[1] || String(p.apiPort || "8080");
  if (p.apiPort != null && p.apiPortOpen) return t("svc.ready", { pid: p.pid, port });
  if (p.apiPort != null && p.apiPortOpen === false) return t("svc.unreach", { pid: p.pid, port });
  return t("svc.running", { pid: p.pid });
}

/* ══════════════════════════ Batches (Dashboard, am Gerät persistiert) ════ */
function currentBatches() { const d = byId(state.ui.dashDeviceId); return d ? (d.batches || []) : []; }
function selBatchObj() { const d = byId(state.ui.dashDeviceId); return d ? (d.batches || []).find(b => b.id === state.ui.selBatch) : null; }
function persistBatches(d, msg) {
  saveDeviceNative(d).then(res => {
    if (res.ok) { applyDevices(res.data); if (msg) toast(msg); }
    else toast(String(res.error || "error"), true);
  });
}
function runBatch() {
  const b = selBatchObj(); const d = byId(state.ui.dashDeviceId);
  if (!b || !d || state.con.running) return;
  if (!d.allow_batch) { toast(t("batch.disabled"), true); return; }
  if (!b.id) { toast(t("batch.save.first"), true); return; }
  state.con = { lines: ["$ " + b.script], running: true, exit: null, dur: null, timer: null };
  renderDash();
  Native.call("runBatch", { id: d.id, batchId: b.id }).then(res => {
    state.con.running = false;
    if (!res.ok) {
      state.con.lines.push("ERROR: " + String(res.error || "error"));
      logIt(d.name, "error", `${b.name} -> ${String(res.error || "error")}`);
    } else {
      const r = res.data;
      (r.stdout || "").split(/\r?\n/).filter(x => x.length).forEach(x => state.con.lines.push(x));
      (r.stderr || "").split(/\r?\n/).filter(x => x.length).forEach(x => state.con.lines.push("! " + x));
      if (r.truncated) state.con.lines.push("… (truncated)");
      state.con.exit = r.exitCode;
      state.con.dur = (r.durationMs / 1000).toFixed(1);
      logIt(d.name, r.exitCode === 0 ? "info" : "error", `${b.name} -> ${t("batch.exit.short", { c: r.exitCode })}`);
    }
    renderDash();
  });
}

/* ══════════════════════════ Render: Geräte ════════════════════════════════ */
/* Geräte in der aktuell gewählten Gerätelisten-Sortierung (auch für das
   Dashboard: Wischen wechselt Geräte in genau dieser Reihenfolge). */
function sortDevices(devs) {
  const rank = { online: 0, offline: 1, waking: 2, unknown: 3 };
  const ipKey = ip => (ip || "").split(".").map(n => String(n.length).padStart(2,"0") + n).join(".");
  if (state.ui.sort === "name") devs.sort((a,b) => a.name.localeCompare(b.name));
  else if (state.ui.sort === "ip") devs.sort((a,b) => ipKey(a.ip).localeCompare(ipKey(b.ip)));
  else if (state.ui.sort === "mac") devs.sort((a,b) => a.mac.localeCompare(b.mac));
  else devs.sort((a,b) => rank[a.status] - rank[b.status] || a.name.localeCompare(b.name));
  return devs;
}
function filteredDevices(search) {
  let devs = [...state.devices];
  const q = (search || "").toLowerCase();
  if (q) devs = devs.filter(d => (d.name + " " + d.ip + " " + d.mac + " " + d.username).toLowerCase().includes(q));
  return sortDevices(devs);
}
function nameSuffix(d) {
  let s = "";
  if (d.local) s += ` <span style="color:var(--text-dim);font-weight:400">${esc(t("device.me"))}</span>`;
  if (!d.enabled) s += ` <span style="color:var(--text-dim);font-weight:400">${esc(t("device.disabled"))}</span>`;
  return s;
}
function renderDevices() {
  const online = state.devices.filter(d => d.status === "online").length;
  const devs = filteredDevices(state.ui.search);
  const grid = state.ui.deviceView === "grid";
  const cards = grid
    ? `<div class="grid">${devs.map(d => `
        <div class="card ${d.enabled ? "" : "dis"}" data-press data-id="${d.id}">
          <span class="dot ${dotCls(d)}" title="${esc(statusName(d))}"></span>
          <div class="name">${esc(d.name)}${nameSuffix(d)}</div>
          ${d.ip ? `<span class="mono">${esc(d.ip)}</span>` : ""}
          <span class="mono">${esc(d.mac)}</span>
          <div class="tiles">
            <button class="tileBtn" data-act="rdp-full" data-id="${d.id}" title="${esc(t("button.remote_fullscreen"))}" ${d.status!=="online"?"disabled":""}>🖥️</button>
            <button class="tileBtn" data-act="rdp-win" data-id="${d.id}" title="${esc(t("button.remote_window"))}" ${d.status!=="online"?"disabled":""}>🪟</button>
            <button class="tileBtn" data-act="open-dash" data-id="${d.id}" title="${esc(t("button.dashboard"))}" ${d.status!=="online"?"disabled":""}>📊</button>
          </div>
          ${d.status === "online"
            ? `<button class="shutdownBtn" data-act="shutdown" data-id="${d.id}">${esc(t("devices.shutdown"))}</button>`
            : `<button class="wakeBtn" data-act="wake" data-id="${d.id}" ${d.status==="waking"||!d.enabled?"disabled":""}>${esc(t("devices.wake"))}</button>`}
        </div>`).join("")}</div>`
    : `<div class="panel">${devs.map((d, i) => `
        ${i ? '<div class="sep"></div>' : ""}
        <div class="row64" data-press data-id="${d.id}">
          <span class="dot ${dotCls(d)}" title="${esc(statusName(d))}"></span>
          <div class="rowInfo"><div class="rowTitle ${d.enabled?"":"dis"}">${esc(d.name)}${nameSuffix(d)}</div>
            <span class="mono">${esc([d.ip, d.mac].filter(Boolean).join(" · "))}</span></div>
          <div class="tiles">
            <button class="tileBtn" data-act="rdp-full" data-id="${d.id}" ${d.status!=="online"?"disabled":""}>🖥️</button>
            <button class="tileBtn" data-act="rdp-win" data-id="${d.id}" ${d.status!=="online"?"disabled":""}>🪟</button>
            <button class="tileBtn" data-act="open-dash" data-id="${d.id}" ${d.status!=="online"?"disabled":""}>📊</button>
            <button class="tileBtn" data-act="edit-dev" data-id="${d.id}">✏️</button>
          </div>
        </div>`).join("")}</div>`;
  $("#s-devices").innerHTML = `
    <div class="toprow"><div><div class="pageTitle">${esc(t("nav.devices"))}</div>
      <div class="pageSub">${esc(t("devices.summary", { total: state.devices.length, online }))}</div></div></div>
    <div class="toolbar">
      <button class="iconBtn" data-act="view" title="${esc(t(grid ? "devices.viewList" : "devices.viewGrid"))}">${grid ? "☰" : "▦"}</button>
      <button class="iconBtn" data-act="refresh" title="${esc(t("devices.refresh"))}">⟳</button>
      <span class="spacer"></span>
      <button class="btn primary small" data-act="wake-all">${esc(t("devices.wake_all"))}</button>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:10px">
      <select class="sel" data-act="sort" style="flex:0 0 auto">
        ${["name","ip","mac","status"].map(s => `<option value="${s}" ${state.ui.sort===s?"selected":""}>${esc(t("sort."+s))}</option>`).join("")}
      </select>
      <div class="search" style="flex:1;margin-bottom:0">🔍<input placeholder="${esc(t("devices.search"))}" value="${esc(state.ui.search)}" data-act="search"></div>
    </div>
    ${devs.length === 0 ? `<div class="empty">${esc(t("devices.empty"))}</div>` : cards}`;
}

/* ══════════════════════════ Render: Verwalten ═════════════════════════════ */
function renderManage() {
  const devs = state.devices
    .filter(d => !state.ui.manageSearch || (d.name+" "+d.ip+" "+d.mac+" "+d.username).toLowerCase().includes(state.ui.manageSearch.toLowerCase()))
    .sort((a,b) => a.name.localeCompare(b.name));
  const sc = state.scan;
  $("#s-manage").innerHTML = `
    <div class="toprow"><div><div class="pageTitle">${esc(t("nav.manage"))}</div>
      <div class="pageSub">${esc(t("manage.subtitle"))}</div></div></div>
    <div class="sectionHeading">${esc(t("manage.sec.devices"))}</div>
    <div class="toolbar" style="flex-wrap:wrap">
      <button class="btn primary small" data-act="add-device">${esc(t("manage.add"))}</button>
      <button class="btn small" data-act="import">${esc(t("manage.import"))}</button>
      <button class="btn small" data-act="export">${esc(t("manage.export"))}</button>
    </div>
    <div class="search">🔍<input placeholder="${esc(t("devices.search"))}" value="${esc(state.ui.manageSearch)}" data-act="manage-search"></div>
    ${devs.length === 0 ? `<div class="empty">${esc(t("devices.empty"))}</div>` :
    `<div class="panel">${devs.map((d, i) => `
      ${i ? '<div class="sep"></div>' : ""}
      <div class="row64">
        <span class="dot ${dotCls(d)}" title="${esc(statusName(d))}"></span>
        <div class="rowInfo"><div class="rowTitle ${d.enabled?"":"dis"}">${esc(d.name)}${nameSuffix(d)}</div>
          <span class="mono">${esc([d.ip, d.mac].filter(Boolean).join(" · "))}</span></div>
        <div class="tiles">
          <button class="tileBtn" data-act="edit-dev" data-id="${d.id}">✏️</button>
          <button class="tileBtn tileDanger" data-act="del-dev" data-id="${d.id}">🗑️</button>
        </div>
      </div>`).join("")}</div>`}
    <div class="sectionHeading">${esc(t("manage.sec.scan"))}</div>
    <div class="panel">${state.scan.ifaces.map((f, i) => `
      ${i ? '<div class="sep"></div>' : ""}
      <div class="togRow"><div class="mono" style="font-size:12px">${esc(f.ip)}/${esc(f.prefix)}${f.dns ? esc(t("manage.dns", { dns: f.dns })) : ""}</div>
        <div class="toggle ${f.checked ? "on" : ""}" data-act="iface-toggle" data-i="${i}"></div></div>`).join("")}
    </div>
    <div class="toolbar" style="margin-top:10px">
      <button class="btn primary small" data-act="scan" ${sc.running?"disabled":""}>${esc(t("manage.scan.start"))}</button>
    </div>
    <div class="pageSub">${sc.running ? '<span class="spin"></span> ' + esc(t("manage.scan.running"))
      : sc.shown ? esc(t("manage.scan.done", { count: sc.results.length }))
      : esc(t("manage.scan.initial"))}</div>
    ${sc.running ? '<div class="progress"><i id="scanProg"></i></div>' : ""}
    ${sc.shown && sc.results.length ? `<div class="panel" id="scanResults" style="margin-top:10px">${sc.results.map((r, i) => `
      ${i ? '<div class="sep"></div>' : ""}
      <div class="row64">
        <span class="dot dotOnline"></span>
        <div class="rowInfo"><div class="rowTitle">${esc(r.host || "Unknown")}
          <span class="badge ${r.known ? "known" : "new"}">${esc(t(r.known ? "scan.known" : "scan.new"))}</span></div>
          <span class="mono">${esc(r.ip)}${r.mac ? " · " + esc(r.mac) : ""}</span></div>
        <button class="btn small" style="border-color:var(--accent);color:var(--accent)" data-act="scan-add" data-i="${i}">${esc(t("manage.add.btn"))}</button>
      </div>`).join("")}</div>` : ""}`;
}

/* ══════════════════════════ Render: Zeitplan ══════════════════════════════ */
function renderSched() {
  let list = [...state.schedules].sort((a,b) => a.time.localeCompare(b.time));
  const q = state.ui.schedSearch.toLowerCase();
  if (q) list = list.filter(s => {
    const d = byId(s.deviceId);
    return ((d?.name || "") + " " + s.time + " " + t("sched." + s.action) + " " + daysText(s.days)).toLowerCase().includes(q);
  });
  $("#s-sched").innerHTML = `
    <div class="toprow"><div><div class="pageTitle">${esc(t("nav.schedule"))}</div>
      <div class="pageSub">${esc(t("sched.subtitle"))}</div></div></div>
    <div class="toolbar">
      <button class="btn primary small" data-act="add-sched">${esc(t("sched.add"))}</button>
    </div>
    <div class="search">🔍<input placeholder="${esc(t("sched.search"))}" value="${esc(state.ui.schedSearch)}" data-act="sched-search"></div>
    ${list.length === 0 ? `<div class="empty">${esc(t("sched.empty"))}</div>` :
    `<div class="panel">${list.map((s, i) => {
      const d = byId(s.deviceId);
      return `${i ? '<div class="sep"></div>' : ""}
      <div class="row64">
        <div class="toggle ${s.enabled ? "on" : ""}" data-act="sc-toggle" data-id="${s.id}"></div>
        <div class="rowInfo"><div class="rowTitle ${s.enabled?"":"dis"}">${esc(d ? d.name : t("sc.unknown"))}</div>
          <span class="mono">${esc(daysText(s.days))} · ${esc(s.time)} · ${esc(t("sched." + s.action))}</span></div>
        <div class="tiles">
          <button class="tileBtn" data-act="sc-edit" data-id="${s.id}">✏️</button>
          <button class="tileBtn tileDanger" data-act="sc-del" data-id="${s.id}">🗑️</button>
        </div>
      </div>`; }).join("")}</div>`}`;
}

/* ══════════════════════════ Render: Protokolle ════════════════════════════ */
const LVL_TXT = { info: "INFO", warn: "WARN", error: "FEHLER" };
const LVL_CLS = { info: "badgeInfo", warn: "badgeWarn", error: "badgeError" };
function renderLogs() {
  const q = state.ui.logSearch.toLowerCase();
  const rows = state.logs.filter(l =>
    (state.ui.logLevel === "all" || l.level === state.ui.logLevel) &&
    (!q || (l.msg + " " + l.device).toLowerCase().includes(q)));
  const fmt = ts => { const d = new Date(ts);
    return String(d.getDate()).padStart(2,"0") + "." + String(d.getMonth()+1).padStart(2,"0") + " " +
           String(d.getHours()).padStart(2,"0") + ":" + String(d.getMinutes()).padStart(2,"0"); };
  $("#s-logs").innerHTML = `
    <div class="toprow"><div><div class="pageTitle">${esc(t("nav.logs"))}</div>
      <div class="pageSub">${esc(t("logs.subtitle"))}</div></div></div>
    <div class="search">🔍<input placeholder="${esc(t("logs.search"))}" value="${esc(state.ui.logSearch)}" data-act="log-search"></div>
    <div class="toolbar">
      <select class="sel" data-act="log-level" style="flex:1">
        <option value="all" ${state.ui.logLevel==="all"?"selected":""}>${esc(t("logs.level.all"))}</option>
        <option value="info" ${state.ui.logLevel==="info"?"selected":""}>INFO</option>
        <option value="warn" ${state.ui.logLevel==="warn"?"selected":""}>WARN</option>
        <option value="error" ${state.ui.logLevel==="error"?"selected":""}>FEHLER</option>
      </select>
      <button class="btn small" data-act="log-export">${esc(t("logs.export"))}</button>
    </div>
    ${rows.length === 0 ? `<div class="empty">${esc(t("logs.empty"))}</div>` :
    `<div class="panel">${rows.map((l, i) => `
      ${i ? '<div class="sep"></div>' : ""}
      <div class="logrow">
        <span class="lvl ${LVL_CLS[l.level]}">${LVL_TXT[l.level]}</span>
        <span class="t">${fmt(l.ts)}</span>
        ${l.device && l.device !== "—" && l.device !== t("logs.unknown") ? `<span class="dv">${esc(l.device)} ·</span>` : ""}
        <span class="m" title="${esc(l.msg)}">${esc(l.msg)}</span>
      </div>`).join("")}</div>`}`;
}

/* ══════════════════════════ Render: Einstellungen (+ Info unten) ══════════ */
function renderSettings() {
  const s = state.settings;
  $("#s-set").innerHTML = `
    <div class="toprow"><div><div class="pageTitle">${esc(t("nav.settings"))}</div>
      <div class="pageSub">${esc(t("set.subtitle"))}</div></div></div>
    <div class="field"><label>${esc(t("set.broadcast_ip"))}</label>
      <input class="inp" id="st-ip" value="${esc(s.broadcastIp)}" placeholder="255.255.255.255"></div>
    <div class="field"><label>${esc(t("set.broadcast_port"))}</label>
      <input class="inp" id="st-port" type="number" min="1" max="65535" value="${s.broadcastPort}"></div>
    <div class="field"><label>${esc(t("set.language"))}</label>
      <select class="sel" id="st-lang" style="width:100%">
        <option value="de" ${s.language==="de"?"selected":""}>Deutsch</option>
        <option value="en" ${s.language==="en"?"selected":""}>English</option>
        <option value="fr" ${s.language==="fr"?"selected":""}>Français</option>
        <option value="es" ${s.language==="es"?"selected":""}>Español</option></select></div>
    <div class="field"><label>${esc(t("set.display"))}</label>
      <select class="sel" id="st-disp" style="width:100%">
        <option value="auto" ${s.displayMode==="auto"?"selected":""}>${esc(t("disp.auto"))}</option>
        <option value="light" ${s.displayMode==="light"?"selected":""}>${esc(t("disp.light"))}</option>
        <option value="dark" ${s.displayMode==="dark"?"selected":""}>${esc(t("disp.dark"))}</option></select></div>
    <div class="togRow" style="padding:6px 0"><div>${esc(t("set.auto_update"))}</div>
      <div class="toggle ${s.autoUpdate?"on":""}" data-act="set-toggle" data-key="autoUpdate"></div></div>
    <div class="field" style="margin-top:12px"><label>${esc(t("set.interval"))}</label>
      <select class="sel" id="st-int" style="width:100%">
        <option value="24" ${s.interval==="24"?"selected":""}>${esc(t("int.day"))}</option>
        <option value="168" ${s.interval==="168"?"selected":""}>${esc(t("int.week"))}</option>
        <option value="720" ${s.interval==="720"?"selected":""}>${esc(t("int.month"))}</option></select></div>
    <div class="field"><label>${esc(t("set.max_logs"))}</label>
      <input class="inp" id="st-maxlogs" type="number" min="10" max="10000" step="50" value="${s.maxLogs}"></div>
    <div class="infoBlock">${esc(t("set.info"))}</div>
    <div class="toolbar" style="justify-content:flex-end;margin-top:14px">
      <button class="btn small" data-act="set-reset">${esc(t("set.reset"))}</button>
      <button class="btn primary small" data-act="set-save">${esc(t("set.save"))}</button>
    </div>

    <div class="sep" style="margin:20px 0 0"></div>
    <div class="aboutBlock">
      <div class="logoTile">⚡</div>
      <div class="aboutTitle">${esc(t("about.name"))}</div>
      <div class="aboutVer">${esc(t("about.version", { v: "2.3.0" }))} · Android</div>
      <div class="aboutText">${esc(t("about.desc"))}</div>
      <div style="display:flex;gap:10px;justify-content:center">
        <button class="btn primary small" data-act="upd-check">${esc(t("upd.check"))}</button>
        <a class="btn small" style="text-decoration:none;display:inline-block" href="https://github.com/pdchristian/WOL/releases" target="_blank" rel="noopener">${esc(t("upd.changelog"))}</a>
      </div>
      <div class="updStatus" id="updStatus">${state.upd}</div>
    </div>`;
}

/* ══════════════════════════ Render: Dashboard (📊, kein Nav-Eintrag) ══════ */
function renderDash(dir) {
  const d = byId(state.ui.dashDeviceId);
  if (!d) { $("#s-dash").innerHTML = `<div class="empty">${esc(t("devices.empty"))}</div>`; return; }
  const dlist = dashDevicesOrdered();
  const dpos = dlist.findIndex(x => x.id === d.id);
  const on = d.status === "online";
  const pill = on ? "pillOnline" : d.status === "offline" ? "pillOffline" : "pillUnknown";
  let warn = "";
  if (!on) warn = `<div class="warnbox err">${esc(t("dash.unreach", { ip: d.ip || "?" }))}</div>`;
  else if (!d.username) warn = `<div class="warnbox warn">${esc(t("dash.creds"))}</div>`;
  else if (d.dashError) warn = `<div class="warnbox err">${esc(t("dash.err", { msg: d.dashError }))}</div>`;
  const showMetrics = on && d.username && !!d.metrics;
  const m = showMetrics ? d.metrics : null;
  const svc = d.watch.map(w => ({ w, p: procFor(d, w) }));
  const models = (m && m.processes || []).flatMap(p => p.models || []);
  const anyReady = (m && m.processes || []).some(p => p.apiPortOpen);
  const batches = currentBatches();
  const sb = selBatchObj();
  const metricCard = (key, val, detail) => `
    <div class="metricCard">
      <div class="mt"><i style="background:var(--gauge-${key})"></i>${esc(t("m." + key))}</div>
      <div class="gauge" data-g="${key}" style="--v:${val ?? 0};--c:var(--gauge-${key})">
        <div class="in"><b data-gv="${key}">${val ?? "–"}%</b></div></div>
      <div class="mdet">${esc(detail)}</div>
      ${key !== "vram" ? `<div data-spark="${key}">${sparkSvg(d.spark[key], `var(--gauge-${key})`)}</div>` : ""}
    </div>`;
  const anim = dir === "left" ? " dashInLeft" : dir === "right" ? " dashInRight" : "";
  $("#s-dash").innerHTML = `<div class="dashSwap${anim}">
    <div class="toolbar" style="align-items:center">
      <button class="btn small" data-act="nav-devices">${esc(t("dash.back"))}</button>
      <span class="spacer"></span>
      <span class="mono" style="font-size:11px">${esc(t("dash.interval"))}</span>
      <select class="sel" data-act="dash-int" style="padding:6px 8px">
        ${[2000,3000,5000,10000].map(v => `<option value="${v}" ${state.ui.dashInterval===v?"selected":""}>${v/1000} s</option>`).join("")}
      </select>
    </div>
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
      <div class="pageTitle" style="font-size:19px">${esc(d.name)}</div>
      ${dlist.length > 1 ? `<span class="pill dashPos mono" title="${esc(t("dash.swipe"))}">${dpos + 1}/${dlist.length}</span>` : ""}
      <span class="pill ${pill}">${esc(statusName(d))}</span>
    </div>
    <div class="mono">${esc([d.ip, d.mac].filter(Boolean).join(" · "))} · ${m && m.protocol >= 3 ? esc(t("hostv", { v: m.protocol })) : "—"}</div>
    ${warn}
    ${showMetrics ? `
      <div class="sectionHeading" style="display:flex;justify-content:space-between;align-items:baseline">
        <span>${esc(t("dash.svc"))}</span><span style="font-size:11px;font-weight:400">${esc(t("dash.svc.sub"))}</span></div>
      ${d.watch.length ? `<div class="panel">${svc.map((s, i) => `
        ${i ? '<div class="sep"></div>' : ""}
        <div class="row64" style="min-height:56px">
          <span style="font-size:20px">${s.w.toLowerCase().includes("llama") ? "🦙" : "⚙️"}</span>
          <div class="rowInfo"><div class="rowTitle" style="font-size:13px">${esc(s.w.split(":")[0])}
            ${s.w.toLowerCase().includes("llama") && d.gpuHigh >= 2 ? `<span class="chip probe" style="margin-left:6px;font-size:9px" id="infBadge">${esc(t("dash.inferenz"))}</span>` : ""}</div>
            <span class="mono">${esc(svcLine(d, s.w))}</span>
            ${s.p && s.p.models && s.p.models.length && s.p.apiPortOpen ? `<span class="mono">${esc(t("dash.model", { m: s.p.models[0] }))}${s.p.models.length > 1 ? ` +${s.p.models.length - 1}` : ""}</span>` : ""}
          </div>
        </div>`).join("")}</div>`
      : `<div class="pageSub">${esc(t("dash.svc.none"))}</div>`}
      ${m ? `
      <div class="mono" id="dashUptime" style="margin:10px 0 0">${esc(t("d.uptime", { v: fmtUptime(m.uptime || 0) }))}</div>
      <div class="metrics">
        ${metricCard("cpu", m.cpu, t("d.cores", { n: m.cpuCount }))}
        ${metricCard("ram", m.ram, t("d.gb", { used: m.ramUsedGB, total: m.ramTotalGB }))}
        ${metricCard("gpu", m.gpu, m.gpuName || t("d.na"))}
        ${metricCard("vram", m.vram, m.vramTotalGB ? t("d.gb", { used: m.vramUsedGB, total: m.vramTotalGB }) : t("d.na"))}
      </div>` : ""}` : ""}
    <div class="sectionHeading" style="display:flex;justify-content:space-between;align-items:baseline">
      <span>${esc(t("batch.title"))}</span>
      <button class="btn small" data-act="batch-new">${esc(t("batch.new"))}</button></div>
    ${batches.length ? `<div class="panel">${batches.map(b => `
      <div class="batchItem ${state.ui.selBatch === b.id ? "sel" : ""}" data-act="batch-sel" data-id="${b.id}">
        ${esc(b.name)}<div class="mono">${esc(b.script)} · ${b.timeout} s</div></div>
      <div class="sep"></div>`).join("")}</div>
      <div class="toolbar" style="margin-top:8px">
        <button class="btn small" data-act="batch-dup">${esc(t("batch.dup"))}</button>
        <button class="btn small danger" data-act="batch-del">${esc(t("batch.del"))}</button>
      </div>`
    : `<div class="pageSub">${esc(t("batch.empty"))}</div>`}
    ${sb ? `
    <div class="panel" style="padding:12px;margin-top:10px">
      <div class="field"><input class="inp" id="b-name" value="${esc(sb.name)}" placeholder="${esc(t("batch.newname"))}"></div>
      <textarea class="code" id="b-script" placeholder="@echo off">${esc(sb.script)}</textarea>
      <div class="toolbar" style="margin:10px 0 0;align-items:center">
        <span class="mono" style="font-size:11px">${esc(t("batch.timeout"))}</span>
        <input class="inp" id="b-timeout" type="number" min="5" max="3600" value="${sb.timeout}" style="width:76px;padding:6px 8px">
        <span class="spacer"></span>
        <button class="btn small" data-act="batch-save" ${state.ui.selBatch===sb.id?"":""} >${esc(t("batch.save"))}</button>
        <button class="btn small primary" data-act="batch-run">${esc(t("batch.run"))}</button>
      </div>
      <div class="togRow" style="padding:10px 0 0"><div style="font-size:12px">${esc(t("batch.allow"))}</div>
        <div class="toggle ${d.allow_batch?"on":""}" data-act="batch-allow"></div></div>
      ${!d.allow_batch ? `<div class="hint" style="font-size:11px;color:var(--unknown);margin-top:6px">${esc(t("batch.disabled"))}</div>` : ""}
    </div>
    <div class="sectionHeading" style="display:flex;justify-content:space-between;align-items:baseline">
      <span>${esc(t("batch.out"))}</span>
      <button class="btn small" data-act="con-clear">${esc(t("batch.clear"))}</button></div>
    <div class="console">${state.con.lines.map(l =>
      `<div class="${/fehler|error/i.test(l) ? "err" : ""}">${esc(l)}</div>`).join("")}
      ${state.con.running ? `<div class="dim">${esc(t("batch.running"))}</div>` : ""}
      ${state.con.exit != null ? `<div class="dim">${esc(t("batch.exit", { c: state.con.exit }))} · ${esc(t("batch.dur", { s: state.con.dur }))}</div>` : ""}</div>` : ""}
  </div>`;
}

/* ══════════════════════════ Theme / Sprache ═══════════════════════════════ */
function applyTheme() {
  const mode = state.settings.displayMode;
  const eff = mode === "auto"
    ? (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark") : mode;
  state.theme = eff;
  document.documentElement.dataset.theme = eff;
}
matchMedia("(prefers-color-scheme: light)").addEventListener?.("change", () => {
  if (state.settings.displayMode === "auto") applyTheme();
});

function renderAll() {
  applyTheme();
  document.querySelectorAll("[data-t]").forEach(el => el.textContent = t(el.dataset.t));
  renderDevices(); renderManage(); renderSched(); renderLogs(); renderSettings(); renderDash();
}

/* ══════════════════════════ Navigation ════════════════════════════════════ */
function go(screen) {
  state.ui.screen = screen;
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  $("#s-" + screen).classList.add("active");
  document.querySelectorAll(".nav").forEach(n => n.classList.toggle("active", n.dataset.nav === screen));
  if (screen === "logs") renderLogs();
  if (screen === "dash") renderDash();
  if (screen === "devices") renderDevices();
}

/* ══════════════════════════ Event-Delegation ══════════════════════════════ */
document.addEventListener("click", ev => {
  const nav = ev.target.closest("[data-nav]");
  if (nav) return go(nav.dataset.nav);
  const el = ev.target.closest("[data-act]");
  if (!el) return;
  const act = el.dataset.act, id = el.dataset.id;
  switch (act) {
    /* ── Geräte ── */
    case "view": state.ui.deviceView = state.ui.deviceView === "grid" ? "list" : "grid"; renderDevices(); break;
    case "refresh": refreshStatus(); toast(t("devices.refresh") + " …"); break;
    case "wake": wakeDevice(byId(id)); break;
    case "shutdown": openShutdownConfirm(byId(id)); break;
    case "wake-all": {
      const targets = state.devices.filter(d => d.enabled && d.status !== "online" && d.status !== "waking");
      if (!targets.length) break;
      openConfirm(t("wakeall.title"), t("wakeall.message", { count: targets.length }), () => {
        closeSheet();
        targets.forEach(d => setRt(d.id, { status: "waking" }));
        renderDevices();
        Native.call("wakeAll", {});
      });
      break; }
    case "rdp-full": doRemote(id, "full"); break;
    case "rdp-win": doRemote(id, "win"); break;
    case "open-dash": state.ui.dashDeviceId = id; state.ui.selBatch = null; state.con = { lines:[],running:false,exit:null,dur:null,timer:null }; go("dash"); break;
    case "nav-devices": go("devices"); break;
    case "edit-dev": openDeviceSheet(id); break;
    case "del-dev": deleteDevice(id); break;
    case "dev-save": saveDeviceFromSheet(); break;
    /* ── Long-Press-Menü ── */
    case "m-rdp": closeSheet(); doRemote(id, el.dataset.mode); break;
    case "m-dash": closeSheet(); state.ui.dashDeviceId = id; go("dash"); break;
    case "m-wake": closeSheet(); wakeDevice(byId(id)); break;
    case "m-shutdown": closeSheet(); openShutdownConfirm(byId(id)); break;
    case "m-ping": closeSheet(); pingDevice(byId(id)); break;
    case "m-edit": closeSheet(); openDeviceSheet(id); break;
    case "m-del": closeSheet(); deleteDevice(id); break;
    /* ── Verwalten ── */
    case "add-device": openDeviceSheet(null); break;
    case "import": Native.call("importDevices", {}); break;
    case "export": Native.call("exportDevices", {}); break;
    case "scan": startScan(); break;
    case "scan-add": { const r = state.scan.results[+el.dataset.i]; scanAdd(r.host, r.ip, r.mac); break; }
    case "sheet-close": closeSheet(); break;
    case "confirm-yes": { const fn = state.ui.confirmFn; state.ui.confirmFn = null; closeSheet(); fn && fn(); break; }
    case "edit-toggle": {
      const e = state.ui.editing;
      e[el.dataset.key] = !e[el.dataset.key];
      el.classList.toggle("on"); break; }
    /* ── Zeitplan ── */
    case "add-sched": openSchedSheet(null); break;
    case "sc-toggle": { const s = state.schedules.find(x => x.id === id);
      Native.call("saveSchedule", { id: s.id, deviceId: s.deviceId, action: s.action,
        time: s.time, days: s.days, enabled: !s.enabled }).then(res => {
        if (res.ok) { state.schedules = res.data || []; renderSched(); }
        else toast(String(res.error || "error"), true);
      }); break; }
    case "sc-edit": openSchedSheet(id); break;
    case "sc-save": saveSchedFromSheet(); break;
    case "sc-del": {
      const s = state.schedules.find(x => x.id === id); const d = byId(s.deviceId);
      openConfirm(t("sched.del.title"), t("sched.del.message", { name: d ? d.name : t("sc.unknown") }), () => {
        Native.call("deleteSchedule", { id }).then(res => {
          if (!res.ok) { toast(String(res.error || "error"), true); return; }
          state.schedules = res.data || [];
          closeSheet(); renderSched(); toast(t("sched.del.title") + " ✓");
        });
      }, "danger");
      break; }
    case "sc-day": {
      const e = state.ui.editing, day = el.dataset.day;
      e.days = e.days.includes(day) ? e.days.filter(x => x !== day) : [...e.days, day];
      el.classList.toggle("run"); el.classList.toggle("off"); break; }
    /* ── Protokolle ── */
    case "log-export": Native.call("exportCsv", {}); break;
    /* ── Einstellungen ── */
    case "set-toggle": {
      const k = el.dataset.key; state.settings[k] = !state.settings[k]; el.classList.toggle("on"); break; }
    case "set-save": {
      const ip = $("#st-ip").value.trim(), port = +$("#st-port").value;
      if (!ip) { openAlert(t("err.ip_missing"), t("err.ip_msg")); break; }
      if (!RE_IP.test(ip) && !RE_HOST.test(ip)) { openAlert(t("err.ip_title"), t("err.ip_msg")); break; }
      if (!(port >= 1 && port <= 65535)) { openAlert(t("err.port_title"), t("err.port_msg")); break; }
      const next = {
        broadcastIp: ip, broadcastPort: port,
        language: $("#st-lang").value, displayMode: $("#st-disp").value,
        autoUpdate: state.settings.autoUpdate, interval: $("#st-int").value,
        maxLogs: +$("#st-maxlogs").value || 100,
      };
      Native.call("saveSettings", next).then(res => {
        if (!res.ok) { toast(String(res.error || "error"), true); return; }
        Object.assign(state.settings, next);
        state.lang = state.settings.language || systemLang();
        applyTheme(); renderAll();
        openAlert(t("set.saved.title"), t("set.saved.msg"));
      });
      break; }
    case "set-reset":
      openConfirm(t("set.reset.title"), t("set.reset.msg"), () => {
        Native.call("resetSettings", {}).then(res => {
          if (!res.ok) { toast(String(res.error || "error"), true); return; }
          Native.call("snapshot", {}).then(s => { applySnapshot(s); closeSheet(); renderAll(); });
        });
      });
      break;
    /* ── Info / Update ── */
    case "upd-check": {
      state.upd = `<span class="spin"></span> ${esc(t("upd.checking"))}`;
      $("#updStatus").innerHTML = state.upd;
      Native.call("updateCheck", {}).then(res => {
        if (!res.ok) { state.upd = esc(t("upd.err", { msg: t("upd.err.msg") })); }
        else if (res.data.state === "update") state.upd = esc(t("upd.new", { v: res.data.version }));
        else if (res.data.state === "latest") state.upd = esc(t("upd.ok"));
        else state.upd = esc(t("upd.err", { msg: t("upd.err.msg") }));
        const el2 = $("#updStatus"); if (el2) el2.textContent = state.upd;
      });
      break; }
    /* ── Dashboard / Batches ── */
    case "batch-new": {
      const d = byId(state.ui.dashDeviceId); if (!d) break;
      const b = { id: "b" + Date.now(), name: t("batch.newname"), script: "@echo off", timeout: 120 };
      d.batches = [...(d.batches || []), b]; state.ui.selBatch = b.id; renderDash();
      persistBatches(d); break; }
    case "batch-sel": state.ui.selBatch = id; state.con = { lines:[],running:false,exit:null,dur:null,timer:null }; renderDash(); break;
    case "batch-dup": { const d = byId(state.ui.dashDeviceId); const b = selBatchObj();
      if (d && b) { const c = { ...b, id: "b" + Date.now(), name: b.name + " (Kopie)" };
        d.batches = [...d.batches, c]; state.ui.selBatch = c.id; renderDash(); persistBatches(d); }
      break; }
    case "batch-del": { const d = byId(state.ui.dashDeviceId);
      if (d) { d.batches = (d.batches || []).filter(b => b.id !== state.ui.selBatch); state.ui.selBatch = null;
        renderDash(); persistBatches(d, t("dev.saved")); }
      break; }
    case "batch-save": {
      const d = byId(state.ui.dashDeviceId); const b = selBatchObj(); if (!d || !b) break;
      b.name = $("#b-name").value.trim() || b.name; b.script = $("#b-script").value;
      b.timeout = clamp(+$("#b-timeout").value || 120, 5, 3600);
      renderDash(); persistBatches(d, t("dev.saved")); break; }
    case "batch-run": runBatch(); break;
    case "batch-allow": { const d = byId(state.ui.dashDeviceId); if (!d) break;
      d.allow_batch = !d.allow_batch; renderDash(); persistBatches(d); break; }
    case "con-clear": state.con = { lines:[],running:false,exit:null,dur:null,timer:null }; renderDash(); break;
  }
});
document.addEventListener("change", ev => {
  const el = ev.target.closest("[data-act]"); if (!el) return;
  switch (el.dataset.act) {
    case "sort": state.ui.sort = el.value; renderDevices(); break;
    case "log-level": state.ui.logLevel = el.value; renderLogs(); break;
    case "dash-int": state.ui.dashInterval = +el.value; restartDashTimer(); renderDash(); break;
  }
});
document.addEventListener("input", ev => {
  const el = ev.target.closest("[data-act]"); if (!el) return;
  const act = el.dataset.act;
  const keepFocus = (fn) => { const pos = el.selectionStart; fn(); };
  if (act === "search") { state.ui.search = el.value; renderDevices();
    const n = document.querySelector('[data-act="search"]'); if (n) { n.focus(); n.setSelectionRange(el.selectionStart, el.selectionStart); } }
  if (act === "manage-search") { state.ui.manageSearch = el.value; renderManage();
    const n = document.querySelector('[data-act="manage-search"]'); if (n) { n.focus(); n.setSelectionRange(el.selectionStart, el.selectionStart); } }
  if (act === "sched-search") { state.ui.schedSearch = el.value; renderSched();
    const n = document.querySelector('[data-act="sched-search"]'); if (n) { n.focus(); n.setSelectionRange(el.selectionStart, el.selectionStart); } }
  if (act === "log-search") { state.ui.logSearch = el.value; renderLogs();
    const n = document.querySelector('[data-act="log-search"]'); if (n) { n.focus(); n.setSelectionRange(el.selectionStart, el.selectionStart); } }
});
/* Interface-Toggles (Scan) – Klick auf Toggle */
document.addEventListener("click", ev => {
  const el = ev.target.closest('[data-act="iface-toggle"]');
  if (!el) return;
  const f = state.scan.ifaces[+el.dataset.i]; f.checked = !f.checked; renderManage();
});

/* Long-Press = Rechtsklick-Kontextmenü auf Karten/Zeilen */
document.addEventListener("pointerdown", ev => {
  const host = ev.target.closest("[data-press]");
  if (!host || ev.target.closest("button")) return;
  state.ui.pressTimer = setTimeout(() => { openDeviceMenu(host.dataset.id); Native.call("vibrate", { ms: 12 }); }, 550);
});
["pointerup","pointercancel","pointermove"].forEach(evt =>
  document.addEventListener(evt, () => clearTimeout(state.ui.pressTimer)));

$("#overlay").addEventListener("click", closeSheet);

/* Zurück-Taste (nativ): offenes Sheet schließen, sonst nichts tun. */
window.onNativeBack = () => {
  if ($("#sheet").classList.contains("open") || $("#overlay").classList.contains("open")) closeSheet();
};

/* ══════════════════════════ Native-Events ════════════════════════════════ */
Native.on("scan-progress", ev => {
  const bar = $("#scanProg");
  if (bar && ev.total) bar.style.width = Math.round(100 * ev.done / ev.total) + "%";
});
Native.on("scan-found", ev => {
  const known = state.devices.some(d => d.ip === ev.ip || (ev.mac && d.mac === ev.mac));
  state.scan.results.push({ ip: ev.ip, host: ev.host, mac: ev.mac || "", known });
  const list = $("#scanResults");
  if (list) {
    const row = document.createElement("div");
    row.innerHTML = `<div class="sep"></div><div class="row64">
      <span class="dot dotOnline"></span>
      <div class="rowInfo"><div class="rowTitle">${esc(ev.host || "Unknown")}
        <span class="badge ${known ? "known" : "new"}">${esc(t(known ? "scan.known" : "scan.new"))}</span></div>
        <span class="mono">${esc(ev.ip)}${ev.mac ? " · " + esc(ev.mac) : ""}</span></div>
      <button class="btn small" style="border-color:var(--accent);color:var(--accent)"
        data-act="scan-add" data-i="${state.scan.results.length - 1}">${esc(t("manage.add.btn"))}</button>
    </div>`;
    list.append(...row.children);
  }
});
Native.on("scan-done", ev => {
  state.scan.running = false; state.scan.shown = true;
  logIt("—", "info", t("manage.scan.done", { count: ev.count }));
  renderManage();
});
Native.on("wake-result", ev => {
  if (ev.ok) toast(t("wol.sent", { name: byId(ev.id)?.name || "" }));
  else { setRt(ev.id, { status: "unknown" }); toast(t("wol.failone", { name: byId(ev.id)?.name || "" }), true); }
  renderDevices();
});
Native.on("wake-all-done", ev => {
  toast(t("wakeall.done", { count: ev.count }));
  setTimeout(refreshStatus, 4000);
});
Native.on("status", ev => {
  const d = byId(ev.id); if (!d) return;
  setRt(d.id, { checking: false, status: ev.online ? "online" : "offline" });
  if (state.ui.screen === "devices") renderDevices();
});
Native.on("status-done", () => {
  state.devices.forEach(d => { if (d.checking) setRt(d.id, { checking: false, status: "offline" }); });
  if (state.ui.screen === "devices") renderDevices();
});
Native.on("exported", ev => toast(t("exp.done", { name: ev.name, count: ev.count })));
Native.on("imported", ev => {
  if (ev.error) { toast(t("imp.err"), true); return; }
  Native.call("snapshot", {}).then(s => { if (s.ok) { applySnapshot(s.data); renderAll(); } });
  toast(t("imp.summary", { added: ev.added || 0, updated: ev.updated || 0, skipped: ev.skipped || 0 }));
});

/* ══════════════════════════ Boot ═════════════════════════════════════════ */
function systemLang() {
  const l = (navigator.language || "de").slice(0, 2).toLowerCase();
  return ["de", "en", "fr", "es"].includes(l) ? l : "de";
}
function applySnapshot(s) {
  applyDevices(s.devices);
  state.schedules = s.schedules || [];
  state.logs = s.logs || [];
  Object.assign(state.settings, s.settings || {});
  state.lang = state.settings.language || systemLang();
}
function boot() {
  Native.call("snapshot", {}).then(res => {
    if (res.ok) { applySnapshot(res.data); renderAll(); refreshStatus(); loadIfaces(); }
    else { renderAll(); toast(String(res.error || "snapshot failed"), true); }
  });
}
boot();
