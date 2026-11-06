"""Bundle the app into one self-contained HTML file: dist/Miu手帳.html (double-click to open).

Each ES module becomes an IIFE that returns its exports; imports become destructuring.
CSS and miu-pixel.js are inlined. Fonts still load from Google Fonts / jsDelivr when online.
Run:  python3 app/build.py
"""
import pathlib, re

ROOT = pathlib.Path(__file__).parent
ORDER = ['store', 'schedule', 'app']

def module(name):
    src = (ROOT / 'js' / f'{name}.js').read_text(encoding='utf-8')
    def imp(m):
        names, frm = m.group(1), pathlib.Path(m.group(2)).stem
        return f'const {{{names}}} = __{frm};'
    src = re.sub(r"^import\s*\{([^}]*)\}\s*from\s*'([^']+)';", imp, src, flags=re.M)
    exported = re.findall(r'^export\s+(?:async\s+)?(?:function|const|let|class)\s+(\w+)', src, flags=re.M)
    src = re.sub(r'^export\s+', '', src, flags=re.M)
    return f'const __{name} = (() => {{\n{src}\nreturn {{{", ".join(exported)}}};\n}})();\n'

html = (ROOT / 'index.html').read_text(encoding='utf-8')
css = (ROOT / 'css' / 'app.css').read_text(encoding='utf-8')
miu = (ROOT / 'js' / 'miu-pixel.js').read_text(encoding='utf-8')
bundle = ''.join(module(n) for n in ORDER).replace('</script', '<\\/script')

html = html.replace('<link rel="stylesheet" href="css/app.css">', f'<style>\n{css}\n</style>')
html = html.replace('<script src="js/miu-pixel.js"></script>', '<script>\n' + miu.replace('</script', '<\\/script') + '\n</script>')
html = html.replace('<script type="module" src="js/app.js"></script>', f'<script>\n{bundle}</script>')
assert 'src="js/' not in html and 'href="css/' not in html
out = ROOT / 'dist' / 'Miu手帳.html'
out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding='utf-8')
print('wrote', out, f'{len(html) // 1024} KB')
