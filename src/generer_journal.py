# -*- coding: utf-8 -*-
"""Fabrique un journal d'événements pour les exercices de process mining.

La ligne d'assemblage CityLine de CycloPlus, poste par poste, vélo par vélo.
Le journal est simulé, pas relevé. Il reproduit le comportement du cas, pour
que les étudiants retrouvent par la mesure ce que le cours a calculé.

Ce que le journal permet de faire :
  - dessiner le graphe du processus : sept postes en série, un retour en
    arrière pour les retouches ;
  - comparer charge et capacité, poste par poste : minutes de travail par
    jour contre 480 minutes disponibles ;
  - désigner le goulot : la peinture, dont les changements de couleur
    consomment du temps sans produire ;
  - mesurer l'attente : chaque événement porte son début et sa fin, donc le
    temps passé en file se calcule.

Le temps est compté en minutes ouvrées, puis converti en dates : la ligne
travaille de 7h00 à 15h00, du lundi au vendredi.

Usage  : python generer_journal.py
Sortie : journal.csv
"""

import csv
import random
from datetime import datetime, timedelta

GRAINE = 42
NB_VELOS = 300
PREMIER_JOUR = datetime(2026, 9, 1)    # un mardi
HEURE_OUVERTURE = 7
MINUTES_PAR_JOUR = 480

# Les sept postes, avec leur temps de cycle de gamme, en minutes.
POSTES = [
    ("Cadre et peinture", 10.0, "Peinture 1"),
    ("Fourche et direction", 8.0, "Montage 2"),
    ("Roues", 11.0, "Montage 3"),
    ("Transmission", 16.0, "Montage 4"),
    ("Freins", 12.0, "Montage 5"),
    ("Accessoires", 9.0, "Montage 6"),
    ("Contrôle final", 7.0, "Contrôle 7"),
]
PEINTURE, CONTROLE = 0, 6

DISPERSION = 0.18                  # irrégularité des temps de travail
PERFORMANCE_TRANSMISSION = 0.90    # la transmission tourne à 90 % de sa gamme
MINUTES_ENTRE_CHANGEMENTS = 51.0   # cinq changements de couleur par jour
DUREE_CHANGEMENT = 45.0
TAUX_RETOUCHE = 0.175              # part des cadres qui repassent en retouche
DUREE_RETOUCHE = 15.0
# La retouche se fait dans une cabine séparée : elle ne prend pas de temps à
# la peinture, qui reste le goulot de la ligne.
RESSOURCE_RETOUCHE = "Retouche 8"
ENTRE_LANCEMENTS = 20.0            # minutes entre deux lancements, en moyenne

SORTIE = "journal.csv"


def en_date(minute: float) -> datetime:
    """Convertit une minute ouvrée en date et heure."""
    jour, reste = divmod(minute, MINUTES_PAR_JOUR)
    date = PREMIER_JOUR
    avance = 0
    while avance < jour:
        date += timedelta(days=1)
        if date.weekday() < 5:
            avance += 1
    while date.weekday() >= 5:
        date += timedelta(days=1)
    return date.replace(hour=HEURE_OUVERTURE) + timedelta(minutes=reste)


def travail(hasard: random.Random, base: float) -> float:
    return max(1.0, hasard.gauss(base, base * DISPERSION))


def placer(debut: float, duree: float) -> tuple[float, float]:
    """Pose une tâche sans la couper par la nuit.

    Une tâche qui ne tient pas dans la fin de journée est reportée au
    lendemain matin : on ne laisse pas un cadre à moitié peint sur la ligne.
    """
    jour, offset = divmod(debut, MINUTES_PAR_JOUR)
    if offset + duree > MINUTES_PAR_JOUR:
        debut = (jour + 1) * MINUTES_PAR_JOUR
    return debut, debut + duree


def main() -> None:
    hasard = random.Random(GRAINE)
    libre = [0.0] * len(POSTES)           # quand chaque poste se libère
    libre_retouche = 0.0
    depuis_changement = 0.0               # minutes peintes depuis le dernier
    evenements = []
    lancement = 0.0

    for numero in range(1, NB_VELOS + 1):
        cas = f"CityLine-{numero:04d}"
        instant = lancement
        evenements.append((cas, "Lancement en production", instant, instant,
                           "Ordonnancement"))

        for rang, (activite, cycle, ressource) in enumerate(POSTES):
            debut = max(instant, libre[rang])

            if rang == PEINTURE and depuis_changement >= MINUTES_ENTRE_CHANGEMENTS:
                debut, fin_reglage = placer(debut, DUREE_CHANGEMENT)
                evenements.append((cas, "Changement de couleur", debut,
                                   fin_reglage, ressource))
                depuis_changement = 0.0
                debut = fin_reglage

            base = cycle
            if activite == "Transmission":
                base = cycle / PERFORMANCE_TRANSMISSION
            duree = travail(hasard, base)
            debut, fin = placer(debut, duree)
            if rang == PEINTURE:
                depuis_changement += duree

            evenements.append((cas, activite, debut, fin, ressource))
            libre[rang] = fin
            instant = fin

        if hasard.random() < TAUX_RETOUCHE:
            debut, fin = placer(max(instant, libre_retouche),
                                travail(hasard, DUREE_RETOUCHE))
            evenements.append((cas, "Retouche peinture", debut, fin,
                               RESSOURCE_RETOUCHE))
            libre_retouche = fin

            debut, fin = placer(max(fin, libre[CONTROLE]),
                                travail(hasard, POSTES[CONTROLE][1]))
            evenements.append((cas, "Contrôle final", debut, fin,
                               POSTES[CONTROLE][2]))
            libre[CONTROLE] = fin
            instant = fin

        debut, fin = placer(instant, 5.0)
        evenements.append((cas, "Expédition", debut, fin, "Expédition"))
        lancement += hasard.expovariate(1.0 / ENTRE_LANCEMENTS)

    evenements.sort(key=lambda ligne: (ligne[2], ligne[0]))

    with open(SORTIE, "w", encoding="utf-8", newline="") as fichier:
        plume = csv.writer(fichier)
        plume.writerow(["case_id", "activite", "debut", "fin", "ressource"])
        for cas, activite, debut, fin, ressource in evenements:
            plume.writerow([cas, activite,
                            en_date(debut).strftime("%Y-%m-%d %H:%M:%S"),
                            en_date(fin).strftime("%Y-%m-%d %H:%M:%S"),
                            ressource])

    print(f"{len(evenements)} événements, {NB_VELOS} vélos, écrits dans {SORTIE}")


if __name__ == "__main__":
    main()
