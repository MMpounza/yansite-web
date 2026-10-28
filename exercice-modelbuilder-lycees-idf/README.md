# Exercice ModelBuilder : lycées, cinémas et fast-foods en Île-de-France

Exercice ArcGIS Pro personnalisé, dans la suite du tutoriel « Jeux Olympiques »
(zone tampon, itérateur, jointure spatiale). Il va au-delà de ces outils.

| Fichier | Rôle |
|---|---|
| [`TUTORIEL.md`](TUTORIEL.md) | Énoncé pas à pas : préparation de la GDB, 5 modèles, questions d'analyse |
| [`scripts/01_construire_gdb.py`](scripts/01_construire_gdb.py) | Télécharge les données ouvertes et construit `Donnees_Lycees_IDF.gdb` (Lambert-93) |
| [`scripts/02_correction_modeles.py`](scripts/02_correction_modeles.py) | Correction : équivalent arcpy des modèles |

## Démarrage rapide

1. Dans ArcGIS Pro, ouvrez **Analyse > Python > Fenêtre Python** et lancez :

   ```python
   exec(open(r"C:\chemin\vers\scripts\01_construire_gdb.py", encoding="utf-8").read())
   ```

2. La GDB est créée dans `Documents\ArcGIS\Projects\DonneesLyceesIDF\`.
3. Suivez [`TUTORIEL.md`](TUTORIEL.md) à partir de la Partie 1.3.

Pour choisir un autre dossier, lancez le script depuis l'invite de commandes Python
d'ArcGIS Pro :

```bash
propy 01_construire_gdb.py "D:\SIG\DonneesLyceesIDF"
```

## Téléchargement manuel

Si le script ne peut pas télécharger un fichier (proxy, site en maintenance...),
récupérez-le avec un navigateur, renommez-le et placez-le dans le dossier `brut\` :

| Nom attendu dans `brut\` | Où le trouver |
|---|---|
| `lycees.csv` | data.education.gouv.fr, jeu « Annuaire de l'éducation » (`fr-en-annuaire-education`). Filtrer *Type établissement = Lycée*, puis Export > CSV. |
| `ips_lycees.csv` *(facultatif)* | data.education.gouv.fr, « Indices de position sociale dans les lycées » (à partir de 2022). Export > CSV. |
| `cinemas.csv` | data.culture.gouv.fr, « Établissements cinématographiques » (CNC). Export > CSV. |
| `fastfood.json` | overpass-turbo.eu : collez la requête ci-dessous, **Exporter > Données brutes (JSON)**. |
| `communes.geojson` | `https://geo.api.gouv.fr/communes?codeRegion=11&fields=nom,code,codeDepartement,population&format=geojson&geometry=contour` |
| `arrondissements.geojson` *(facultatif)* | `https://geo.api.gouv.fr/communes?codeDepartement=75&type=arrondissement-municipal&fields=nom,code,codeDepartement,population&format=geojson&geometry=contour` |

Requête Overpass pour les fast-foods :

```
[out:json][timeout:300];
area["ISO3166-2"="FR-IDF"]->.idf;
nwr["amenity"="fast_food"](area.idf);
out center tags;
```

Le script reconnaît automatiquement les noms de colonnes : majuscules ou minuscules,
accents, coordonnées en deux colonnes (`latitude`/`longitude`) ou en une seule
(`"48.85, 2.35"`). Les fichiers facultatifs peuvent manquer : le champ `IPS` sera vide,
et Paris restera une seule commune au lieu de 20 arrondissements.

## Licences des données

- Annuaire de l'éducation et IPS : Licence Ouverte / Etalab 2.0, ministère de l'Éducation nationale
- Établissements cinématographiques : Licence Ouverte, CNC / ministère de la Culture
- Fast-foods : © contributeurs OpenStreetMap, licence ODbL
- Communes : API Découpage administratif (IGN / INSEE), Licence Ouverte
