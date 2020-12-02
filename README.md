# ebayKleinanzeigen

## Prerequisites

* config.json (from config.json.example)
* geckodriver (to /usr/local/bin): https://github.com/mozilla/geckodriver/releases
* Python packages: ```pip install selenium python-dateutil```

## Features

- **New** Can send E-mails on failure, along with a screenshot of the browser session
- **New** Refined logging (info, warning, error, debug)
- **New** Now passes Python 3 linting
- **New** Automatically deletes and re-publishes ad if existing one is too old
- **New** Keeps track of ad publishing and last updating date
- **New** Ability to selectively enable / disable ads being published / updated
- Selects category and fills the form data
- Uploads multiple photos
