# RS Investment 🚀

A comprehensive 6-month relative strength (RS) scanner for US stocks.

## Live Demo

🔗 **Website**: <https://coreorders.github.io/RS_Investment/>

## Features

- 📊 **Individual RS Analysis**: Track individual stock performance vs QQQ benchmark (1M, 3M, 6M)
- 🎯 **Weighted RS (WRS)**: Sector/industry level analysis with market cap weighting
- 📈 **Today's List**: Auto-filtered list of top-performing stocks in strong sectors
- 💹 **50DIV**: 50-day moving average divergence indicator
- 📱 **Responsive UI**: Dark-themed, mobile-friendly interface
- 🔄 **Auto-Update**: Daily data collection via GitHub Actions
- ✨ **RS_Investment**: Renamed project for investment purposes

## Quick Start

Visit **<https://coreorders.github.io/RS_Investment/>** to start using the scanner!

## Local Development

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/coreorders/RS_Investment.git
cd RS_Investment

# Install dependencies
pip install -r requirements.txt

# Run data collection
python fetch_and_save.py
```

### View Locally

Simply open `index.html` in your browser, or use a simple HTTP server:

```bash
python -m http.server 8000
```

Then visit `http://localhost:8000`

## Data Updates

Data is updated daily after US market close (21:00 UTC / 6:00 AM KST) via GitHub Actions.

## Tech Stack

- **Frontend**: Vanilla JavaScript, HTML, CSS
- **Data Collection**: Python (pandas, yfinance)
- **Hosting**: GitHub Pages
- **Automation**: GitHub Actions

## Project Structure

```
RS_Investment/
├── .github/
│   └── workflows/         # GitHub Actions automation
├── static/                # Data files
│   ├── result.json        # Main stock data
│   └── sector_search.json # Sector/industry data
├── templates/             # HTML templates (if any)
├── index.html             # Main frontend application
├── fetch_and_save.py      # Data collection script
├── utils.py               # Helper functions
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Key Metrics

- **RS (Relative Strength)**: Stock return - QQQ return (1M, 3M, 6M periods)
- **RS Rank (%)**: Percentile ranking of RS values (lower is better)
- **50DIV (%)**: Percentage deviation from 50-day moving average
- **WRS**: Market-cap weighted relative strength by sector/industry
- **WRS_MD**: Median RS value within each sector/industry

## Today's List Criteria

Automatically filters stocks using:

- **Sector Filter**: Count ≥ 2, WRS rank ≤ 30%, WRS_MD rank ≤ 40%
- **Stock Filter**: RS rank ≤ 20% within qualified sectors

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is for **personal educational purposes only** and is **not for commercial use**.
Data provided by Yahoo Finance.

## Disclaimer

All data is strictly for informational purposes and should not be considered financial advice. This tool is provided as-is with no warranties.

## Credits

- **Idea & Development**: In-kyu Lee (인규 이)
- **Data**: Yahoo Finance API

---

Made with ❤️ for stock market analysis
