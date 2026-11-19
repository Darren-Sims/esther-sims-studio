import re
VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
TAG=re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9-]*)\b[^>]*?(/?)>|<!--.*?-->', re.S)
def children(html, start=0, end=None):
    """Yield (s,e,tag,opening) for top-level elements in html[start:end]."""
    end=len(html) if end is None else end
    i=start; depth=0; cur=None; out=[]
    raw=('script','style')
    while i<end:
        m=TAG.search(html,i,end)
        if not m: break
        if m.group(0).startswith('<!--'):
            i=m.end(); continue
        close,tag,selfc=m.group(1),m.group(2).lower(),m.group(3)
        if not close and tag in raw:
            j=html.find(f'</{tag}>',m.end())
            if depth==0: out.append((m.start(),j+len(tag)+3,tag,m.group(0)))
            i=j+len(tag)+3; continue
        if close:
            depth-=1
            if depth==0 and cur: out.append((cur[0],m.end(),cur[1],cur[2])); cur=None
        elif tag in VOID or selfc:
            if depth==0: out.append((m.start(),m.end(),tag,m.group(0)))
        else:
            if depth==0: cur=(m.start(),tag,m.group(0))
            depth+=1
        i=m.end()
    return out
