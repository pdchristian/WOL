import re, json, glob, os
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 1. Gather all Translations.tr("...") keys from Python source files
all_keys = set()
for pyfile in glob.glob("wol_app/*.py"):
    content = open(pyfile, encoding="utf-8").read()
    found = re.findall(r'Translations\.tr\(["\']([a-zA-Z0-9_.]+)["\']', content)
    all_keys.update(found)

# 2. Load each locale file
for lang in ["en", "de", "fr", "es"]:
    path = f"wol_app/locales/{lang}.json"
    locale_keys = set(json.load(open(path, encoding="utf-8")).keys())
    
    missing = all_keys - locale_keys
    
    print(f"\n{'='*60}")
    print(f"Language: {lang.upper()} | Locale file: {path}")
    print(f"  Keys in code   : {len(all_keys)}")
    print(f"  Keys in locale : {len(locale_keys)}")
    print(f"  Missing        : {len(missing)}")
    print(f"  Extra (unused) : {len(locale_keys - all_keys)}")
    
    if missing:
        print(f"\n  MISSING KEYS:")
        for k in sorted(missing):
            print(f"    - {k}")