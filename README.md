# Energy Management App

Simple Flask application for managing energy meter readings and generating rebilling invoices.

## Features
- Manage meters with nickname, type (electricity, gas, water) and tenant to bill.
- Enter readings for a selected month and energy type.
- Edit previously entered readings.
- Generate invoice table showing usage difference from previous month.

## Running
```bash
pip install -r requirements.txt
python3 -m flask --app app.py run
```
Then open `http://localhost:5000` in your browser.
