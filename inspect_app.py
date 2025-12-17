import app
import inspect

print("Inspecting app module...")
if hasattr(app, 'presenze_required'):
    print("Found presenze_required in app module")
    print(inspect.getsource(app.presenze_required))
else:
    print("presenze_required NOT found in app module")

if hasattr(app, 'amministrazione_required'):
    print("Found amministrazione_required in app module")
else:
    print("amministrazione_required NOT found in app module")
