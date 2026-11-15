"""Check published report links and accidental raw/credential files (stdlib only)."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import json,re

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.ids=set();self.captions=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.add(a['id'])
        if tag=='a' and 'href' in a:self.links.append(a['href'])
        if tag=='img' and 'src' in a:self.links.append(a['src'])
        if tag=='figcaption':self.captions+=1

def main():
    root=Path(__file__).resolve().parent;missing=[];pages={}
    for p in (root/'report').rglob('*.html'):
        page=Page();page.feed(p.read_text(encoding='utf-8'));pages[p.resolve()]=page
    references=[(p,h) for p,page in pages.items() for h in page.links]
    for name in ['README.md','FINDINGS.md','FIGURE_GUIDE.md']:
        p=root/name
        references.extend((p,h) for h in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')))
    for source,href in references:
        u=urlsplit(href)
        if u.scheme or u.netloc:continue
        target=(source.parent/unquote(u.path)).resolve() if u.path else source.resolve()
        if not target.exists():missing.append({'source':str(source.relative_to(root)),'target':href})
        elif u.fragment and target in pages and unquote(u.fragment) not in pages[target].ids:
            missing.append({'source':str(source.relative_to(root)),'target':href,'reason':'missing fragment'})
    forbidden=[];suspects=[]
    patterns=[r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{30,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'postgres(?:ql)?://[^\s/:]+:[^\s/@]+@']
    files=[p for p in root.rglob('*') if p.is_file()]
    for p in files:
        if p.name=='.env' or p.suffix in ['.pkl','.npz','.sqlite','.db']:forbidden.append(str(p.relative_to(root)))
        if p.suffix in ['.py','.md','.json','.html','.cjs','.csv','.txt']:
            text=p.read_text(encoding='utf-8-sig')
            if any(re.search(pattern,text) for pattern in patterns):suspects.append(str(p.relative_to(root)))
    main_report=pages[(root/'report/deepening/index.html').resolve()]
    result=dict(passed=not missing and not forbidden and not suspects and main_report.captions==12,
        checked_reports=len(pages),main_report_figures=main_report.captions,
        missing_links=missing,credential_pattern_hits=suspects,forbidden_raw_or_secret_files=forbidden,
        largest_file_bytes=max(p.stat().st_size for p in files))
    (root/'verification').mkdir(exist_ok=True)
    (root/'verification/package_scan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
