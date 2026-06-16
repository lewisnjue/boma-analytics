project structure 

```sh
boma-analytics/
├── config/
│   └── config.yaml          # Pipeline thresholds, API paths, and model hyperparams
├── data/
│   ├── processed/           # Features ready for model training
│   └── raw/                 # Unchanged data from house listing sources
├── models/                  # Saved serialized models (.pkl, .onnx, etc.)
├── notebooks/               # For EDA and prototyping
├── src/
│   └── boma_analytics/
│       ├── __init__.py
│       ├── ingestion.py     # Code to fetch/scrape data from target companies
│       ├── main.py          # Main execution entrypoint
│       ├── pipeline.py      # Orchestration layer for automated weekly/monthly jobs
│       └── training.py      # Training, retraining logic, and drift monitoring
├── tests/                   # Unit tests for data shapes and processing steps
├── .gitignore
├── .python-version
├── pyproject.toml           # Managed by uv
└── README.md
```