# support

Support queues can get overwhelming fast. I made this small dashboard to turn a pile of tickets into a clearer picture of what needs attention, what is overdue, and what keeps coming back.

The tickets are fictional. I deliberately based them on familiar team, student, and retail-style tech issues instead of using any real customer or employee information.

## What it can do

- Store and query support tickets in SQLite
- Surface open, overdue, and average-resolution-time metrics
- Filter by status, priority, or a keyword
- Add a new fictional ticket through the dashboard
- Group recurring issues so patterns are easier to spot
- Serve a simple JSON API and responsive interface without a framework

## Built with

- Python's standard library (`http.server`, `sqlite3`, `json`)
- SQLite
- HTML, CSS, and vanilla JavaScript

I kept the stack deliberately small so I could understand every layer instead of hiding the useful parts behind a template.

## Run it locally

```bash
cd supportops-dashboard
python3 app.py
```

Open `http://localhost:8000`. On the first run, the app creates a local database and fills it with fictional tickets.

To deliberately restore the original demo data later:

```bash
python3 app.py --reset-demo
```

## API endpoints

- `GET /api/metrics`
- `GET /api/tickets`
- `GET /api/tickets?status=Open&priority=High&query=Wi-Fi`

## A few design choices

- **SQLite:** enough structure to practise queries and metrics, without needing a cloud account.
- **Search on the server:** filters are part of the API, so the browser does not have to download everything first.
- **Fictional data:** it makes the project safe to share publicly while still looking at realistic support patterns.

## If you ask me about it in an interview

I would start with the problem: it is easy to lose track of which support issues are urgent or repeating. Then I would explain how the ticket data is stored, how the Python API applies filters, and how the dashboard turns the results into a quick triage view.

Before adding this to a résumé, I should be able to walk through the code and describe those choices in my own words.
