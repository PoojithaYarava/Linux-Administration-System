# Reproducible live-data evaluation

The production inference paths are implemented in `backend/app/intelligence.py` (unsupervised anomaly detection) and `backend/app/forecasting.py` (resource trend forecasts). The authenticated notebook `evaluation.ipynb` fetches real observations from a running API, applies those same modules, and displays the actual walk-forward forecast evaluation and observed anomaly findings available for that host.

## Run the notebook

1. Start the backend and sign in with an account that can read metrics.
2. Install Jupyter in the project Python environment if it is not already available: `python -m pip install jupyter`.
3. From the repository root, launch `jupyter notebook ml/evaluation.ipynb`.
4. Set `LAP_API_URL` if the API is not at `http://127.0.0.1:8000/api`. The notebook prompts for credentials unless `LAP_USERNAME` and `LAP_PASSWORD` are supplied in the environment.
5. Run the cells. It requires at least 12 valid timestamped observations for forecast evaluation and 20 observations for anomaly scoring. Empty/short histories are reported as insufficient data, not replaced with generated values.

The notebook does not claim labeled failure-prediction precision/recall. Its forecast MAE is specific to the returned host history and is not a production-wide quality claim. Credentials are requested at runtime and are not saved in notebook cells or outputs.
