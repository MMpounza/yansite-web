# ModelBuilder avancé : lycées, cinémas et fast-foods en Île-de-France

> Tutoriel ArcGIS Pro (interface en français). Il prolonge l'exercice « Jeux Olympiques »
> (zone tampon, itérateur, jointure spatiale) et va plus loin : analyse de proximité
> (1 à n), statistiques, jointure de champ, champs calculés avec bloc de code, paramètres
> et variables en ligne, polygones de Thiessen, maillage hexagonal, analyse de points
> chauds, itérateur sur valeurs de champ, logique conditionnelle, export Python.

---

## Problématique

**Les lycéens franciliens ont-ils un environnement plus « fast-food » que « culture » ?**

Pour chaque lycée d'Île-de-France, on va mesurer :

1. son **exposition aux fast-foods** : combien de fast-foods à moins de *R* mètres (R au
   choix de l'utilisateur), et à quelle distance se trouve le plus proche ;
2. son **accès à la culture** : distance au cinéma le plus proche, et quels cinémas
   « desservent » le plus de lycées ;
3. un **indice d'environnement** (0 à 100), cartographié et testé statistiquement
   (points chauds) ;
4. une **synthèse par département et par commune** (fast-foods pour 10 000 habitants),
   avec une alerte automatique pour les départements qui ont des lycées très exposés.

## Vue d'ensemble des modèles

| Modèle | Ce qu'il apprend | Outils principaux |
|---|---|---|
| 0. Préparation (manuelle) | travailler une GDB avant analyse | Calculer un champ, Supprimer les identiques, Domaines |
| 1. `ModeleExposition` | paramètres de modèle, variables en ligne, relation 1-n | Calculer une valeur, Proximité, Générer une table de proximité, Statistiques récapitulatives, Joindre un champ, Calculer un champ (bloc de code) |
| 2. `ModeleCinemas` | zones d'influence, synthèse spatiale | Proximité, Modifier un champ, Créer des polygones de Thiessen, Découper, Synthétiser à l'intérieur |
| 3. `ModeleTerritoire` | maillage, statistiques spatiales | Générer une tessellation, Sélectionner une couche par emplacement, Analyse de points chauds optimisée, (Densité de noyau) |
| 4. `ModeleDepartements` | itération, condition, collecte | Itérer les valeurs de champ, Sélectionner, Si le nombre de lignes est, Collecter des valeurs, Combiner |
| 5. `ModeleComplet` | modèles imbriqués, export Python | les modèles 1 à 4 comme outils |

---

## Partie 1 : construire la géodatabase

### 1.1 Les données

| Classe d'entités | Source | Contenu |
|---|---|---|
| `Lycees_IDF` (points) | Annuaire de l'éducation, data.education.gouv.fr | UAI, nom, statut public/privé, commune, voies (générale, technologique, professionnelle), nb d'élèves, cantine, **IPS** (indice de position sociale, si disponible) |
| `Cinemas_IDF` (points) | Établissements cinématographiques (CNC), data.culture.gouv.fr | nom, commune, écrans, fauteuils, entrées, multiplexe, art et essai |
| `FastFood_IDF` (points) | OpenStreetMap (`amenity=fast_food`) via l'API Overpass | nom, enseigne, type de cuisine, chaîne oui/non |
| `Communes_IDF` (polygones) | geo.api.gouv.fr (Paris découpé en 20 arrondissements) | nom, code INSEE, département, population |
| `Departements_IDF` (polygones) | fusion des communes | code, nom, population |
| `Limite_IDF` (polygone) | fusion des communes | contour régional |

Tout est en **RGF93 / Lambert-93 (EPSG:2154)** : les distances sont en mètres.

### 1.2 Lancer le script

1. Copiez le dossier `scripts` sur votre PC.
2. Ouvrez ArcGIS Pro (n'importe quel projet), menu **Analyse > Python > Fenêtre Python**.
3. Tapez (en adaptant le chemin) :

   ```python
   exec(open(r"C:\Users\VOUS\Documents\scripts\01_construire_gdb.py", encoding="utf-8").read())
   ```

4. Le script :
   - télécharge les fichiers bruts dans `Documents\ArcGIS\Projects\DonneesLyceesIDF\brut\` ;
   - filtre l'Île-de-France, nettoie les champs, écarte les coordonnées aberrantes ;
   - crée `Documents\ArcGIS\Projects\DonneesLyceesIDF\Donnees_Lycees_IDF.gdb`.

> **Si un téléchargement échoue** (proxy de l'université, par exemple), le script affiche
> l'URL du fichier manquant. Téléchargez-le avec votre navigateur, renommez-le comme
> indiqué, déposez-le dans `brut\` et relancez le script : il ne retélécharge pas les
> fichiers déjà présents. Le détail est dans le [README](README.md#téléchargement-manuel).

### 1.3 Créer le projet

1. ArcGIS Pro > **Nouveau projet > Carte**. Nom : `LyceesFastFoodIDF`.
2. **Vue > Fenêtre Catalogue > Bases de données > clic droit > Ajouter une base de données**
   puis sélectionnez `Donnees_Lycees_IDF.gdb`.
3. La géodatabase du projet `LyceesFastFoodIDF.gdb` recevra **toutes les sorties**.
   La GDB source reste intacte : on peut relancer les modèles autant de fois qu'on veut.
4. Glissez les 6 couches sur la carte. Symbologie conseillée :
   lycées = cercle bleu, cinémas = étoile violette, fast-foods = petit point rouge
   semi-transparent, communes = contour gris sans remplissage.

---

## Partie 2 : travailler la GDB avant les modèles

Une bonne analyse commence par des données vérifiées. Faites ces étapes **à la main**
(sans ModelBuilder) dans la GDB source.

### 2.1 Contrôler les données

- Clic droit sur chaque couche > **Propriétés > Source** : vérifiez *RGF 1993 Lambert-93*.
- Ouvrez les tables attributaires et notez le nombre d'entités de chaque couche.
- Sur `Lycees_IDF`, faites **Données > Statistiques** sur `Statut` et `Code_Dep`.
  Combien de lycées publics et privés y a-t-il ? Quel département en compte le plus ?

### 2.2 Ajouter un type de lycée

`Lycees_IDF` > **Calculer un champ** (Outils de gestion des données) :

- Nom du champ : `Type_Lycee` (nouveau, type **Texte**)
- Expression : `type_lycee(!Voie_Gen!, !Voie_Tech!, !Voie_Pro!)`
- Bloc de code :

```python
def type_lycee(g, t, p):
    gt = (g == 1) or (t == 1)
    if gt and p == 1:
        return "Polyvalent"
    if gt:
        return "Général et technologique"
    if p == 1:
        return "Professionnel"
    return "Non renseigné"
```

### 2.3 Nettoyer les fast-foods

Dans OpenStreetMap, un même restaurant est parfois saisi deux fois (un point et un
bâtiment). Outil **Supprimer les identiques** (*Delete Identical*) sur `FastFood_IDF` :

- Champs : `Shape` et `Nom_FF`
- Tolérance XY : `10 Mètres`

Notez combien d'entités ont été supprimées.

> Travaillez sur une **copie** si vous voulez garder l'original : **Copier des entités**
> vers `FastFood_IDF_brut` avant de nettoyer.

### 2.4 Créer un domaine pour la classe d'exposition

Catalogue > clic droit sur `Donnees_Lycees_IDF.gdb` > **Domaines** > nouveau domaine :

- Nom : `Dom_Exposition`, type de champ : Texte, type de domaine : **valeurs précodées**
- Codes / descriptions : `Aucune`, `Faible`, `Moyenne`, `Forte`, `Très forte`

On l'appliquera au champ `Classe_Expo` créé par le modèle 1 (Partie 3, étape 11).

---

## Partie 3 : Modèle 1, `ModeleExposition`

**Objectif.** Pour chaque lycée : la distance au fast-food le plus proche (`Dist_FF`), le
nombre de fast-foods à moins de R mètres (`NB_FF`) et une classe d'exposition.
**R est un paramètre**, choisi à chaque exécution (300 m, 500 m, 1 000 m...).

> **Pourquoi pas une zone tampon + jointure spatiale comme pour les JO ?**
> Ça marcherait, mais on va utiliser la **table de proximité** : elle garde
> *chaque couple* lycée ↔ fast-food avec sa distance (relation 1-n). On peut ensuite
> compter, prendre un minimum, une moyenne... sans créer de polygones.

### Schéma cible

```
 Rayon_m (P) ──► Calculer une valeur ──► Distance (Unité linéaire)
                                             │
 Lycees_IDF (P) ─► Copier des entités ─► Lycees_Expo_%Rayon_m%m
                                             │
 FastFood_IDF (P) ─────────────► Proximité ──► Modifier un champ (NEAR_DIST → Dist_FF)
                     │                              │
                     └─► Générer une table de proximité (rayon = Distance)
                                   │
                         Statistiques récapitulatives (COUNT par IN_FID)
                                   │
                         Joindre un champ ──► Calculer un champ NB_FF
                                                   │
                                          Calculer un champ Classe_Expo (P)
```

(P) = paramètre du modèle.

### Étapes

1. **Catalogue > Boîtes à outils > `LyceesFastFoodIDF.atbx` > clic droit > Nouveau > Modèle.**
   Clic droit sur le modèle > **Propriétés** : Nom et Étiquette `ModeleExposition`.

2. **Créer la variable du rayon.** Onglet ModelBuilder > **Variable** > type de données
   **Entier long**. Renommez-la `Rayon_m` (clic droit > Renommer), double-cliquez et
   saisissez `500`. Clic droit > **Paramètre** : un petit **P** apparaît.

3. **Calculer une valeur** (ModelBuilder > Utilitaires > Calculer une valeur) :
   - Expression : `"%Rayon_m% Meters"`
   - Type de données : **Unité linéaire**
   - Renommez la sortie `Distance`.

   Comme `Rayon_m` est seulement utilisé « en ligne » (entre `%`), il n'est relié à rien.
   Tracez une flèche de `Rayon_m` vers *Calculer une valeur* et choisissez
   **Condition préalable** : l'outil attendra que la variable soit définie.

   > **Variable en ligne** : `%Rayon_m%` est remplacé par la valeur de la variable au
   > moment de l'exécution. Avec 500 → `"500 Meters"`.

4. **Copier des entités** : entrée `Lycees_IDF` (glissée depuis la GDB source), sortie
   `LyceesFastFoodIDF.gdb\Lycees_Expo_%Rayon_m%m`. Le nom de la sortie suit le rayon :
   `Lycees_Expo_500m`, `Lycees_Expo_1000m`...

5. **Proximité** (*Near*, Outils d'analyse) : entités en entrée = la copie,
   entités de proximité = `FastFood_IDF`, **sans rayon de recherche**. L'outil ajoute
   `NEAR_FID` et `NEAR_DIST` à la table.

6. **Modifier un champ** (*Alter Field*) sur la sortie de *Proximité* : `NEAR_DIST` →
   nouveau nom `Dist_FF`, alias « Distance fast-food (m) ».
   Puis **Supprimer un champ** : `NEAR_FID` (il sera recréé par le modèle 2).

7. **Générer une table de proximité** (Outils d'analyse) :
   - Entités en entrée : sortie de *Supprimer un champ*
   - Entités de proximité : `FastFood_IDF`
   - Table en sortie : `Proxi_FF_%Rayon_m%m`
   - Rayon de recherche : reliez la variable **Distance** (flèche > *Rayon de recherche*)
   - Décochez « Rechercher uniquement l'entité la plus proche » (*closest = ALL*), nombre
     max. = 0 (illimité)

   La table contient une ligne par couple lycée/fast-food à moins de R m :
   `IN_FID` (identifiant du lycée), `NEAR_FID`, `NEAR_DIST`, `NEAR_RANK`.

8. **Statistiques récapitulatives** (*Summary Statistics*) :
   - Table en entrée : `Proxi_FF_%Rayon_m%m`
   - Table en sortie : `Stats_FF_%Rayon_m%m`
   - Champ statistique : `NEAR_FID`, type **Nombre** (*COUNT*)
   - Champ de regroupement : `IN_FID`

9. **Joindre un champ** (*Join Field*, Outils de gestion des données) :
   - Table en entrée : sortie de *Supprimer un champ*, champ `OBJECTID`
   - Table de jointure : `Stats_FF_...`, champ `IN_FID`
   - Champs à transférer : `COUNT_NEAR_FID`

   > Différence avec une **jointure spatiale** : ici la jointure se fait **par attribut**
   > (OBJECTID = IN_FID) et elle est **permanente** (les champs sont écrits dans la table).

10. **Calculer un champ** `NB_FF` (nouveau champ, **Entier long**) :
    - Expression : `nz(!COUNT_NEAR_FID!)`
    - Bloc de code :

    ```python
    def nz(v):
        return 0 if v is None else int(v)
    ```

    Les lycées sans fast-food dans le rayon avaient `<Null>` après la jointure : ils
    passent à 0. (Facultatif : **Supprimer un champ** `COUNT_NEAR_FID`.)

11. **Calculer un champ** `Classe_Expo` (nouveau champ, **Texte**) :
    - Expression : `classe(!NB_FF!)`
    - Bloc de code :

    ```python
    def classe(nb):
        if nb == 0:
            return "Aucune"
        elif nb <= 2:
            return "Faible"
        elif nb <= 5:
            return "Moyenne"
        elif nb <= 10:
            return "Forte"
        return "Très forte"
    ```

    Après exécution, appliquez le domaine `Dom_Exposition` au champ :
    **Affecter un domaine à un champ** (*Assign Domain To Field*). Ou ajoutez l'outil à la
    fin du modèle.

12. **Paramètres du modèle** : clic droit > Paramètre sur `Lycees_IDF`, `FastFood_IDF`,
    `Rayon_m` et sur la sortie finale. Ordre et libellés :
    **ModelBuilder > Propriétés > Paramètres**.

13. **Mise en page automatique**, **Valider**, **Enregistrer**, **Exécuter**.

14. **Testez l'outil** : dans le Catalogue, double-cliquez sur `ModeleExposition`. Il
    s'ouvre comme un outil normal. Lancez-le avec 300, 500 et 1 000 m et comparez.

### Résultat attendu

`Lycees_Expo_500m` avec `Dist_FF`, `NB_FF` et `Classe_Expo`. Symbologie conseillée :
**Valeurs uniques** sur `Classe_Expo` (vert → rouge foncé), ou **Symboles gradués**
(taille) sur `NB_FF`.

---

## Partie 4 : Modèle 2, `ModeleCinemas`

**Objectif.** (a) Ajouter à chaque lycée la distance au cinéma le plus proche et son
nom. (b) Découper l'Île-de-France en **zones d'influence des cinémas** (chaque point de
la zone est plus proche de ce cinéma que de tout autre) et compter les lycées par zone.

### Étapes

1. Nouveau modèle `ModeleCinemas`. Glissez `Lycees_Expo_500m` (sortie du modèle 1),
   `Cinemas_IDF` et `Limite_IDF`.

2. **Proximité** : `Lycees_Expo_500m` → `Cinemas_IDF`.

3. **Modifier un champ** : `NEAR_DIST` → `Dist_Cine`. Puis enchaînez un 2e
   **Modifier un champ** : `NEAR_FID` → `FID_Cine`.

4. **Joindre un champ** : entrée = sortie précédente, champ `FID_Cine` ; table de
   jointure `Cinemas_IDF`, champ `OBJECTID` ; champs `Nom_Cinema`, `Ecrans`.
   Chaque lycée connaît maintenant « son » cinéma.

5. **Créer des polygones de Thiessen** (*Create Thiessen Polygons*, Outils d'analyse) :
   entrée `Cinemas_IDF`, sortie `Thiessen_Cinemas`, champs en sortie : **Tous les champs**.

   > Les polygones de Thiessen (ou de Voronoï) sont une alternative aux zones tampons :
   > au lieu d'une distance fixe, chaque cinéma reçoit le territoire qui lui est le plus
   > proche. Le résultat couvre une emprise rectangulaire, d'où l'étape suivante.

6. **Découper** : entrée `Thiessen_Cinemas`, entités de découpage `Limite_IDF`,
   sortie `Zones_Cinemas`.

7. **Synthétiser à l'intérieur** (*Summarize Within*, Outils d'analyse) :
   - Polygones en entrée : `Zones_Cinemas`
   - Entités en entrée à synthétiser : la sortie de *Joindre un champ* (les lycées)
   - Conserver les polygones sans points : oui
   - Champs de synthèse : `NB_FF`, statistique **Moyenne**
   - Ajouter des récapitulatifs de forme : oui (crée `Point_Count`)
   - Sortie : `Zones_Cinemas_Lycees`

   > **Synthétiser à l'intérieur** ressemble à une jointure spatiale, mais il produit
   > directement des comptages et statistiques, et peut grouper par catégorie (essayez
   > *Champ de regroupement* = `Statut` pour séparer public et privé).

8. Mise en page automatique, enregistrer, exécuter.

### À cartographier

- `Lycees_Expo_500m` en **symboles gradués** sur `Dist_Cine` : quels lycées sont à plus
  de 3 km d'un cinéma ?
- `Zones_Cinemas_Lycees` en **couleurs graduées** sur `Point_Count` : quels cinémas ont
  le plus grand « bassin lycéen » ? Comparez avec leur nombre d'écrans.

---

## Partie 5 : Modèle 3, `ModeleTerritoire`

**Objectif.** Combiner les mesures en un **indice d'environnement**, passer du point au
**maillage hexagonal**, puis repérer les concentrations **statistiquement
significatives** (points chauds).

### Étapes

1. Nouveau modèle `ModeleTerritoire`. Glissez `Lycees_Expo_500m` (avec les champs du
   modèle 2), `FastFood_IDF` et `Limite_IDF`.

2. **Calculer un champ** `Indice_Env` (nouveau champ, **Entier court**) :
   - Expression : `indice(!NB_FF!, !Dist_FF!, !Dist_Cine!)`
   - Bloc de code :

   ```python
   def indice(nb_ff, d_ff, d_cine):
       score = 50
       score -= min(nb_ff or 0, 10) * 4      # jusqu'à -40 pts selon le nb de fast-foods
       if d_ff is not None and d_ff < 100:   # fast-food quasiment en face du lycée
           score -= 10
       if d_cine is not None:                # bonus d'accès à la culture
           if d_cine <= 500:
               score += 30
           elif d_cine <= 1000:
               score += 20
           elif d_cine <= 2000:
               score += 10
       return max(0, min(100, score))
   ```

   > Les pondérations sont **un choix** de l'analyste. Discutez-les : faut-il pondérer
   > par le nombre d'écrans ? Pénaliser davantage les chaînes (`Chaine = "Oui"`) ?

3. **Générer une tessellation** (*Generate Tessellation*, Outils de gestion des données) :
   - Sortie : `Hex_Brut`
   - Étendue : **Identique à la couche `Limite_IDF`**
   - Forme : **Hexagone**, taille : `1` **Kilomètres carrés**
   - Système de coordonnées : Lambert-93

4. **Sélectionner une couche par emplacement** : `Hex_Brut` qui **intersecte**
   `Limite_IDF`, puis **Copier des entités** → `Hex_IDF` (on supprime les hexagones hors
   région).

5. **Synthétiser à l'intérieur** : `Hex_IDF` ← `FastFood_IDF` → `Hex_FF`.
   Puis **Modifier un champ** : `Point_Count` → `NB_FF`.

6. **Synthétiser à l'intérieur** : `Hex_FF` ← lycées → `Hex_FF_Lycees`.
   Puis **Modifier un champ** : `Point_Count` → `NB_LYC`.

   > Pourquoi renommer ? Le 2e *Synthétiser* recréerait un champ `Point_Count` : on
   > distingue ainsi les deux comptages.

7. **Analyse de points chauds optimisée** (*Optimized Hot Spot Analysis*, Outils de
   statistiques spatiales) :
   - Entités en entrée : `Hex_FF_Lycees`, champ d'analyse `NB_FF`
   - Sortie : `HotSpot_FF_Hex`

   L'outil calcule le **Gi\* de Getis-Ord**. Il ne dit pas seulement « il y a beaucoup de
   fast-foods ici » mais « cette concentration est **statistiquement significative** »
   (confiance de 90, 95 ou 99 %).

8. Deuxième **Analyse de points chauds optimisée** : entrée = les lycées, champ
   `Indice_Env`, sortie `HotSpot_Indice_Lycees`. Les **points froids** sont des
   groupes de lycées où l'environnement est défavorable.

9. **Option avec Spatial Analyst.**
   **Densité de noyau** (*Kernel Density*) sur `FastFood_IDF` (taille de cellule 100,
   rayon 1 000, unité km²) → `Densite_FF`. Puis **Extraire les valeurs vers des points**
   (*Extract Values to Points*) avec les lycées → `Lycees_DensiteFF` (champ
   `RASTERVALU` = densité de fast-foods sous chaque lycée).

10. Groupez les étapes 3 à 6 (sélection > **Grouper**) et nommez le groupe
    « Maillage hexagonal ». Mise en page automatique, enregistrer, exécuter.

### À cartographier

- `HotSpot_FF_Hex` : la symbologie (rouge = point chaud, bleu = point froid) est
  appliquée automatiquement.
- `Hex_FF_Lycees` : **symbologie bivariée** (*Couleurs bivariées*) `NB_FF` × `NB_LYC`.
  Où se superposent forte densité de lycées et forte densité de fast-foods ?

---

## Partie 6 : Modèle 4, `ModeleDepartements`

**Objectif.** Pour chaque département : calculer le nombre de fast-foods pour 10 000
habitants **par commune**, puis créer une couche d'alerte **seulement si** le
département a des lycées en exposition « Très forte ». À la fin, fusionner les 8
départements.

> Rappel de l'exercice JO : un modèle qui contient un itérateur **exécute tout le modèle
> une fois par valeur**. Les outils placés après **Collecter des valeurs** ne s'exécutent
> qu'une fois, après la dernière itération.

### Étapes

1. Nouveau modèle `ModeleDepartements`. Glissez `Departements_IDF`, `Communes_IDF`,
   `FastFood_IDF` et `Lycees_Expo_500m`.

2. **Itérateurs > Itérer les valeurs de champ** (*Iterate Field Values*) :
   - Table en entrée : `Departements_IDF`
   - Champ : `Code_Dep`
   - Type de données : Chaîne
   - Sortie : `Value` (vous pouvez la renommer `Dep`, l'expression en ligne devient
     alors `%Dep%`)

3. **Sélectionner** (*Select*, Outils d'analyse) :
   - Entrée : `Communes_IDF`
   - Sortie : `Communes_%Value%`
   - Expression : `Code_Dep = '%Value%'` (les apostrophes sont nécessaires : c'est un
     champ texte)
   - Reliez `Value` à *Sélectionner* comme **Condition préalable**.

4. **Synthétiser à l'intérieur** : `Communes_%Value%` ← `FastFood_IDF` →
   `FF_Communes_%Value%`.

5. **Calculer un champ** `FF_10000hab` (**Double**) :
   - Expression : `ratio(!Point_Count!, !Population!)`
   - Bloc de code :

   ```python
   def ratio(nb, pop):
       if not pop:
           return None
       return round(nb / pop * 10000, 2)
   ```

6. **Utilitaires > Collecter des valeurs** : reliez-y la sortie de *Calculer un champ*
   (**Valeur en entrée**).

7. **Combiner** (*Merge*) : entrée = *Valeurs en sortie* de Collecter des valeurs,
   sortie `FF_Communes_IDF`.

8. **La branche conditionnelle.**
   - **Créer une couche** (*Make Feature Layer*) : entrée `Lycees_Expo_500m`, nom
     `TresExposes_%Value%`, expression
     `Code_Dep = '%Value%' AND Classe_Expo = 'Très forte'`
   - **Logique > Si le nombre de lignes est** (*If Row Count Is*) : entrée = la
     couche, condition **Supérieur à** `0`. L'outil a deux sorties booléennes :
     **Vrai** et **Faux**.
   - **Exporter des entités** : entrée = la couche, sortie `Alerte_Lycees_%Value%`.
     Reliez la sortie **Vrai** à *Exporter des entités* comme **Condition préalable**.

   > Résultat : `Alerte_Lycees_93` existera peut-être, mais pas `Alerte_Lycees_77` si
   > aucun lycée de Seine-et-Marne n'est en exposition très forte. Le modèle **décide**.

9. Mise en page automatique, enregistrer, exécuter. La fenêtre d'exécution affiche les
   8 itérations (75, 77, 78, 91, 92, 93, 94, 95).

10. Le contenu des sorties intermédiaires `Communes_%Value%` (8 couches) n'est pas utile :
    clic droit > **Intermédiaire**. Les données intermédiaires sont supprimées après
    l'exécution.

### À cartographier

`FF_Communes_IDF` en **couleurs graduées** sur `FF_10000hab` (discrétisation par
seuils naturels ou quantiles). Comparez Paris, la petite couronne et la grande couronne.

---

## Partie 7 : Modèle 5, `ModeleComplet` (modèles imbriqués) et export Python

1. Nouveau modèle `ModeleComplet`. Glissez **les outils** `ModeleExposition`,
   `ModeleCinemas`, `ModeleTerritoire` depuis la boîte à outils : un modèle devient un
   outil dans un autre modèle (**sous-modèle**).
2. Reliez la sortie de `ModeleExposition` à l'entrée de `ModeleCinemas`, et ainsi de
   suite. Pour que ce soit possible, la couche des lycées doit avoir été déclarée comme
   **paramètre** dans chaque modèle (étape 12 de la Partie 3).
3. Exposez `Rayon_m` comme seul paramètre : en un clic, toute la chaîne est relancée
   pour 300 m ou 1 000 m.
4. **ModelBuilder > Exporter > Exporter vers un fichier Python** : comparez votre script
   avec la correction `scripts/02_correction_modeles.py`.
5. Bonus : partagez la boîte à outils (`.atbx`) avec un camarade. Il suffit qu'il change
   les paramètres d'entrée pour l'appliquer à une autre région, par exemple
   Auvergne-Rhône-Alpes.

---

## Partie 8 : questions d'analyse

1. Combien de lycées ont au moins un fast-food à moins de 300 m ? 500 m ? 1 000 m ?
   Faites un tableau. La relation est-elle linéaire ?
2. Quelle est la distance médiane lycée → fast-food le plus proche, et lycée → cinéma le
   plus proche ? (Clic droit sur le champ > **Statistiques**.)
3. Les lycées **privés** sont-ils plus ou moins exposés que les lycées **publics** ?
   (Outil *Statistiques récapitulatives*, champ de regroupement `Statut`.)
4. Les lycées **professionnels** sont-ils plus exposés ? (`Type_Lycee` de la Partie 2.)
5. Si l'IPS est présent : diagramme de dispersion (*Créer un diagramme > Nuage de
   points*) de `IPS` en fonction de `NB_FF`. Y a-t-il une corrélation ? Peut-on parler de
   causalité ?
6. Les lycées **sans cantine** (`Cantine = 0`) ont-ils plus de fast-foods autour ?
7. Les points chauds de fast-foods coïncident-ils avec les points froids de l'indice ?
   Quelle est la part de l'effet « Paris centre » ?
8. Limites : OSM n'est pas exhaustif (en particulier en grande couronne), la distance
   est à vol d'oiseau (et non à pied), l'indice repose sur des pondérations arbitraires.
   Comment améliorer l'analyse ? (Pistes : Network Analyst et zones de desserte
   piétonnes de 10 minutes ; données SIRENE avec le code NAF 56.10C « restauration
   rapide » pour compléter OSM.)

---

## Annexe : récapitulatif des outils

| Outil (FR) | Outil (EN) | Boîte à outils | Utilisé dans |
|---|---|---|---|
| Calculer une valeur | Calculate Value | ModelBuilder > Utilitaires | M1 |
| Copier des entités | Copy Features | Gestion des données | M1, M3 |
| Proximité | Near | Analyse | M1, M2 |
| Générer une table de proximité | Generate Near Table | Analyse | M1 |
| Statistiques récapitulatives | Summary Statistics | Analyse | M1 |
| Joindre un champ | Join Field | Gestion des données | M1, M2 |
| Calculer un champ | Calculate Field | Gestion des données | M1, M3, M4 |
| Modifier un champ / Supprimer un champ | Alter Field / Delete Field | Gestion des données | M1, M2, M3 |
| Créer des polygones de Thiessen | Create Thiessen Polygons | Analyse | M2 |
| Découper | Clip | Analyse | M2 |
| Synthétiser à l'intérieur | Summarize Within | Analyse | M2, M3, M4 |
| Générer une tessellation | Generate Tessellation | Gestion des données | M3 |
| Sélectionner une couche par emplacement | Select Layer By Location | Gestion des données | M3 |
| Analyse de points chauds optimisée | Optimized Hot Spot Analysis | Statistiques spatiales | M3 |
| Densité de noyau | Kernel Density | Spatial Analyst | M3 (option) |
| Extraire les valeurs vers des points | Extract Values to Points | Spatial Analyst | M3 (option) |
| Itérer les valeurs de champ | Iterate Field Values | ModelBuilder > Itérateurs | M4 |
| Sélectionner | Select | Analyse | M4 |
| Si le nombre de lignes est | If Row Count Is | ModelBuilder > Logique | M4 |
| Exporter des entités | Export Features | Conversion | M4 |
| Collecter des valeurs | Collect Values | ModelBuilder > Utilitaires | M4 |
| Combiner | Merge | Gestion des données | M4 |

## Annexe : dépannage

| Problème | Solution |
|---|---|
| `Classe_Expo` reste vide | Vérifiez que `NB_FF` a bien été calculé avant (ordre des outils : la sortie de l'un doit être l'entrée du suivant). |
| « Le champ NEAR_DIST n'existe pas » dans le modèle 2 | Le modèle 1 l'a déjà renommé. C'est normal : *Proximité* le recrée, vérifiez que *Modifier un champ* prend bien la sortie de *Proximité*. |
| Erreur « champ existe déjà » en relançant un modèle | Activez **Projet > Options > Géotraitement > Autoriser les outils à remplacer les jeux de données existants**, ou supprimez la sortie. |
| `%Value%` apparaît tel quel dans un nom | La variable n'est pas reliée : ajoutez une **Condition préalable** depuis `Value`. |
| *Densité de noyau* grisé | Extension Spatial Analyst non disponible : faites l'étape 9 du modèle 3 avec les hexagones uniquement. |
| Thiessen : avertissement « points coïncidents » | Deux cinémas à la même adresse : un seul polygone est créé, c'est sans conséquence ici. |
