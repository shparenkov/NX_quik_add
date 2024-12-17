from flask import Flask, render_template, request, redirect, url_for, send_file, session
import sqlite3
import csv
from datetime import datetime  # Import for timestamp

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'  # Store session on the server-side

# Function to fetch equipment from the database
def fetch_equipment(search_query=None):
    conn = sqlite3.connect('equipment.db')
    cursor = conn.cursor()
    if search_query:
        cursor.execute("""
            SELECT category, type_id, description
            FROM equipment
            WHERE (description LIKE ? OR category LIKE ?)
            AND description NOT LIKE '%[sales]%'
            AND category NOT LIKE '%[sales]%'
            ORDER BY CASE WHEN category = 'Cables' THEN 1 ELSE 2 END, description
        """, (f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("""
            SELECT category, type_id, description
            FROM equipment
            WHERE description NOT LIKE '%[sales]%'
            AND category NOT LIKE '%[sales]%'
            ORDER BY CASE WHEN category = 'Cables' THEN 1 ELSE 2 END, description
        """)
    data = cursor.fetchall()
    conn.close()
    return data

# Route: Main Page to Display Equipment
@app.route('/', methods=['GET', 'POST'])
def index():
    # Default sorting preferences
    category_sort = request.form.get('category_sort', 'asc')  # 'asc' or 'desc'
    equipment_sort = request.form.get('equipment_sort', 'asc')  # 'asc' or 'desc'

    # Fetch data
    search_query = request.form.get('search', '').strip()
    data = fetch_equipment(search_query)

    # Group data by category
    equipment_by_category = {}
    for category, type_id, description in data:
        if category not in equipment_by_category:
            equipment_by_category[category] = []
        equipment_by_category[category].append((type_id, description))

    # Sort categories
    if category_sort == 'asc':
        equipment_by_category = dict(sorted(equipment_by_category.items()))
    elif category_sort == 'desc':
        equipment_by_category = dict(sorted(equipment_by_category.items(), reverse=True))

    # Sort equipment within each category
    for category in equipment_by_category:
        if equipment_sort == 'asc':
            equipment_by_category[category].sort(key=lambda x: x[1])  # Sort by Description A-Z
        elif equipment_sort == 'desc':
            equipment_by_category[category].sort(key=lambda x: x[1], reverse=True)  # Sort Z-A

    # Pass data and sorting options to the template
    selections = session.get('selections', {})
    return render_template('index.html', 
                           equipment_by_category=equipment_by_category, 
                           search_query=search_query,
                           selections=selections,
                           category_sort=category_sort,
                           equipment_sort=equipment_sort)


# Route: Add to Summary
@app.route('/summary', methods=['POST', 'GET'])
def summary():
    # Update session quantities if user changes them on summary page
    if request.method == 'POST':
        session['selections'] = {}  # Reset the session to avoid duplicates
        for key, value in request.form.items():
            if value.isdigit() and int(value) > 0:
                session['selections'][key] = int(value)

    # Fetch descriptions and prepare items for the summary page
    conn = sqlite3.connect('equipment.db')
    cursor = conn.cursor()
    summary_items = []
    for type_id, quantity in session.get('selections', {}).items():
        cursor.execute("SELECT description FROM equipment WHERE type_id = ?", (type_id,))
        result = cursor.fetchone()
        if result:
            summary_items.append((type_id, result[0], quantity))
    conn.close()

    return render_template('summary.html', summary_items=summary_items)

# Route: Export to CSV
@app.route('/export', methods=['POST'])
def export():
    # Update session with submitted quantities
    for key, value in request.form.items():
        if value.isdigit() and int(value) > 0:
            session['selections'][key] = int(value)
        elif key in session['selections']:  # Remove items with 0 quantity
            session['selections'].pop(key)

    # Generate timestamped file name
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    csv_file = f"export_{timestamp}.csv"

    # Create CSV file
    with open(csv_file, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['TYPE', 'QUANTITY'])  # Headers
        for type_id, quantity in session.get('selections', {}).items():
            writer.writerow([type_id, quantity])

    return send_file(csv_file, as_attachment=True)

@app.route('/clear')
def clear():
    # Safely clear the selections key if it exists
    if 'selections' in session:
        session.pop('selections', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
