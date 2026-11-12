# SEO-Release und erneutes Crawling bei Google

Dieser PR bereitet Floorball Stats und die Hauptseite auf erneutes Crawling vor.
Die Einreichung erfolgt **nach dem Merge und dem erfolgreichen Produktionsdeployment**.
Ein PR-Preview darf nicht bei Google eingereicht werden.

## Was sich für Google ändert

- Liga-Titel enthalten Wettbewerb, Männer/Frauen und die volle Saison.
- Alle Lexikon-Detailseiten sind über normale Links erreichbar.
- Produktseiten mit bewertbaren Reviews erhalten Produkt-/Review-Markup. Bewertungswerte
  werden aus den tatsächlich sichtbaren Reviews berechnet; ohne Reviews wird
  keine aggregierte Bewertung ausgezeichnet.
- Zusammengeführte Spieler-URLs zeigen auf eine Hauptidentität und erhalten
  permanente Weiterleitungen. Die Alias-URLs stehen nicht mehr in der Sitemap.
- Technische Stats-Sammelseiten und Newsletter-Bestätigungen werden aus der
  Sitemap entfernt und mit `noindex,follow` versehen.
- Die Sitemaps verwenden dieselben URLs wie die Canonical-Tags. Netlify verändert
  die bestehenden `.html`-Links nicht mehr beim Postprocessing.
- Spieltermine werden nicht mehr als Sitemap-Änderungsdatum ausgegeben. `lastmod`
  erscheint nur bei expliziter, nicht zukünftiger `Modified`-Metadatenangabe.
  Wo ein tatsächlicher Änderungszeitpunkt fehlt, wird das optionale Feld ausgelassen.
- Spielseiten haben eine Überschrift, eine sachliche Zusammenfassung und eine
  lesbare HTML-Torliste. Fehlende Hallen werden nicht durch erfundene Orte ersetzt.
- Stats lädt auf der Startseite nur einen kleinen Terminbereich und den nächsten
  Spieltag pro Division. Alle Saisonspiele bleiben über die Ligaseiten erreichbar.
- Passende Liga-/Streaming- und Lexikon-/Stats-Seiten verlinken aufeinander.

## 1. Nach dem Deployment prüfen

Die folgenden Adressen müssen die neue Version ausliefern:

- [Stats-Sitemap](https://stats.floorballconnect.com/sitemap.xml)
- [Hauptseiten-Sitemap](https://www.floorballconnect.com/sitemap.xml)
- [Stats robots.txt](https://stats.floorballconnect.com/robots.txt)
- [Hauptseiten robots.txt](https://www.floorballconnect.com/robots.txt)
- [SSL-Tabelle](https://stats.floorballconnect.com/category/se-26-27-regular-season.html):
  Seitentitel mit SSL und 2026/2027.
- [Lexikon](https://www.floorballconnect.com/floorball-lexicon/): Begriffe verlinken
  auf eigene Detailseiten.
- [ZONE AIRLIGHT](https://www.floorballconnect.com/floorball-sticks/zone-airlight/):
  sichtbare Bewertungen und Produkt-Markup im [Rich Results Test](https://search.google.com/test/rich-results) prüfen.
- [Alter Spieler-Link](https://stats.floorballconnect.com/player-e66353b67c2ae9ab.html):
  führt dauerhaft auf [Tino von Pritzbuer](https://stats.floorballconnect.com/player-8cfdaa5edf5547b8.html).

Der Test im PR validiert den erzeugten Build. Redirects, Netlify-Postprocessing,
DNS und HTTP-Header müssen nach dem Deployment zusätzlich live geprüft werden.

## 2. Beide Sitemaps einreichen

1. [Google Search Console öffnen](https://search.google.com/search-console).
2. Die Domain-Property `floorballconnect.com` auswählen, falls vorhanden. Sie
   deckt Hauptseite und Stats-Subdomain ab. Alternativ die beiden passenden
   URL-Präfix-Properties verwenden; nötigenfalls zuerst deren Inhaberschaft bestätigen.
3. Unter **Indexierung → Sitemaps** die zwei oben verlinkten Sitemap-Adressen
   einreichen beziehungsweise den bestehenden Eintrag auf erfolgreiche Verarbeitung prüfen.
4. Einreichungsdatum und gemeldete Anzahl erkannter URLs festhalten.

Die Sitemap ist der Weg für die vielen betroffenen URLs. Es ist nicht nötig,
jedes Spiel oder jeden Spieler einzeln einzureichen. Bereits eingereichte
Sitemaps bleiben an derselben Adresse und werden beim nächsten Abruf aktualisiert.

## 3. Einige wichtige Seiten gezielt neu prüfen lassen

In Search Console oben eine vollständige URL eingeben, **Live-URL testen** und
bei erfolgreicher Prüfung **Indexierung beantragen** wählen. Dafür sind die
entsprechenden Rechte in der Property erforderlich.

Zuerst diese Seiten verwenden:

1. [Stats-Startseite](https://stats.floorballconnect.com/)
2. [SSL Männer](https://stats.floorballconnect.com/category/se-26-27-regular-season.html)
3. [SSL Frauen](https://stats.floorballconnect.com/category/sew-26-27-regular-season.html)
4. [Leaders](https://stats.floorballconnect.com/leaders.html)
5. [Hauptseite](https://www.floorballconnect.com/)
6. [Lexikon](https://www.floorballconnect.com/floorball-lexicon/)
7. [Powerplay](https://www.floorballconnect.com/floorball-lexicon/powerplay/)
8. [Stick-Übersicht](https://www.floorballconnect.com/floorball-sticks/)
9. [ZONE AIRLIGHT](https://www.floorballconnect.com/floorball-sticks/zone-airlight/)
10. [Schwedischer Streaming-Guide](https://www.floorballconnect.com/watch-floorball/how-to-watch-swedish-floorball/)

Die Liste liegt auch als [Textdatei zum Kopieren](google-reindex-urls.txt) vor.
Google begrenzt einzelne Anträge. Falls das Tageskontingent erschöpft ist,
später fortsetzen; wiederholte Anträge für dieselbe URL beschleunigen nichts.

**Nicht einreichen:** Spieler-Aliase, Bestätigungsseiten, technische Sammelseiten,
Build-Unterordner, Netlify-Preview-Adressen oder die alte Netlify-Hauptdomain.
Ein erwartetes `noindex` bei solchen Seiten ist kein Grund, es zu entfernen.

## 4. Nachkontrolle

Nach einigen Tagen beziehungsweise Wochen prüfen:

- Sind beide Sitemaps erfolgreich verarbeitet?
- Wählt Google bei Stichproben die angegebene kanonische URL?
- Werden Alias-URLs als Weiterleitungen erkannt?
- Sind die Lexikonseiten entdeckt und crawlfähig?
- Welche Produktseiten erhalten gültige Review-/Produkt-Erweiterungen?
- Wie entwickeln sich Impressionen und Klickrate für SSL, F-Liiga, Bundesliga,
  konkrete Produkte und Trainingsbegriffe? Zeiträume gleicher Länge vergleichen.

Es gibt keinen Schalter für eine garantierte vollständige Neuindexierung. Ein
Crawling-Antrag garantiert weder sofortige Aufnahme noch ein bestimmtes Ranking.
Quelle: [Google: erneutes Crawling beantragen](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl),
[Google: Sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).

## Technische Freigabe vor dem Merge

```sh
python -m pytest -q
python -m pelican content -o output -s publishconf.py
python scripts/check_seo.py output --report /tmp/floorball-seo-check.json
```

Der Build verwendet vorhandene veröffentlichte Inhalte, führt keinen Liga-Refresh
aus und benötigt für die SEO-Korrekturen keine neuen Datenbankzugriffe. Ein regulär
konfigurierter Hauptseiten-Build kann wie bisher Notion-Inhalte synchronisieren.
Der lokale Check prüft Metadaten, Canonicals, Sitemap-Ziele, interne Links,
gültiges JSON-LD und die Erreichbarkeit der Lexikonseiten. `output/seo-report.json`
dokumentiert ausgeschlossene Stats-URLs und Spieler-Aliase.

## Redaktionelle Folgeschritte

Nicht durch technische Änderungen zu ersetzen: fehlende Produktreviews sammeln,
Erfahrungsberichte und Vergleiche verfassen, Streamingpreise und Deals anhand der
Originalquellen neu prüfen, echte Änderungszeitpunkte aus dem Veröffentlichungs-
beziehungsweise Datenmodell bereitstellen und neue Themen-/Liga-Einstiege anhand
von Suchdaten auswählen. Bestehende Bewertungen, Preise und Erfahrungen wurden
nicht erfunden oder automatisch neu geschrieben.
