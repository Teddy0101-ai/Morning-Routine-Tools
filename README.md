# Morning Routine Program

Single-page Streamlit version of your two tools.

## Layout
- Left: Ticker Assistant
- Right: Stock Graph Generator
- No page navigation in the sidebar

## Deploy on Streamlit Community Cloud
- Upload everything in this folder to a new GitHub repo
- Main file path: `Home.py`

## Logo file location
Put your logo file here:

```text
logo/logo.png
```

This is the first location checked by the stock graph generator.

## Notes
- The stock graph PNG generation logic is kept in `utils/stock_graph.py`
- `packages.txt` installs Chromium for Kaleido/Plotly image export on Streamlit Cloud
