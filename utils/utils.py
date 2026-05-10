import polars as pl
from chembl_webresource_client.new_client import new_client
import os
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
import matplotlib.pyplot as plt
import seaborn as sns

target_id = "CHEMBL2147" 
activity_type = "IC50"

def fetch_chembl_activity_to_polars(target_id=target_id, activity_type="IC50"):
    activity = new_client.activity
    query = activity.filter(target_chembl_id=target_id).filter(standard_type=activity_type)
    
    print(f"Pobieranie danych dla celu: {target_id}...")
    data = list(query)

    if data:
        df = pl.DataFrame(data, infer_schema_length=None)
        
        # Konwersja standard_value na float (jeśli istnieje)
        if "standard_value" in df.columns:
             df = df.with_columns(
                pl.col("standard_value").cast(pl.Float64, strict=False)
            )
        
        return df
    else:
        print("Nie znaleziono danych.")
        return pl.DataFrame()

def get_data_from_parquet(file_path = f"{target_id}_IC50.parquet"):
    if os.path.exists(file_path):
        print(f"Wczytywanie danych z pliku lokalnego: {file_path}")
        return pl.read_parquet(file_path)
    else:
        print(f"Plik nie istnieje: {file_path}")
        return None

        
def save_data_to_parquet(df, file_path = f"{target_id}_IC50.parquet"):
    if df is not None:
        print(f"Zapisywanie danych do pliku: {file_path}")
        df.write_parquet(file_path)
    else:
        print("Nie ma danych do zapisania.")


def fetch_chembl_data_with_properties(target_id=target_id, activity_type="IC50"):
    # 1. Pobieranie aktywności (Twój kod)
    print(f"Pobieranie aktywności dla celu: {target_id}...")
    activity_query = new_client.activity.filter(
        target_chembl_id=target_id, 
        standard_type=activity_type
    ).only(['molecule_chembl_id', 'standard_value', 'standard_units',
            'canonical_smiles', 'molecule_pref_name', 
            'standard_relation', 'target_organism'])
    
    act_data = list(activity_query)
    if not act_data:
        print("Nie znaleziono danych aktywności.")
        return pl.DataFrame()
    
    df_act = pl.DataFrame(act_data)

    # 2. Pobieranie właściwości cząsteczek (HBD, HBA, PSA)
    # Wyciągamy unikalne ID cząsteczek, żeby nie pytać o to samo dwa razy
    unique_mol_ids = df_act["molecule_chembl_id"].unique().to_list()
    
    print(f"Pobieranie właściwości dla {len(unique_mol_ids)} unikalnych cząsteczek...")
    mol_query = new_client.molecule.filter(
        molecule_chembl_id__in=unique_mol_ids
    ).only(['molecule_chembl_id', 'molecule_properties'])
    
    mol_data = list(mol_query)
    
    # 3. Tworzenie DataFrame z właściwościami i rozbijanie słownika na kolumny
    # Używamy Twojej prośby: wyciągamy do osobnych kolumn
    df_mol = pl.DataFrame(mol_data).with_columns([
        pl.col("molecule_properties").struct.field("hbd").alias("hbd"),
        pl.col("molecule_properties").struct.field("hba").alias("hba"),
        pl.col("molecule_properties").struct.field("psa").alias("psa"),
        pl.col("molecule_properties").struct.field("full_mwt").alias("mw")
    ]).drop("molecule_properties")

    # 4. Łączenie (Join) aktywności z właściwościami
    df_final = df_act.join(df_mol, on="molecule_chembl_id", how="left")

    # Konwersja typów (standard_value na float)
    if "standard_value" in df_final.columns:
        df_final = df_final.with_columns(
            pl.col("standard_value").cast(pl.Float64, strict=False)
        )


    desired_cols = [
        "molecule_chembl_id", "canonical_smiles", "molecule_pref_name",
        "standard_value", "standard_units", "standard_relation", "target_organism",
        "hbd", "hba", "psa", "mw"
    ]
    # Bierzemy tylko te, które faktycznie istnieją (bezpieczne)
    available = [c for c in desired_cols if c in df_final.columns]
    df_final = df_final.select(available)
    df_final = df_final.with_columns(
        (9 - pl.col("standard_value").log(10))
        .alias("pchembl_value"))
    df_final = df_final.with_columns(
        pl.col("canonical_smiles")
        .map_elements(lambda x: ECFP_from_smiles(x), return_dtype=pl.List(pl.Int64))
        .alias("ecfp_smiles")
    ) 
    #df_final = add_graph_features_to_df(df_final)
    

    return df_final



# define function that transforms SMILES strings into ECFPs
def ECFP_from_smiles(smiles,
                     R = 2,
                     L = 2**10,
                     use_features = False,
                     use_chirality = False):
    """
    Inputs:

    - smiles ... SMILES string of input compound
    - R ... maximum radius of circular substructures
    - L ... fingerprint-length
    - use_features ... if false then use standard DAYLIGHT atom features, if true then use pharmacophoric atom features
    - use_chirality ... if true then append tetrahedral chirality flags to atom features

    Outputs:
    - np.array(feature_list) ... ECFP with length L and maximum radius R
    """

    molecule = AllChem.MolFromSmiles(smiles)
    feature_list = AllChem.GetMorganFingerprintAsBitVect(molecule,
                                                                       radius = R,
                                                                       nBits = L,
                                                                       useFeatures = use_features,
                                                                       useChirality = use_chirality)
    return np.array(feature_list)


# ── Cechy grafu molekularnego (GNN) ──────────────────────────────────────────

# Pomocnicze mapowania enum → int
from rdkit.Chem import rdchem

_ATOM_SYMBOLS = ['C', 'N', 'O', 'S', 'F', 'Cl', 'Br', 'I', 'P', 'Si', 'B', 'Se']

_HYBRIDIZATION_MAP = {
    rdchem.HybridizationType.SP:      0,
    rdchem.HybridizationType.SP2:     1,
    rdchem.HybridizationType.SP3:     2,
    rdchem.HybridizationType.SP3D:    3,
    rdchem.HybridizationType.SP3D2:   4,
    rdchem.HybridizationType.S:       5,
}

_CHIRAL_MAP = {
    rdchem.ChiralType.CHI_UNSPECIFIED:       0,
    rdchem.ChiralType.CHI_TETRAHEDRAL_CW:    1,
    rdchem.ChiralType.CHI_TETRAHEDRAL_CCW:   2,
    rdchem.ChiralType.CHI_OTHER:             3,
}

_BOND_TYPE_MAP = {
    rdchem.BondType.SINGLE:   0,
    rdchem.BondType.DOUBLE:   1,
    rdchem.BondType.TRIPLE:   2,
    rdchem.BondType.AROMATIC: 3,
}

_BOND_STEREO_MAP = {
    rdchem.BondStereo.STEREONONE:   0,
    rdchem.BondStereo.STEREOANY:    1,
    rdchem.BondStereo.STEREOZ:      2,
    rdchem.BondStereo.STEREOE:      3,
    rdchem.BondStereo.STEREOCIS:    4,
    rdchem.BondStereo.STEREOTRANS:  5,
}


def get_mol_graph_features(smiles: str) -> dict | None:
    """
    Wyciąga cechy grafu molekularnego z ciągu SMILES.

    Cechy atomów (node_features) — 8 wartości na atom:
        [symbol, hybrydyzacja, num_H, w_pierścieniu,
         stereochemia, walencja, ładunek, stopień]

    Cechy wiązań (edge_features) — 5 wartości na krawędź:
        [typ_wiązania, stereochemia, aromatyczność,
         sprzężenie, w_pierścieniu]

    Graf jest dwukierunkowy — każde wiązanie daje 2 krawędzie.

    Zwraca None jeśli SMILES jest niepoprawny.
    """
    if smiles is None:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    # ── Cechy atomów ──────────────────────────────────────────────────────────
    node_features = []
    for atom in mol.GetAtoms():
        sym = atom.GetSymbol()
        feat = [
            _ATOM_SYMBOLS.index(sym) if sym in _ATOM_SYMBOLS else len(_ATOM_SYMBOLS),
            _HYBRIDIZATION_MAP.get(atom.GetHybridization(), 6),
            atom.GetTotalNumHs(),
            int(atom.IsInRing()),
            _CHIRAL_MAP.get(atom.GetChiralTag(), 0),
            atom.GetTotalValence(),
            atom.GetFormalCharge(),
            atom.GetDegree(),
        ]
        node_features.append(feat)

    # ── Cechy wiązań + krawędzie (bidirectional) ──────────────────────────────
    edge_index = []
    edge_features = []
    for bond in mol.GetBonds():
        i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        feat = [
            _BOND_TYPE_MAP.get(bond.GetBondType(), 4),
            _BOND_STEREO_MAP.get(bond.GetStereo(), 0),
            int(bond.GetIsAromatic()),
            int(bond.GetIsConjugated()),
            int(bond.IsInRing()),
        ]
        # Obie kierunki (i→j i j→i)
        edge_index  += [[i, j], [j, i]]
        edge_features += [feat, feat]

    return {
        "node_features": node_features,   # List[List[int]]  shape: [num_atoms, 8]
        "edge_index":    edge_index,       # List[List[int]]  shape: [num_edges*2, 2]
        "edge_features": edge_features,    # List[List[int]]  shape: [num_edges*2, 5]
    }


def add_graph_features_to_df(
    df: pl.DataFrame,
    smiles_col: str = "canonical_smiles"
) -> pl.DataFrame:
    """
    Dodaje do DataFrame'u Polars trzy kolumny z grafem molekularnym:
      - node_features  : list[list[i64]]  — cechy atomów
      - edge_index     : list[list[i64]]  — pary (src, dst) krawędzi
      - edge_features  : list[list[i64]]  — cechy wiązań

    Cząsteczki z niepoprawnym SMILES dostaną None w każdej kolumnie.
    """
    node_feat_col, edge_idx_col, edge_feat_col = [], [], []

    for smiles in df[smiles_col].to_list():
        result = get_mol_graph_features(smiles)
        if result is not None:
            node_feat_col.append(result["node_features"])
            edge_idx_col.append(result["edge_index"])
            edge_feat_col.append(result["edge_features"])
        else:
            node_feat_col.append(None)
            edge_idx_col.append(None)
            edge_feat_col.append(None)

    return df.with_columns([
        pl.Series("node_features",  node_feat_col),
        pl.Series("edge_index",     edge_idx_col),
        pl.Series("edge_features",  edge_feat_col),
    ])


def analyze_and_drop_correlated(df: pl.DataFrame, threshold=0.8) -> pl.DataFrame:
    """
    Analiza korelacji (Polars): Heatmapa, wypisanie par, usuwanie skorelowanych cech.
    """
    # W Polars operacje są zazwyczaj 'lazy' lub zwracają nowe obiekty,
    # ale dla bezpieczeństwa można zrobić clone, jeśli planujemy modyfikacje wewnątrz (choć tu zwracamy nowy df).
    df_clean = df.clone()

    # Wybieramy tylko kolumny numeryczne za pomocą selektorów
    numeric_df = df_clean.select(cs.numeric())

    if numeric_df.is_empty() or len(numeric_df.columns) < 2:
        print("   -> Zbyt mało kolumn numerycznych do analizy korelacji.")
        return df_clean

    # 1. Obliczanie macierzy korelacji
    corr_df = numeric_df.corr()

    # Przygotowanie danych do Heatmapy
    # Musimy przypisać nazwy kolumn jako indeks w Pandas, aby heatmapa miała etykiety
    corr_pandas = corr_df.to_pandas()
    corr_pandas.index = numeric_df.columns

    plt.figure(figsize=(12, 10))
    plt.title('Correlation Matrix')
    sns.heatmap(corr_pandas, linewidths=0.1, cmap='RdYlGn', annot=False)
    plt.show()
    print("   -> Wyświetlono heatmapę korelacji.")

    # 2. Znalezienie silnie skorelowanych par
    # W Polars nie używamy maskowania trójkąta (triu).
    # Zamiast tego robimy 'unpivot' (melt) i filtrujemy.

    # Dodajemy kolumnę z nazwami zmiennych (bo Polars nie ma indeksu)
    feature_names = numeric_df.columns

    long_corr = (
        corr_df
        .with_columns(pl.Series("var1", feature_names)) # Dodajemy nazwę wiersza
        .unpivot(index="var1", variable_name="var2", value_name="correlation") # Spłaszczamy macierz
    )

    # Filtrowanie:
    # 1. Usuwamy autokorelacje i duplikaty par (bierzemy tylko gdzie var1 < var2, to symuluje górny trójkąt)
    # 2. Bierzemy wartość bezwzględną korelacji > threshold
    high_corr_pairs = long_corr.filter(
        (pl.col("var1") < pl.col("var2")) &
        (pl.col("correlation").abs() > threshold)
    ).sort("correlation", descending=True)

    if not high_corr_pairs.is_empty():
        print(f"\n   Pary cech o korelacji powyżej {threshold}:")
        print(high_corr_pairs)

        # 3. Usuwanie cech (Automatyczne)
        # Strategia: Z pary (var1, var2) usuwamy var2 (tę "drugą" w kolejności, podobnie jak w logice Pandas upper_tri)

        potential_drop = high_corr_pairs.select("var2").unique().to_series().to_list()

        # Specjalna ochrona dla targetów
        protected_cols = ['is_active', 'pchembl_value', 'standard_value']
        to_drop = [col for col in potential_drop if col not in protected_cols]

        if to_drop:
            print(f"\n   -> Usuwanie {len(to_drop)} silnie skorelowanych cech: {to_drop}")
            df_clean = df_clean.drop(to_drop)
        else:
            print("   -> Znaleziono silne korelacje, ale dotyczą kolumn chronionych (targetów). Nie usuwam.")
    else:
        print("   -> Brak cech o korelacji powyżej progu.")

    return df_clean


# 1. Funkcja obliczająca komplet deskryptorów Lipińskiego
def get_lipinski_data(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        return {
            "MW": Descriptors.MolWt(mol),
            "LogP": Descriptors.MolLogP(mol),
            "HBD": Descriptors.NumHDonors(mol),
            "HBA": Descriptors.NumHAcceptors(mol)
        }
    return {"MW": None, "LogP": None, "HBD": None, "HBA": None}

# Uruchomienie
