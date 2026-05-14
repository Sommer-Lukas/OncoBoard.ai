# Data seeding

OncoBoard.ai ships two seed paths:

## 1. Synthetic seed (fast, no download)

Four hand-crafted cases that cover every molecular subtype (Luminal A,
Luminal B, HER2-enriched, Triple Negative). Useful for development,
tests, and demos when you don't want to pull down the full dataset.

```powershell
.\.venv\Scripts\python.exe -m src.data.seed_synthetic
```

Fixture lives at `src/data/fixtures/synthetic_cases.json`. Case IDs are
`SYN-001`..`SYN-004`. Each row also seeds a small `case_genomics` blob
(7 sample genes) so the gene-lookup path is exercised end-to-end.

## 2. Real TCGA-BRCA seed (Kaggle)

### Download

Kaggle dataset: `breast-cancer-vision-and-genomic-fusion-ml-ready`.

You need the three CSVs unzipped into `data/raw/`:

```
data/raw/
  Clinical_Treatment_Data.csv     # ~1097 patients, clean receptor + drug one-hots
  Clinical_Demographic_Data.csv   # ~122 patients, rich TCGA fields
  CNV_RAW.csv                     # ~125 patients × ~59K gene columns
```

The MRI/SVS image patches are optional and not required for the seed —
the loader registers their file paths in `case_files` only if you pass
`--images-dir`.

`data/raw/` is gitignored — never commit the CSVs.

### Run

```powershell
.\.venv\Scripts\python.exe -m src.data.seed_tcga
```

To also register image files (slow — 250K+ patches):

```powershell
.\.venv\Scripts\python.exe -m src.data.seed_tcga --images-dir data/raw/MRI_and_SVS_Patches
```

### What it does

- Reads `Clinical_Treatment_Data.csv` row-by-row → upserts into `cases`.
  `case_id` = `bcr_patient_barcode` (full TCGA barcode).
- For each case, looks up matching `Patient_ID` in
  `Clinical_Demographic_Data.csv` and stores the raw row as
  `source_demographic_json`.
- Extracts the drug one-hot columns (`Drug_<Name>`) into a deduped list
  in `treatments_json`.
- Derives `molecular_subtype` from ER/PR/HER2 IHC (see
  `src/data/subtype.py`).
- Reads `CNV_RAW.csv` → for each case that's already in the DB, stores a
  `{gene: copy_number}` blob in `case_genomics`. The `CNV_` prefix is
  stripped so agents look up `TP53`, not `CNV_TP53`.

The script is idempotent: re-running upserts rows by primary key.
