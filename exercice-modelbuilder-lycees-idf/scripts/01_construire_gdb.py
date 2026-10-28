# -*- coding: utf-8 -*-
"""
01_construire_gdb.py
====================

Construit la géodatabase fichier Donnees_Lycees_IDF.gdb (Lambert-93, EPSG:2154)
à partir de données ouvertes :

  - Lycées d'Île-de-France ....... Annuaire de l'éducation (data.education.gouv.fr)
  - IPS des lycées (optionnel) ... Indice de position sociale (data.education.gouv.fr)
  - Cinémas d'Île-de-France ...... Établissements cinématographiques CNC (data.culture.gouv.fr)
  - Fast-foods d'Île-de-France ... OpenStreetMap, amenity=fast_food (API Overpass)
  - Communes d'Île-de-France ..... API Découpage administratif (geo.api.gouv.fr)

Le script fonctionne en deux étapes :

  1. TÉLÉCHARGEMENT : les fichiers bruts sont enregistrés dans <dossier>/brut/.
     Cette étape n'a pas besoin d'arcpy (python "normal" suffit).
     Si un téléchargement échoue (proxy de l'université, site en panne...), téléchargez
     le fichier à la main (voir README) et déposez-le dans brut/ sous le nom attendu :
        brut/lycees.csv   brut/ips_lycees.csv   brut/cinemas.csv
        brut/fastfood.json   brut/communes.geojson   brut/arrondissements.geojson
     Un fichier déjà présent n'est jamais retéléchargé (supprimez-le pour le rafraîchir).

  2. CONSTRUCTION : lecture des fichiers bruts, filtrage Île-de-France, nettoyage,
     création des classes d'entités puis projection en Lambert-93. Nécessite arcpy
     (ArcGIS Pro).

Utilisation
-----------
  Dans ArcGIS Pro : Analyse > Python > Fenêtre Python, puis
      exec(open(r"C:\\chemin\\vers\\01_construire_gdb.py", encoding="utf-8").read())
  ou en ligne de commande (invite de commandes Python d'ArcGIS Pro) :
      propy 01_construire_gdb.py  [dossier_de_sortie]  [--telecharger-seulement]

Par défaut, le dossier de sortie est  Documents\\ArcGIS\\Projects\\DonneesLyceesIDF
"""

import csv
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

# --------------------------------------------------------------------------------------
# Paramètres
# --------------------------------------------------------------------------------------
DOSSIER_DEFAUT = os.path.join(os.path.expanduser("~"), "Documents", "ArcGIS",
                              "Projects", "DonneesLyceesIDF")
NOM_GDB = "Donnees_Lycees_IDF.gdb"

DEPS_IDF = {
    "75": "Paris", "77": "Seine-et-Marne", "78": "Yvelines", "91": "Essonne",
    "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis", "94": "Val-de-Marne",
    "95": "Val-d'Oise",
}
# Emprise approximative de l'Île-de-France (WGS84) pour écarter les coordonnées aberrantes
BBOX_IDF = (1.40, 48.10, 3.60, 49.25)  # lon_min, lat_min, lon_max, lat_max

ODS_EDUCATION = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/"
ODS_CULTURE = "https://data.culture.gouv.fr/api/explore/v2.1/catalog/datasets/"

SOURCES = {
    "lycees.csv": ODS_EDUCATION + "fr-en-annuaire-education/exports/csv?" + urllib.parse.urlencode(
        {"where": 'type_etablissement="Lycée"', "delimiter": ";"}),
    "ips_lycees.csv": ODS_EDUCATION + "fr-en-ips-lycees-ap2022/exports/csv?" + urllib.parse.urlencode(
        {"delimiter": ";"}),
    "cinemas.csv": ODS_CULTURE + "etablissements-cinematographiques/exports/csv?" + urllib.parse.urlencode(
        {"delimiter": ";"}),
    "communes.geojson": "https://geo.api.gouv.fr/communes?" + urllib.parse.urlencode(
        {"codeRegion": "11", "fields": "nom,code,codeDepartement,population",
         "format": "geojson", "geometry": "contour"}),
    "arrondissements.geojson": "https://geo.api.gouv.fr/communes?" + urllib.parse.urlencode(
        {"codeDepartement": "75", "type": "arrondissement-municipal",
         "fields": "nom,code,codeDepartement,population",
         "format": "geojson", "geometry": "contour"}),
}
OPTIONNELS = {"ips_lycees.csv", "arrondissements.geojson"}

OVERPASS_SERVEURS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_REQUETE = """
[out:json][timeout:300];
area["ISO3166-2"="FR-IDF"]->.idf;
nwr["amenity"="fast_food"](area.idf);
out center tags;
"""

USER_AGENT = "Exercice-ModelBuilder-Lycees-IDF/1.0 (usage pedagogique)"


# --------------------------------------------------------------------------------------
# Outils génériques
# --------------------------------------------------------------------------------------
def log(msg):
    print(msg)
    try:  # affiche aussi dans la fenêtre de géotraitement si lancé comme outil de script
        import arcpy
        arcpy.AddMessage(msg)
    except Exception:
        pass


def normaliser(texte):
    """'Entrées 2023' -> 'entrees_2023' (minuscules, sans accents, séparateur _)."""
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", texte.lower()).strip("_")


def telecharger(url, chemin, data=None, timeout=300):
    requete = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:
        contenu = reponse.read()
    if not contenu:
        raise IOError("réponse vide")
    with open(chemin, "wb") as f:
        f.write(contenu)
    return len(contenu)


class PointVirgule(csv.excel):
    delimiter = ";"


def lire_csv(chemin):
    """Renvoie (liste de dict avec clés normalisées, liste des en-têtes normalisés)."""
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        echantillon = f.read(20000)
        f.seek(0)
        try:
            dialecte = csv.Sniffer().sniff(echantillon, delimiters=";,\t")
        except csv.Error:
            dialecte = PointVirgule
        lecteur = csv.reader(f, dialecte)
        entetes = [normaliser(h) for h in next(lecteur)]
        lignes = [dict(zip(entetes, ligne)) for ligne in lecteur if ligne]
    return lignes, entetes


def trouver_colonne(entetes, *candidats, contient=None, obligatoire=False):
    """Cherche la première colonne existante parmi les candidats (noms normalisés),
    sinon la première colonne contenant tous les morceaux de `contient`."""
    for c in candidats:
        if c in entetes:
            return c
    if contient:
        for e in entetes:
            if all(m in e for m in contient):
                return e
    if obligatoire:
        raise KeyError("Colonne introuvable parmi %s. Colonnes disponibles : %s"
                       % (list(candidats) or contient, ", ".join(entetes)))
    return None


def nombre(valeur, entier=False):
    if valeur is None:
        return None
    valeur = str(valeur).strip().replace("\u202f", "").replace(" ", "").replace(",", ".")
    if valeur == "":
        return None
    try:
        return int(float(valeur)) if entier else float(valeur)
    except ValueError:
        return None


def texte(valeur, longueur=254):
    if valeur is None:
        return None
    valeur = str(valeur).strip()
    return valeur[:longueur] if valeur else None


def dans_idf(lon, lat):
    return (lon is not None and lat is not None
            and BBOX_IDF[0] <= lon <= BBOX_IDF[2] and BBOX_IDF[1] <= lat <= BBOX_IDF[3])


def lire_latlon(ligne, entetes):
    """Coordonnées WGS84 (lon, lat) d'une ligne, quel que soit le format de la source."""
    c_lat = trouver_colonne(entetes, "latitude", "lat", "coordonnees_latitude")
    c_lon = trouver_colonne(entetes, "longitude", "lon", "lng", "coordonnees_longitude")
    if c_lat and c_lon:
        lat, lon = nombre(ligne.get(c_lat)), nombre(ligne.get(c_lon))
        if lat is not None and lon is not None:
            return lon, lat
    c_geo = trouver_colonne(entetes, "position", "geolocalisation", "geo_point_2d",
                            "geopoint", "coordonnees", "geo_point")
    if c_geo and ligne.get(c_geo):
        morceaux = re.split(r"[,;\s]+", ligne[c_geo].strip())
        if len(morceaux) >= 2:
            lat, lon = nombre(morceaux[0]), nombre(morceaux[1])
            if lat is not None and lon is not None:
                return lon, lat
    return None, None


def code_dep(code_commune):
    code = (code_commune or "").strip()
    return code[:2] if len(code) >= 2 else None


# --------------------------------------------------------------------------------------
# Étape 1 : téléchargement
# --------------------------------------------------------------------------------------
def telecharger_tout(dossier_brut):
    os.makedirs(dossier_brut, exist_ok=True)
    manquants = []

    for nom, url in SOURCES.items():
        chemin = os.path.join(dossier_brut, nom)
        if os.path.exists(chemin):
            log("  [déjà présent] " + nom)
            continue
        log("  Téléchargement de %s ..." % nom)
        try:
            taille = telecharger(url, chemin)
            log("    OK (%.1f Mo)" % (taille / 1e6))
        except Exception as e:
            log("    ÉCHEC : %s" % e)
            if nom not in OPTIONNELS:
                manquants.append((nom, url))

    chemin = os.path.join(dossier_brut, "fastfood.json")
    if os.path.exists(chemin):
        log("  [déjà présent] fastfood.json")
    else:
        donnees = urllib.parse.urlencode({"data": OVERPASS_REQUETE}).encode()
        for serveur in OVERPASS_SERVEURS:
            log("  Téléchargement des fast-foods OSM via %s ..." % serveur)
            try:
                taille = telecharger(serveur, chemin, data=donnees, timeout=400)
                log("    OK (%.1f Mo)" % (taille / 1e6))
                break
            except Exception as e:
                log("    ÉCHEC : %s" % e)
                time.sleep(5)
        else:
            manquants.append(("fastfood.json", "https://overpass-turbo.eu (voir README)"))

    if manquants:
        log("\nFichiers à télécharger manuellement puis à déposer dans %s :" % dossier_brut)
        for nom, url in manquants:
            log("  - %s  <-  %s" % (nom, url))
    return not manquants


# --------------------------------------------------------------------------------------
# Étape 2 : lecture / nettoyage (Python pur, testable sans ArcGIS)
# --------------------------------------------------------------------------------------
def lire_ips(chemin):
    """Dictionnaire UAI -> IPS (rentrée la plus récente)."""
    if not os.path.exists(chemin):
        return {}
    lignes, entetes = lire_csv(chemin)
    c_uai = trouver_colonne(entetes, "uai", "code_uai", "numero_uai", contient=("uai",))
    c_ips = trouver_colonne(entetes, "ips_ensemble_gt_pro", "ips_etab", "ips",
                            "ips_voie_gt", contient=("ips",))
    c_rentree = trouver_colonne(entetes, "rentree_scolaire", "rentree", contient=("rentree",))
    if not (c_uai and c_ips):
        log("  IPS : colonnes non reconnues, IPS ignoré")
        return {}
    ips = {}
    for l in lignes:
        uai, valeur = (l.get(c_uai) or "").strip().upper(), nombre(l.get(c_ips))
        if not uai or valeur is None:
            continue
        rentree = l.get(c_rentree, "") if c_rentree else ""
        if uai not in ips or rentree > ips[uai][0]:
            ips[uai] = (rentree, valeur)
    return {uai: v for uai, (_, v) in ips.items()}


def lire_lycees(chemin, ips=None):
    ips = ips or {}
    lignes, e = lire_csv(chemin)
    c_uai = trouver_colonne(e, "identifiant_de_l_etablissement", "uai", "numero_uai", obligatoire=True)
    c_nom = trouver_colonne(e, "nom_etablissement", "appellation_officielle", "nom", obligatoire=True)
    c_type = trouver_colonne(e, "type_etablissement")
    c_etat = trouver_colonne(e, "etat")
    c_statut = trouver_colonne(e, "statut_public_prive", "secteur", "secteur_public_prive")
    c_commune = trouver_colonne(e, "nom_commune", "libelle_commune", "commune")
    c_code_com = trouver_colonne(e, "code_commune", "code_insee", "code_insee_commune")
    c_cp = trouver_colonne(e, "code_postal")
    c_vg = trouver_colonne(e, "voie_generale")
    c_vt = trouver_colonne(e, "voie_technologique")
    c_vp = trouver_colonne(e, "voie_professionnelle")
    c_eleves = trouver_colonne(e, "nombre_d_eleves", "effectif", contient=("eleves",))
    c_resto = trouver_colonne(e, "restauration")

    resultat, vus = [], set()
    for l in lignes:
        if c_type and not l.get(c_type, "").lower().startswith("lyc"):
            continue
        if c_etat and l.get(c_etat) and l[c_etat].upper() != "OUVERT":
            continue
        code_com = (l.get(c_code_com) if c_code_com else "") or ""
        dep = code_dep(code_com) or code_dep(l.get(c_cp) if c_cp else "")
        if dep not in DEPS_IDF:
            continue
        lon, lat = lire_latlon(l, e)
        if not dans_idf(lon, lat):
            continue
        uai = l[c_uai].strip().upper()
        if uai in vus:
            continue
        vus.add(uai)
        resultat.append({
            "lon": lon, "lat": lat,
            "UAI": uai,
            "Nom_Lycee": texte(l.get(c_nom)),
            "Statut": texte(l.get(c_statut)) if c_statut else None,
            "Commune": texte(l.get(c_commune)) if c_commune else None,
            "Code_Com": texte(code_com, 5),
            "Code_Dep": dep,
            "Voie_Gen": nombre(l.get(c_vg), True) if c_vg else None,
            "Voie_Tech": nombre(l.get(c_vt), True) if c_vt else None,
            "Voie_Pro": nombre(l.get(c_vp), True) if c_vp else None,
            "Nb_Eleves": nombre(l.get(c_eleves), True) if c_eleves else None,
            "Cantine": nombre(l.get(c_resto), True) if c_resto else None,
            "IPS": ips.get(uai),
        })
    return resultat


def lire_cinemas(chemin):
    lignes, e = lire_csv(chemin)
    c_nom = trouver_colonne(e, "nom", "nom_etablissement", obligatoire=True)
    c_commune = trouver_colonne(e, "commune", "nom_commune")
    c_code_com = trouver_colonne(e, "code_insee", "code_commune", contient=("insee",))
    c_dep = trouver_colonne(e, "dep", "departement", "code_departement")
    c_ecrans = trouver_colonne(e, "ecrans", "nombre_d_ecrans", contient=("ecran",))
    c_fauteuils = trouver_colonne(e, "fauteuils", "nombre_de_fauteuils", contient=("fauteuil",))
    c_multi = trouver_colonne(e, "multiplexe")
    c_ae = trouver_colonne(e, "ae", "art_et_essai", contient=("art", "essai"))
    # colonne des entrées la plus récente : entrees_2024 > entrees_2023 > ...
    cols_entrees = sorted(c for c in e if re.fullmatch(r"entrees_\d{4}", c))
    c_entrees = cols_entrees[-1] if cols_entrees else None

    resultat = []
    for l in lignes:
        code_com = (l.get(c_code_com) if c_code_com else "") or ""
        dep = code_dep(code_com) or (l.get(c_dep, "").strip().zfill(2)[:2] if c_dep else None)
        if dep not in DEPS_IDF:
            continue
        lon, lat = lire_latlon(l, e)
        if not dans_idf(lon, lat):
            continue
        resultat.append({
            "lon": lon, "lat": lat,
            "Nom_Cinema": texte(l.get(c_nom)),
            "Commune": texte(l.get(c_commune)) if c_commune else None,
            "Code_Com": texte(code_com, 5),
            "Code_Dep": dep,
            "Ecrans": nombre(l.get(c_ecrans), True) if c_ecrans else None,
            "Fauteuils": nombre(l.get(c_fauteuils), True) if c_fauteuils else None,
            "Entrees": nombre(l.get(c_entrees), True) if c_entrees else None,
            "Annee_Entrees": int(c_entrees[-4:]) if c_entrees else None,
            "Multiplexe": texte(l.get(c_multi), 10) if c_multi else None,
            "Art_Essai": texte(l.get(c_ae), 50) if c_ae else None,
        })
    return resultat


def lire_fastfoods(chemin):
    with open(chemin, encoding="utf-8") as f:
        donnees = json.load(f)
    resultat = []
    for el in donnees.get("elements", []):
        if "lat" in el:
            lon, lat = el["lon"], el["lat"]
        elif "center" in el:
            lon, lat = el["center"]["lon"], el["center"]["lat"]
        else:
            continue
        if not dans_idf(lon, lat):
            continue
        tags = el.get("tags", {})
        enseigne = tags.get("brand") or None
        resultat.append({
            "lon": lon, "lat": lat,
            "OSM_ID": "%s%s" % (el.get("type", "?")[0], el.get("id")),
            "Nom_FF": texte(tags.get("name")),
            "Enseigne": texte(enseigne, 100),
            "Cuisine": texte(tags.get("cuisine"), 100),
            "Chaine": "Oui" if (enseigne or tags.get("brand:wikidata")) else "Non",
        })
    return resultat


def lire_communes(chemin_communes, chemin_arrondissements):
    with open(chemin_communes, encoding="utf-8") as f:
        entites = json.load(f)["features"]
    if os.path.exists(chemin_arrondissements):
        with open(chemin_arrondissements, encoding="utf-8") as f:
            arrondissements = json.load(f).get("features", [])
        if arrondissements:  # Paris (75056) est remplacé par ses 20 arrondissements
            entites = [c for c in entites if c["properties"].get("code") != "75056"]
            entites += arrondissements
    resultat = []
    for c in entites:
        p = c["properties"]
        dep = p.get("codeDepartement") or code_dep(p.get("code"))
        if dep not in DEPS_IDF or not c.get("geometry"):
            continue
        resultat.append({
            "geometrie": c["geometry"],
            "Nom_Com": texte(p.get("nom")),
            "Code_Com": texte(p.get("code"), 5),
            "Code_Dep": dep,
            "Population": nombre(p.get("population"), True),
        })
    return resultat


# --------------------------------------------------------------------------------------
# Étape 3 : écriture dans la géodatabase (arcpy)
# --------------------------------------------------------------------------------------
CHAMPS = {
    "Lycees_IDF": [("UAI", "TEXT", 10), ("Nom_Lycee", "TEXT", 254), ("Statut", "TEXT", 20),
                   ("Commune", "TEXT", 100), ("Code_Com", "TEXT", 5), ("Code_Dep", "TEXT", 2),
                   ("Voie_Gen", "SHORT", None), ("Voie_Tech", "SHORT", None),
                   ("Voie_Pro", "SHORT", None), ("Nb_Eleves", "LONG", None),
                   ("Cantine", "SHORT", None), ("IPS", "DOUBLE", None)],
    "Cinemas_IDF": [("Nom_Cinema", "TEXT", 254), ("Commune", "TEXT", 100),
                    ("Code_Com", "TEXT", 5), ("Code_Dep", "TEXT", 2), ("Ecrans", "SHORT", None),
                    ("Fauteuils", "LONG", None), ("Entrees", "LONG", None),
                    ("Annee_Entrees", "SHORT", None), ("Multiplexe", "TEXT", 10),
                    ("Art_Essai", "TEXT", 50)],
    "FastFood_IDF": [("OSM_ID", "TEXT", 20), ("Nom_FF", "TEXT", 254), ("Enseigne", "TEXT", 100),
                     ("Cuisine", "TEXT", 100), ("Chaine", "TEXT", 3)],
    "Communes_IDF": [("Nom_Com", "TEXT", 100), ("Code_Com", "TEXT", 5), ("Code_Dep", "TEXT", 2),
                     ("Population", "LONG", None)],
}


def ecrire_classe(arcpy, gdb_temp, gdb, nom, type_geom, enregistrements):
    sr_wgs84 = arcpy.SpatialReference(4326)
    sr_l93 = arcpy.SpatialReference(2154)
    temp = os.path.join(gdb_temp, nom + "_wgs84")
    if arcpy.Exists(temp):
        arcpy.management.Delete(temp)
    arcpy.management.CreateFeatureclass(gdb_temp, nom + "_wgs84", type_geom,
                                        spatial_reference=sr_wgs84)
    champs = CHAMPS[nom]
    for nom_champ, type_champ, longueur in champs:
        arcpy.management.AddField(temp, nom_champ, type_champ, field_length=longueur)

    noms = [c[0] for c in champs]
    if type_geom == "POINT":
        with arcpy.da.InsertCursor(temp, ["SHAPE@XY"] + noms) as curseur:
            for r in enregistrements:
                curseur.insertRow([(r["lon"], r["lat"])] + [r.get(n) for n in noms])
    else:
        with arcpy.da.InsertCursor(temp, ["SHAPE@"] + noms) as curseur:
            for r in enregistrements:
                geom = arcpy.AsShape(r["geometrie"])
                curseur.insertRow([geom] + [r.get(n) for n in noms])

    sortie = os.path.join(gdb, nom)
    if arcpy.Exists(sortie):
        arcpy.management.Delete(sortie)
    try:
        arcpy.management.Project(temp, sortie, sr_l93, "RGF_1993_To_WGS_1984_1")
    except Exception:
        arcpy.management.Project(temp, sortie, sr_l93)
    log("  %-14s : %5d entités" % (nom, int(arcpy.management.GetCount(sortie)[0])))
    return sortie


def construire_gdb(dossier):
    import arcpy  # uniquement nécessaire pour cette étape
    arcpy.env.overwriteOutput = True

    brut = os.path.join(dossier, "brut")
    for obligatoire in ("lycees.csv", "cinemas.csv", "fastfood.json", "communes.geojson"):
        if not os.path.exists(os.path.join(brut, obligatoire)):
            raise IOError("Fichier manquant : %s" % os.path.join(brut, obligatoire))

    log("Lecture et nettoyage des données brutes ...")
    ips = lire_ips(os.path.join(brut, "ips_lycees.csv"))
    lycees = lire_lycees(os.path.join(brut, "lycees.csv"), ips)
    cinemas = lire_cinemas(os.path.join(brut, "cinemas.csv"))
    fastfoods = lire_fastfoods(os.path.join(brut, "fastfood.json"))
    communes = lire_communes(os.path.join(brut, "communes.geojson"),
                             os.path.join(brut, "arrondissements.geojson"))
    log("  IPS trouvés pour %d lycées" % sum(1 for l in lycees if l["IPS"] is not None))

    gdb = os.path.join(dossier, NOM_GDB)
    gdb_temp = os.path.join(dossier, "_temp.gdb")
    for g in (gdb, gdb_temp):
        if not arcpy.Exists(g):
            arcpy.management.CreateFileGDB(dossier, os.path.basename(g))

    log("Création des classes d'entités (Lambert-93) dans %s ..." % gdb)
    ecrire_classe(arcpy, gdb_temp, gdb, "Lycees_IDF", "POINT", lycees)
    ecrire_classe(arcpy, gdb_temp, gdb, "Cinemas_IDF", "POINT", cinemas)
    ecrire_classe(arcpy, gdb_temp, gdb, "FastFood_IDF", "POINT", fastfoods)
    communes_fc = ecrire_classe(arcpy, gdb_temp, gdb, "Communes_IDF", "POLYGON", communes)

    log("Création des départements et de la limite régionale ...")
    deps = os.path.join(gdb, "Departements_IDF")
    arcpy.analysis.PairwiseDissolve(communes_fc, deps, "Code_Dep",
                                    [["Population", "SUM"]])
    arcpy.management.AlterField(deps, "SUM_Population", "Population", "Population")
    arcpy.management.CalculateField(deps, "Nom_Dep", "DEPS[!Code_Dep!]", "PYTHON3",
                                    "DEPS = %r" % DEPS_IDF, "TEXT")
    arcpy.analysis.PairwiseDissolve(communes_fc, os.path.join(gdb, "Limite_IDF"))

    arcpy.management.Delete(gdb_temp)
    log("\nTerminé : %s" % gdb)
    return gdb


# --------------------------------------------------------------------------------------
def main(arguments):
    options = [a for a in arguments if a.startswith("--")]
    positionnels = [a for a in arguments if a and not a.startswith("--")]
    dossier = positionnels[0] if positionnels else DOSSIER_DEFAUT
    os.makedirs(dossier, exist_ok=True)

    log("== Étape 1 : téléchargement dans %s ==" % os.path.join(dossier, "brut"))
    complet = telecharger_tout(os.path.join(dossier, "brut"))
    if "--telecharger-seulement" in options:
        return
    if not complet:
        log("\nDes fichiers obligatoires manquent : construction interrompue.")
        return
    log("\n== Étape 2 : construction de la géodatabase ==")
    construire_gdb(dossier)


if __name__ == "__main__":
    main(sys.argv[1:])
