from app import create_app, db
from app.models import User, Portfolio, Holding

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Portfolio': Portfolio, 'Holding': Holding}

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
