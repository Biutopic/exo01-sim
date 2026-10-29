---
title: "EXO-01 en simulation : flottabilité, assiette, houle, amarrage"
description: "Ce que le modèle numérique d'EXO-01 dit de la plateforme avant sa mise à l'eau — et ce qu'il ne peut pas dire."
maturity: "Exploratoire — géométrie et répartition des masses supposées"
date: 2026-10-29
version: "exo01-sim v1.1"
repo: "https://github.com/Biutopic/exo01-sim"
lang: fr
---

> **Statut : exploratoire.** Tous les chiffres ci-dessous sortent d'un modèle construit sur le plan d'assemblage et sur des masses déclarées, pas mesurées. Ils servent à orienter l'intégration et à préparer les essais ; ils ne sont pas des caractéristiques certifiées. Le code, les configurations et les rapports sont publics : [Biutopic/exo01-sim](https://github.com/Biutopic/exo01-sim).

## Pourquoi simuler avant de mettre à l'eau

EXO-01 est un exosquelette flottant : deux rangées de flotteurs, une structure aluminium, un pont arrière, une plateforme d'observation, 2 kWc de panneaux, 240 kg de batteries et deux propulseurs électriques, qui vient s'accoupler à un bateau existant — ici *L'Hydronaute*. Avant la première mise à l'eau (automne 2026), trois questions conditionnent l'intégration : **où placer les masses** (batteries, armoire électrique), **comment attacher le bateau** (aussières), et **comment l'ensemble bouge** dans le clapot et les sillages de l'Erdre. Un modèle numérique répond à ces questions avec des ordres de grandeur avant que la soudure ne les fige.

![EXO-01 et L'Hydronaute amarré, eau calme](img/web/01_moored_still_iso.webp)
*EXO-01 et L'Hydronaute à couple, eau calme. Rendu de l'outil de simulation (géométrie du plan d'assemblage, coque de L'Hydronaute reconstituée).*

## Méthode

Le simulateur (`exo01-sim`) est un code Python ouvert avec une interface 3D. Il enchaîne cinq calculs, chacun vérifiable séparément :

1. **Géométrie et masses.** Six flotteurs Flofiz (Ø 0,60 × 1,60 m, nez traîneau) en deux rangées, la structure du plan d'assemblage La Mutine (28/05/2026), et une liste de 18 masses : structure 290 kg, flotteurs 180 kg, batteries 2 × 120 kg, panneaux 80 kg, électronique 50 kg, propulseurs 16 kg — **856 kg à vide**, hors charge utile et hors occupants. Chaque masse porte sa provenance (déclarée / estimée / hypothèse).
2. **Hydrostatique exacte.** Volume immergé et centre de carène calculés sur les surfaces triangulées des flotteurs, puis équilibre statique (tirant d'eau, assiette, gîte) résolu par Newton. Stabilité initiale (GM) par la même voie. Vérifié contre les formules analytiques des cylindres.
3. **Hydrodynamique linéaire.** Théorie potentielle (méthode des éléments frontières, [Capytaine 3.0](https://capytaine.github.io/)), 6 degrés de liberté pour EXO-01 seul, **12 degrés de liberté couplés** EXO-01 + L'Hydronaute (interaction hydrodynamique entre les deux coques), profondeur finie 3 m, eau douce. Les coefficients sont pré-calculés et mis en cache ; l'interface anime le mouvement reconstruit en houle régulière.
4. **Amarrage et propulsion.** Quatre aussières modélisées comme des ressorts qui ne travaillent qu'en traction (mou dès qu'elles se détendent), prétension 100 N ; équilibre couplé des deux corps. Propulsion quasi-statique : deux pods RDT POD 5.0 (poussée au point fixe 2 × 62 kgf = 1 216 N), résistance de coque ITTC-57 + facteurs de forme → vitesse d'équilibre et efforts transmis par les aussières, en poussée (pods d'EXO-01) comme en remorquage (moteur du bateau).
5. **Balayages de conception.** Position des batteries (44 positions sur deux zones), arrangement des aussières (36 combinaisons + presets), chacun évalué avec les solveurs ci-dessus — le tableau complet est rendu, pas seulement un « meilleur » choix.

Vérification : 84 tests automatisés et 31 contrôles (analytique vs numérique, transformation du point de référence des coefficients hydrodynamiques exacte à 10⁻¹⁵, convergence du maillage ≤ 8 % sur le cas couplé). Les hypothèses sont tenues dans un fichier `ASSUMPTIONS.md` versionné avec le code.

## Ce que le modèle dit

### 1. L'assiette : le pont arrière est trop chargé

À vide, avec les batteries aux rambardes du pont arrière (position du plan), EXO-01 flotte **pont arrière enfoncé de 3,8°**, franc-bord du pont arrière **0,17 m**, tirant d'eau 0,37 m. La cause est géométrique : le centre de flottabilité des flotteurs est à x ≈ 2,9 m de l'arrière, le centre de masse à x ≈ 2,3 m.

![Position des batteries : avant / après](img/web/10_battery_position_comparison.webp)
*Même état, vue de côté : batteries aux rambardes du pont arrière (haut) et avancées sur les longerons des flotteurs (bas).*

Le balayage de position des batteries le montre sans ambiguïté : sur le pont arrière lui-même, le mieux qu'on obtienne est −3,3°. **Avancées sur les longerons des flotteurs, à x ≈ 3,5 m** (entre les montants central et avant, au-dessus des flotteurs, hors de la coque du bateau), les 240 kg de batteries annulent l'assiette : **0°, franc-bord 0,36 m**, et l'amplitude de roulis en houle de travers baisse de 4,7° à 3,8°.

![Assiette en fonction de la position des batteries](img/web/11_battery_sweep_trim_vs_x.webp)
*Assiette (gauche) et amplitudes de roulis/tangage (droite) en fonction de la position longitudinale des deux batteries ; L'Hydronaute amarré, pas d'occupants.*

C'est nécessaire, pas suffisant. Le pont arrière reste le point faible sous charge : deux personnes de 80 kg à la table arrière ramènent l'assiette à −2,2° même batteries avancées (−6,9° et pont arrière au ras de l'eau dans la position du plan) ; quatre personnes sur le pont arrière laissent 0,09 m de franc-bord (pas d'équilibre statique du tout dans la position du plan). Les conséquences de conception sont listées plus bas.

### 2. La stabilité n'est pas le sujet, l'enfoncement l'est

Hauteur métacentrique transversale ≈ 20 m, longitudinale ≈ 9 m : un catamaran large de 4,5 m sur des flotteurs de 0,60 m est extrêmement raide. Le risque n'est pas le chavirement ; c'est la perte de franc-bord et l'immersion d'un flotteur quand la charge est mal répartie — ce que les chiffres d'assiette ci-dessus décrivent.

### 3. En houle, la plateforme suit la surface

Périodes propres à vide ≈ 1,3–1,5 s (pilonnement 1,4 s, roulis 1,3 s, tangage 1,5 s). Le clapot et les sillages de l'Erdre ont des périodes plus longues (2–3 s) : la plateforme ne résonne pas, elle **épouse la pente de la vague**. En houle régulière de travers de 0,3 m de hauteur et 2,5 s de période, le roulis d'EXO-01 vaut ≈ 4,3–4,5° (la pente de la vague vaut 5,5°), l'accélération verticale sur le pont ≈ 1,2 m/s² (0,12 g). L'Hydronaute amarré roule davantage (≈ 8°) : sa coque est plus étroite.

![Houle de travers, instant de roulis maximal](img/web/04_beam_sea_max_roll.webp)
*Houle régulière de travers H 0,3 m, T 2,5 s : instant de roulis maximal d'EXO-01 (mouvement linéaire reconstruit, échelle 1:1).*

Réserve importante : la théorie potentielle n'a pas d'amortissement visqueux. Près des résonances de l'eau piégée entre les flotteurs (T ≈ 1,2–1,6 s), les coefficients sont surestimés ; seul un essai d'extinction en roulis donnera l'amortissement réel.

### 4. Les aussières : les quatre aussières « vers l'avant » tiennent un remorquage, pas une poussée

L'arrangement du plan (quatre aussières des montants d'EXO-01 vers l'avant du bateau) équilibre un **remorquage** par le moteur de L'Hydronaute, mais pas une **poussée** par les pods d'EXO-01 : les efforts horizontaux ne peuvent pas se fermer et le modèle ne trouve d'équilibre qu'en faisant reculer le bateau de 0,7 m dans la structure. Le balayage des 36 arrangements donne le meilleur compromis : **montants arrière → taquets milieu + montants avant → taquets de poupe** (deux diagonales longues), 472 N maximum dans une aussière à pleine poussée, aucune aussière molle au repos.

![Vue de dessus : L'Hydronaute à couple entre les deux rangées de flotteurs](img/web/02_moored_still_top.webp)
*Vue de dessus : le bateau est accosté entre les deux rangées de flotteurs ; l'espace sous les travées reste libre.*

Avec 100 N de prétension, **toutes les aussières se détendent à chaque cycle** en houle de 0,3 m, avec des reprises de tension estimées à 0,9–1,2 kN : prétension et raideur (ou amortisseurs d'aussière) sont à revoir avant les essais.

### 5. Propulsion : ordre de grandeur seulement

À 100 % des deux pods, l'ensemble EXO-01 + L'Hydronaute atteindrait ≈ 2,8 m/s (10 km/h), avec 870 N transmis au bateau par les aussières. Ces vitesses sont des **bornes supérieures** : le modèle suppose la poussée au point fixe constante avec la vitesse, ce qui est faux pour un propulseur à hélice ; la courbe poussée–vitesse des pods n'est pas connue.

## Ce que le modèle ne dit pas

- **Les masses et leurs positions sont déclarées, pas pesées.** Toute l'assiette repose sur le décalage de 0,6 m entre centre de masse et centre de flottabilité.
- **La coque de L'Hydronaute est une reconstitution** à partir de la table des couples du constructeur (Renaud 8000), pas un relevé ; sa masse (2,1 ou 3,0 t selon les sources) n'est pas mesurée.
- **Pas d'amortissement visqueux, pas de vent, pas de courant, pas de contact** structure–coque, aussières linéaires sans masse.
- **Rien sur la structure** : le modèle ne vérifie pas que les longerons des flotteurs portent 120 kg par batterie, ni les efforts dans les montants.
- **Rien sur l'énergie** : autonomie et bilan solaire sont traités séparément.

## Les cinq mesures qui changeraient tout

1. Position réelle des flotteurs sur le châssis (x, hauteur d'axe, écartement) — toute la flottabilité et l'hydrodynamique en dépendent.
2. Centre de gravité installé de chaque composant, surtout en hauteur, et masse totale pesée.
3. Comptabilité des masses : charge utile, câblage, fluides, surface de pont.
4. Pour l'accouplement : masse et coque de L'Hydronaute, position des taquets, matériau/longueur/prétension des aussières ; courbe poussée–vitesse des pods.
5. Charges opérationnelles et environnement : occupants, profondeur d'eau, climat de houle, **essai d'extinction** en roulis/pilonnement (amortissement).

## Ce que cela change pour EXO-01

- **Avancer les batteries** sur les longerons des flotteurs (ou toute masse équivalente ≈ 400 kg·m vers l'avant), sous réserve de la tenue structurelle du cadre.
- **Revoir l'amarrage** : diagonales longues, prétension et raideur adaptées, protection contre les à-coups.
- **Charger le pont arrière avec mesure** tant que l'assiette n'a pas été corrigée ; prévoir la position des occupants dans les consignes d'exploitation.
- **Mesurer avant de calibrer** : pesée, relevé des flotteurs et essai d'extinction à la première mise à l'eau, puis recalage du modèle.

*Outil : [Biutopic/exo01-sim](https://github.com/Biutopic/exo01-sim) — Python / Capytaine 3.0 / three.js. Rapports complets : `results/optimisation`, `results/comparison`, `results/verification` dans le dépôt.*
