# DCS Server Bot Operations Center — instrukcja PL

Integracja łączy Home Assistanta z oficjalnym pluginem RestAPI projektu
DCSServerBot. Monitorowanie działa zawsze, a sterowanie serwerami jest domyślnie
wyłączone.

## Instalacja

1. Włącz `restapi` w `config/main.yaml` DCSServerBot.
2. Skonfiguruj WebService na porcie dostępnym wyłącznie w zaufanej sieci LAN.
3. Utwórz długi, losowy `api_key` w `config/plugins/restapi.yaml`.
4. Dodaj repozytorium w HACS jako niestandardową integrację.
5. Uruchom ponownie Home Assistanta i dodaj integrację przez **Urządzenia i usługi**.

Po instalacji otrzymasz urządzenie główne bota oraz osobne urządzenie dla każdego
serwera DCS. Sterowanie można włączyć w opcjach integracji. Każdy przycisk
restartu lub zatrzymania na dashboardzie powinien mieć potwierdzenie.

Wersja 0.4.0 dodaje chronologiczny strumień zdarzeń misji, pełną pogodę,
Greenieboard, bullseye i rysunki misji, a przez opcjonalny most także transfer,
stan zapory, alarm DDoS, zablokowane adresy, topologię NUMA i przydział CPU.
Jednostki i trasy na mapie mogą być wyświetlane przez osadzony panel Olympus.

Do `opt_plugins` można dodać `greenieboard` i `firewall`. Dla zapory zacznij od
`action: alert` oraz `max_conns_per_ip: 0`, aby monitoring nie modyfikował reguł.
Pełna analiza źródeł UDP w Windows wymaga Npcap. Gdy Zapora Windows jest
wyłączona, integracja pokaże brak ochrony zamiast fałszywego stanu poprawnego.

Nie przekierowuj portu RestAPI na routerze. API zawiera operacje administracyjne.

