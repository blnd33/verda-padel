import ast,re,sys
from jinja2 import Environment,nodes
from pathlib import Path
from app.i18n import TRANSLATIONS
from app.routes.admin import MODULES
keys=set()
for p in Path('app/templates').rglob('*.html'):
    source=p.read_text(encoding='utf-8')
    keys.update(re.findall(r"\bt\('([^']*)'\)",source))
    keys.update(re.findall(r"\bfield\('[^']*','([^']*)'",source))
    # Capture display labels passed through literal template loops as well.
    for loop in Environment().parse(source).find_all(nodes.For):
        names=[loop.target.name] if isinstance(loop.target,nodes.Name) else [n.name for n in loop.target.items] if isinstance(loop.target,nodes.Tuple) else []
        translated={call.args[0].name for call in loop.find_all(nodes.Call) if isinstance(call.node,nodes.Name) and call.node.name=='t' and call.args and isinstance(call.args[0],nodes.Name)}
        if isinstance(loop.iter,nodes.List):
            for item in loop.iter.items:
                values=item.items if isinstance(item,nodes.Tuple) else [item]
                for name,value in zip(names,values):
                    if name in translated and isinstance(value,nodes.Const) and isinstance(value.value,str):
                        keys.add(value.value)
for p in [Path('app/services/core.py'),*Path('app/routes').glob('*.py')]:
    tree=ast.parse(p.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call):continue
        fn=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
        pos=1 if fn=='notify' else 0
        if fn in ['RuleError','audit','notify','flash'] and len(node.args)>pos and isinstance(node.args[pos],ast.Constant) and isinstance(node.args[pos].value,str):
            keys.add(node.args[pos].value)
for model,permission,title,fields in MODULES.values():
    keys.add(title)
    keys.update(field[1] for field in fields)
keys.discard('')
missing=sorted(keys-TRANSLATIONS.keys())
print('\n'.join(missing))
print(f'{len(keys)} extracted messages; {len(missing)} missing translations')
sys.exit(bool(missing))
