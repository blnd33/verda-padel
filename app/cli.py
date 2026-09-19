import getpass
from pathlib import Path
import sqlite3
import click
from flask_migrate import upgrade
from app import db
from app.models import Settings,TransactionLock,User,Stadium,Table,Product,Category

def register_commands(app):
    @app.cli.command('setup')
    def setup():
        """Apply migrations and initialize empty Verda configuration."""
        upgrade()
        if not db.session.get(TransactionLock,1):
            db.session.add(TransactionLock(id=1))
        if not db.session.get(Settings,1):
            db.session.add(Settings(id=1,site_name='Verda Padel',default_language='en'))
        db.session.commit()
        click.echo('Verda schema ready. Run create-admin, then configure the venue in Settings.')

    @app.cli.command('create-admin')
    @click.option('--username',prompt=True)
    @click.option('--email',prompt=True)
    @click.option('--password',prompt=True,hide_input=True,confirmation_prompt=True)
    def create_admin(username,email,password):
        """Create an administrator; no default or fixed password is seeded."""
        if len(password)<12 or not username.strip() or '@' not in email:
            raise click.ClickException('Use a username, valid email and password of at least 12 characters.')
        if User.query.filter(db.or_(User.username==username.strip().lower(),User.email==email.strip().lower())).first():
            raise click.ClickException('Username or email already exists.')
        user=User(username=username.strip().lower(),email=email.strip().lower(),role='super_admin',is_active=True,is_admin=True,permissions=[])
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo('Administrator created. Sign in at /auth/login.')

    @app.cli.command('demo-data')
    def demo_data():
        """Add clearly fictional inventory and courts to an empty development database."""
        if app.config['SESSION_COOKIE_SECURE']:
            raise click.ClickException('Demo seeding is disabled in production.')
        if Stadium.query.first() or Product.query.first():
            raise click.ClickException('Demo data requires an empty venue catalog.')
        s=db.session.get(Settings,1)
        if not s:
            raise click.ClickException('Run setup first.')
        s.demo_mode=True
        s.opening_hour,s.closing_hour,s.price_per_hour=9,2,30000
        for i in range(1,4):
            db.session.add(Stadium(name=f'Demo Court {i:02}',description='Demonstration court — configure before launch.',price_per_hour=30000,is_active=True))
        for i in range(1,5):
            db.session.add(Table(name=f'Demo Table {i:02}',capacity=4,is_active=True))
        equipment=Category(name_ar='معدات البادل',name_en='Padel essentials')
        refreshments=Category(name_ar='مشروبات',name_en='Refreshments')
        db.session.add_all([equipment,refreshments])
        db.session.flush()
        examples=[('Demo racket','مضرب تجريبي',95000,60000,equipment),('Demo balls · 3 pack','كرات تجريبية',12000,7000,equipment),('Demo overgrip','قبضة تجريبية',5000,2000,equipment),('Demo water','مياه تجريبية',1000,500,refreshments)]
        for i,(en,ar,price,cost,category) in enumerate(examples):
            db.session.add(Product(name_en=en,name_ar=ar,description_en='Fictional demonstration item. Replace with your approved inventory.',
                price=price,cost_price=cost,stock=25,category_id=category.id,track_stock=True,featured=True,barcode=f'VERDADEMO{i+1:04}'))
        db.session.commit()
        click.echo('Fictional demo catalog added. Demo banners stay visible until disabled in Settings.')

    @app.cli.command('backup')
    @click.argument('destination',type=click.Path(path_type=Path))
    def backup(destination):
        """Create a consistent SQLite backup outside the active database path."""
        if db.engine.dialect.name!='sqlite':
            raise click.ClickException('Use your database engine native backup tooling for this database.')
        source=Path(db.engine.url.database).resolve()
        target=destination.resolve()
        if source==target or target.exists():
            raise click.ClickException('Choose a new backup file path.')
        target.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(source) as live,sqlite3.connect(target) as copy:
            live.backup(copy)
        click.echo('Database backup created. Also copy app/static/uploads and retain SECRET_KEY securely.')
