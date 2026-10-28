# -*- coding: utf-8 -*-
"""
02_correction_modeles.py
========================

Équivalent Python (arcpy) des 4 modèles ModelBuilder du tutoriel.
C'est ce que vous obtiendriez (en plus lisible) avec  ModelBuilder > Exporter >
Exporter vers un fichier Python. À utiliser pour vérifier vos résultats.

  Modèle 1 - ModeleExposition   : exposition des lycées aux fast-foods (rayon paramétrable)
  Modèle 2 - ModeleCinemas      : accès des lycées aux cinémas + zones d'influence (Thiessen)
  Modèle 3 - ModeleTerritoire   : indice d'environnement, maillage hexagonal, points chauds
  Modèle 4 - ModeleDepartements : itération par département, condition, fusion

Lancer dans la fenêtre Python d'ArcGIS Pro (projet LyceesFastFoodIDF ouvert) après
avoir adapté les deux chemins ci-dessous.
"""

import os

import arcpy

# --------------------------------------------------------------------------------------
# Chemins à adapter
# --------------------------------------------------------------------------------------
SRC = os.path.join(os.path.expanduser("~"), "Documents", "ArcGIS", "Projects",
                   "DonneesLyceesIDF", "Donnees_Lycees_IDF.gdb")
OUT = os.path.join(os.path.expanduser("~"), "Documents", "ArcGIS", "Projects",
                   "LyceesFastFoodIDF", "LyceesFastFoodIDF.gdb")
RAYON_M = 500

LYCEES = os.path.join(SRC, "Lycees_IDF")
CINEMAS = os.path.join(SRC, "Cinemas_IDF")
FASTFOOD = os.path.join(SRC, "FastFood_IDF")
COMMUNES = os.path.join(SRC, "Communes_IDF")
DEPARTEMENTS = os.path.join(SRC, "Departements_IDF")
LIMITE = os.path.join(SRC, "Limite_IDF")

arcpy.env.overwriteOutput = True
arcpy.env.workspace = OUT

# Blocs de code des outils « Calculer un champ » (identiques à ceux du tutoriel)
CODE_NZ = """def nz(v):
    return 0 if v is None else int(v)"""

CODE_CLASSE = """def classe(nb):
    if nb == 0:
        return "Aucune"
    elif nb <= 2:
        return "Faible"
    elif nb <= 5:
        return "Moyenne"
    elif nb <= 10:
        return "Forte"
    return "Très forte\""""

CODE_INDICE = """def indice(nb_ff, d_ff, d_cine):
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
    return max(0, min(100, score))"""

CODE_RATIO = """def ratio(nb, pop):
    if not pop:
        return None
    return round(nb / pop * 10000, 2)"""


def gdb(nom):
    return os.path.join(OUT, nom)


# --------------------------------------------------------------------------------------
# Modèle 1 : exposition aux fast-foods
# --------------------------------------------------------------------------------------
def modele_exposition(rayon_m=RAYON_M):
    rayon = "%d Meters" % rayon_m                      # = outil « Calculer une valeur »
    lycees = gdb("Lycees_Expo_%dm" % rayon_m)

    arcpy.management.CopyFeatures(LYCEES, lycees)

    # Distance au fast-food le plus proche (sans limite de distance)
    arcpy.analysis.Near(lycees, FASTFOOD)
    arcpy.management.AlterField(lycees, "NEAR_DIST", "Dist_FF", "Distance fast-food (m)")
    arcpy.management.DeleteField(lycees, "NEAR_FID")

    # Nombre de fast-foods dans le rayon : table de proximité 1-n puis agrégation
    table = gdb("Proxi_FF_%dm" % rayon_m)
    arcpy.analysis.GenerateNearTable(lycees, FASTFOOD, table, rayon, "NO_LOCATION",
                                     "NO_ANGLE", "ALL", 0, "PLANAR")
    stats = gdb("Stats_FF_%dm" % rayon_m)
    arcpy.analysis.Statistics(table, stats, [["NEAR_FID", "COUNT"]], "IN_FID")
    arcpy.management.JoinField(lycees, "OBJECTID", stats, "IN_FID", ["COUNT_NEAR_FID"])

    # Les lycées sans fast-food dans le rayon ont <Null> après la jointure -> 0
    arcpy.management.CalculateField(lycees, "NB_FF", "nz(!COUNT_NEAR_FID!)", "PYTHON3",
                                    CODE_NZ, "LONG")
    arcpy.management.DeleteField(lycees, "COUNT_NEAR_FID")
    arcpy.management.CalculateField(lycees, "Classe_Expo", "classe(!NB_FF!)", "PYTHON3",
                                    CODE_CLASSE, "TEXT")
    return lycees


# --------------------------------------------------------------------------------------
# Modèle 2 : accès aux cinémas
# --------------------------------------------------------------------------------------
def modele_cinemas(lycees):
    # Cinéma le plus proche de chaque lycée + ses attributs
    arcpy.analysis.Near(lycees, CINEMAS)
    arcpy.management.AlterField(lycees, "NEAR_DIST", "Dist_Cine", "Distance cinéma (m)")
    arcpy.management.AlterField(lycees, "NEAR_FID", "FID_Cine", "Identifiant cinéma")
    arcpy.management.JoinField(lycees, "FID_Cine", CINEMAS, "OBJECTID",
                               ["Nom_Cinema", "Ecrans"])

    # Zones d'influence des cinémas (Thiessen) découpées sur l'Île-de-France
    thiessen = gdb("Thiessen_Cinemas")
    arcpy.analysis.CreateThiessenPolygons(CINEMAS, thiessen, "ALL")
    zones = gdb("Zones_Cinemas")
    arcpy.analysis.Clip(thiessen, LIMITE, zones)

    # Nombre de lycées (et exposition moyenne) dans la zone d'influence de chaque cinéma
    zones_lycees = gdb("Zones_Cinemas_Lycees")
    arcpy.analysis.SummarizeWithin(zones, lycees, zones_lycees, "KEEP_ALL",
                                   [["NB_FF", "Mean"]], "ADD_SHAPE_SUM")
    return zones_lycees


# --------------------------------------------------------------------------------------
# Modèle 3 : indice d'environnement, maillage hexagonal, points chauds
# --------------------------------------------------------------------------------------
def modele_territoire(lycees):
    arcpy.management.CalculateField(lycees, "Indice_Env",
                                    "indice(!NB_FF!, !Dist_FF!, !Dist_Cine!)", "PYTHON3",
                                    CODE_INDICE, "SHORT")

    # Maillage hexagonal de 1 km² limité à l'Île-de-France
    hex_brut = gdb("Hex_Brut")
    arcpy.management.GenerateTessellation(hex_brut, arcpy.Describe(LIMITE).extent,
                                          "HEXAGON", "1 SquareKilometers",
                                          arcpy.Describe(LIMITE).spatialReference)
    couche = arcpy.management.MakeFeatureLayer(hex_brut, "hex_lyr")
    arcpy.management.SelectLayerByLocation(couche, "INTERSECT", LIMITE)
    hex_idf = gdb("Hex_IDF")
    arcpy.management.CopyFeatures(couche, hex_idf)

    # Comptages successifs dans les hexagones (renommage pour ne pas écraser Point_Count)
    hex_ff = gdb("Hex_FF")
    arcpy.analysis.SummarizeWithin(hex_idf, FASTFOOD, hex_ff, "KEEP_ALL")
    arcpy.management.AlterField(hex_ff, "Point_Count", "NB_FF", "Nb fast-foods")
    hex_final = gdb("Hex_FF_Lycees")
    arcpy.analysis.SummarizeWithin(hex_ff, lycees, hex_final, "KEEP_ALL")
    arcpy.management.AlterField(hex_final, "Point_Count", "NB_LYC", "Nb lycées")

    # Points chauds : concentrations significatives de fast-foods / d'indices faibles
    arcpy.stats.OptimizedHotSpotAnalysis(hex_final, gdb("HotSpot_FF_Hex"), "NB_FF")
    arcpy.stats.OptimizedHotSpotAnalysis(lycees, gdb("HotSpot_Indice_Lycees"), "Indice_Env")

    # Option Spatial Analyst : densité de noyau + valeur sous chaque lycée
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
        densite = arcpy.sa.KernelDensity(FASTFOOD, "NONE", 100, 1000, "SQUARE_KILOMETERS")
        densite.save(gdb("Densite_FF"))
        arcpy.sa.ExtractValuesToPoints(lycees, gdb("Densite_FF"), gdb("Lycees_DensiteFF"))
        arcpy.CheckInExtension("Spatial")

    arcpy.management.Delete(hex_brut)
    return hex_final


# --------------------------------------------------------------------------------------
# Modèle 4 : itération par département
# --------------------------------------------------------------------------------------
def modele_departements(lycees):
    codes = sorted({r[0] for r in arcpy.da.SearchCursor(DEPARTEMENTS, ["Code_Dep"])})
    sorties = []  # = outil « Collecter des valeurs »
    for code in codes:  # = itérateur « Itérer les valeurs de champ » (%Value%)
        communes_dep = gdb("Communes_%s" % code)
        arcpy.analysis.Select(COMMUNES, communes_dep, "Code_Dep = '%s'" % code)

        ff_communes = gdb("FF_Communes_%s" % code)
        arcpy.analysis.SummarizeWithin(communes_dep, FASTFOOD, ff_communes, "KEEP_ALL")
        arcpy.management.CalculateField(ff_communes, "FF_10000hab",
                                        "ratio(!Point_Count!, !Population!)", "PYTHON3",
                                        CODE_RATIO, "DOUBLE")
        sorties.append(ff_communes)

        # Logique « Si le nombre de lignes est » : alerte uniquement s'il y a des lycées
        # très exposés dans le département
        tres_exposes = arcpy.management.MakeFeatureLayer(
            lycees, "tres_exposes_%s" % code,
            "Code_Dep = '%s' AND Classe_Expo = 'Très forte'" % code)
        if int(arcpy.management.GetCount(tres_exposes)[0]) > 0:
            arcpy.conversion.ExportFeatures(tres_exposes, gdb("Alerte_Lycees_%s" % code))
        arcpy.management.Delete(communes_dep)

    fusion = gdb("FF_Communes_IDF")
    arcpy.management.Merge(sorties, fusion)  # = outil « Combiner »
    return fusion


if __name__ == "__main__":
    lyc = modele_exposition(RAYON_M)
    modele_cinemas(lyc)
    modele_territoire(lyc)
    modele_departements(lyc)
    print("Modèles exécutés. Résultats dans", OUT)
