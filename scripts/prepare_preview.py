"""One-time local preview account; never run by application startup."""
import secrets
from pathlib import Path
from app import create_app,db
from app.models import User

app=create_app()
if app.config['SESSION_COOKIE_SECURE']:
    raise SystemExit('Preview accounts are disabled in production.')
with app.app_context():
    if User.query.first():
        print('An account already exists; existing credentials were preserved.')
    else:
        password=secrets.token_urlsafe(18)
        result=app.test_cli_runner().invoke(args=['create-admin','--username','verda-preview','--email','preview@verda.invalid','--password',password])
        if result.exit_code:
            raise RuntimeError(result.output)
        (Path(app.instance_path)/'preview-access.txt').write_text(
            'LOCAL DEVELOPMENT ONLY\nURL: http://127.0.0.1:5000/auth/login\nUsername: verda-preview\nPassword: '+password+
            '\n\nCreate personal staff accounts before deployment. Do not deploy this development database.\n',encoding='utf-8')
        print('Unique preview credentials saved to instance/preview-access.txt.')
